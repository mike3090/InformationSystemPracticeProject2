from __future__ import annotations

import json
import traceback

from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from .config import load_settings
from .schemas import ChatMessage, ChatReply


class ChatRequest(BaseModel):
    user_text: str = Field(min_length=1)
    system_prompt: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    max_tokens: int = Field(default=220, ge=32, le=1000)


class ChatResponse(BaseModel):
    model: str
    assistant_text: str
    spoken_text: str
    display_text: str


settings = load_settings()
app = FastAPI(title="VRChat AI Voice OpenAI Server", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": settings.openai_model}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not settings.openai_api_key:
        print("[ERROR] OPENAI_API_KEY is empty.", flush=True)
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is empty. Copy .env.example to .env and fill your API key.",
        )

    messages: list[dict[str, str]] = []
    system_prompt = request.system_prompt or settings.system_prompt
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "system", "content": _structured_output_instruction()})
    messages.extend({"role": item.role, "content": item.content} for item in request.history if item.role != "system")
    messages.append({"role": "user", "content": request.user_text})

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        completion = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.7,
            max_tokens=request.max_tokens,
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # OpenAI SDK exceptions carry useful text for local logs.
        print(f"[ERROR] OpenAI request failed: {exc}", flush=True)
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {exc}") from exc

    content = completion.choices[0].message.content if completion.choices else ""
    reply = _parse_chat_reply(content or "")
    if not reply.display_text:
        raise HTTPException(status_code=502, detail="OpenAI returned an empty response.")
    return ChatResponse(
        model=settings.openai_model,
        assistant_text=reply.display_text,
        display_text=reply.display_text,
        spoken_text=reply.spoken_text,
    )


def _structured_output_instruction() -> str:
    return (
        "Return ONLY a valid JSON object with exactly these string fields: "
        '"display_text" and "spoken_text". '
        '"display_text" must be shown to the user and must follow this format exactly: '
        "Japanese sentence followed by an English translation in parentheses, for example "
        "こちらにタッチしてください。（Please tap your card here.） "
        '"spoken_text" must contain only the Japanese text that should be spoken aloud by TTS. '
        "Do not include English, parentheses, labels, Markdown, or code fences in spoken_text. "
        "Do not output Chinese."
    )


def _parse_chat_reply(raw_content: str) -> ChatReply:
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI returned invalid JSON: {raw_content}") from exc

    try:
        reply = ChatReply(
            display_text=str(data["display_text"]).strip(),
            spoken_text=str(data["spoken_text"]).strip(),
        )
    except KeyError as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI JSON missing required field: {data}") from exc

    if not reply.spoken_text:
        raise HTTPException(status_code=502, detail=f"OpenAI JSON has empty spoken_text: {data}")
    return reply


def main() -> None:
    import uvicorn

    uvicorn.run("vrchat_ai_voice.openai_server:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
