import os
from typing import Optional, List
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from .base import LLMProvider
from .models import LLMResponse, ChatSession, ChatMessage


class GeminiChatSession(ChatSession):
    def __init__(self, client: genai.Client, model: str, system_instruction: Optional[str] = None, temperature: float = 0.3):
        self._client = client
        self._model = model
        self._provider_name = "gemini"

        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction
        )
        self._chat = client.chats.create(model=model, config=config)

    def send_message(self, message: str) -> LLMResponse:
        response = self._chat.send_message(message)
        return LLMResponse(
            text=response.text,
            raw_response=response,
            model=self._model,
            provider=self._provider_name
        )

    def get_history(self) -> List[ChatMessage]:
        messages = []
        for item in self._chat._curated_history:
            role = "user"
            if item.role == "model":
                role = "assistant"
            elif item.role == "system":
                role = "system"

            content = ""
            if hasattr(item, 'parts') and item.parts:
                for part in item.parts:
                    if hasattr(part, 'text') and part.text:
                        content += part.text

            messages.append(ChatMessage(role=role, content=content))
        return messages


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client = None
        if self._api_key:
            try:
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                print(f"DEBUG: Failed to initialize Gemini client: {e}")

    @property
    def name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return self._client is not None and self._api_key is not None and len(self._api_key) > 0

    def generate_content(
        self,
        model: str,
        contents: str,
        system_instruction: Optional[str] = None,
        response_mime_type: Optional[str] = None,
        temperature: float = 0.1
    ) -> LLMResponse:
        if not self.is_available():
            raise Exception("Gemini provider is not available")

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature
        )
        if response_mime_type:
            config.response_mime_type = response_mime_type

        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )

        return LLMResponse(
            text=response.text,
            raw_response=response,
            model=model,
            provider=self.name
        )

    def create_chat(
        self,
        model: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3
    ) -> ChatSession:
        if not self.is_available():
            raise Exception("Gemini provider is not available")

        return GeminiChatSession(
            client=self._client,
            model=model,
            system_instruction=system_instruction,
            temperature=temperature
        )
