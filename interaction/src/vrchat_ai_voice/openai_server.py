from __future__ import annotations

from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from .config import load_settings
from .schemas import ChatMessage


class ChatRequest(BaseModel):
    user_text: str = Field(min_length=1)
    system_prompt: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    max_tokens: int = Field(default=220, ge=32, le=1000)


class ChatResponse(BaseModel):
    model: str
    assistant_text: str


settings = load_settings()
app = FastAPI(title="VRChat AI Voice OpenAI Server", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": settings.openai_model}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is empty. Copy .env.example to .env and fill your API key.",
        )

    messages: list[dict[str, str]] = []
    system_prompt = request.system_prompt or settings.system_prompt
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend({"role": item.role, "content": item.content} for item in request.history if item.role != "system")
    messages.append({"role": "user", "content": request.user_text})

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        completion = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.7,
            max_tokens=request.max_tokens,
        )
    except Exception as exc:  # OpenAI SDK exceptions carry useful text for local logs.
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {exc}") from exc

    content = completion.choices[0].message.content if completion.choices else ""
    assistant_text = (content or "").strip()
    if not assistant_text:
        raise HTTPException(status_code=502, detail="OpenAI returned an empty response.")
    return ChatResponse(model=settings.openai_model, assistant_text=assistant_text)


def main() -> None:
    import uvicorn

    uvicorn.run("vrchat_ai_voice.openai_server:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
