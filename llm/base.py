from abc import ABC, abstractmethod
from typing import Optional, List
from .models import LLMResponse, ChatSession, ChatMessage


class LLMProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def generate_content(
        self,
        model: str,
        contents: str,
        system_instruction: Optional[str] = None,
        response_mime_type: Optional[str] = None,
        temperature: float = 0.1
    ) -> LLMResponse:
        pass

    @abstractmethod
    def create_chat(
        self,
        model: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3
    ) -> ChatSession:
        pass
