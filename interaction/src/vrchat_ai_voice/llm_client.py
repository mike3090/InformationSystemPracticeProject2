from __future__ import annotations

import httpx

from .config import Settings
from .schemas import ChatMessage


class LocalChatClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def ask(self, user_text: str, history: list[ChatMessage]) -> str:
        payload = {
            "user_text": user_text,
            "system_prompt": self._settings.system_prompt,
            "history": [_dump_message(message) for message in history],
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(f"{self._settings.server_url}/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        return str(data["assistant_text"]).strip()


def _dump_message(message: ChatMessage) -> dict[str, str]:
    if hasattr(message, "model_dump"):
        return message.model_dump()
    return message.dict()
