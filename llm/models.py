from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class ChatMessage:
    role: str  # user, assistant, system
    content: str


@dataclass
class LLMResponse:
    text: str
    raw_response: Any
    model: str
    provider: str


class ChatSession:
    def send_message(self, message: str) -> LLMResponse:
        raise NotImplementedError

    def get_history(self) -> List[ChatMessage]:
        raise NotImplementedError
