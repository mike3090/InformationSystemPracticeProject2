from __future__ import annotations

import httpx

from .config import Settings
from .schemas import ChatMessage, ChatReply


class LocalChatClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def ask(self, user_text: str, history: list[ChatMessage]) -> ChatReply:
        payload = {
            "user_text": user_text,
            "system_prompt": self._settings.system_prompt,
            "history": [_dump_message(message) for message in history],
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                response = await client.post(f"{self._settings.server_url}/chat", json=payload)
            except httpx.RequestError as exc:
                raise RuntimeError(f"Could not reach local LLM server at {self._settings.server_url}: {exc!r}") from exc

        if response.is_error:
            raise RuntimeError(
                f"Local LLM server returned HTTP {response.status_code}.\n"
                f"Response body:\n{response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Local LLM server returned non-JSON response:\n{response.text}") from exc

        try:
            display_text = str(data.get("display_text") or data["assistant_text"]).strip()
            spoken_text = str(data.get("spoken_text") or display_text).strip()
        except KeyError as exc:
            raise RuntimeError(f"Local LLM server response did not include assistant_text/display_text:\n{data}") from exc
        return ChatReply(display_text=display_text, spoken_text=spoken_text)


def _dump_message(message: ChatMessage) -> dict[str, str]:
    if hasattr(message, "model_dump"):
        return message.model_dump()
    return message.dict()
