import os
from typing import Optional, List
from openai import OpenAI
from openai.types.chat import ChatCompletion
from .base import LLMProvider
from .models import LLMResponse, ChatSession, ChatMessage


class DeepseekChatSession(ChatSession):
    def __init__(self, client: OpenAI, model: str, system_instruction: Optional[str] = None, temperature: float = 0.3):
        self._client = client
        self._model = model
        self._temperature = temperature
        self._provider_name = "deepseek"
        self._history: List[ChatMessage] = []

        if system_instruction:
            self._history.append(ChatMessage(role="system", content=system_instruction))

    def send_message(self, message: str) -> LLMResponse:
        self._history.append(ChatMessage(role="user", content=message))

        messages = [{"role": msg.role, "content": msg.content} for msg in self._history]

        response: ChatCompletion = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature
        )

        assistant_content = response.choices[0].message.content
        self._history.append(ChatMessage(role="assistant", content=assistant_content))

        return LLMResponse(
            text=assistant_content,
            raw_response=response,
            model=self._model,
            provider=self._provider_name
        )

    def get_history(self) -> List[ChatMessage]:
        return self._history.copy()


class DeepseekProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self._base_url = base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self._client = None

        if self._api_key:
            try:
                self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
            except Exception as e:
                print(f"DEBUG: Failed to initialize Deepseek client: {e}")

    @property
    def name(self) -> str:
        return "deepseek"

    def is_available(self) -> bool:
        return self._client is not None and self._api_key is not None and len(self._api_key) > 0

    def _map_model_name(self, model: str) -> str:
        model_mapping = {
            "gemini-2.5-flash": "deepseek-chat",
            "gemini-2.5-pro": "deepseek-reasoner",
            "gemini-2.0-flash": "deepseek-chat",
            "gemini-1.5-flash": "deepseek-chat",
            "gemini-1.5-pro": "deepseek-reasoner",
        }
        return model_mapping.get(model, "deepseek-chat")

    def generate_content(
        self,
        model: str,
        contents: str,
        system_instruction: Optional[str] = None,
        response_mime_type: Optional[str] = None,
        temperature: float = 0.1
    ) -> LLMResponse:
        if not self.is_available():
            raise Exception("Deepseek provider is not available")

        mapped_model = self._map_model_name(model)

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": contents})

        if response_mime_type == "application/json":
            messages.append({
                "role": "system",
                "content": "You must respond with valid JSON only. No markdown formatting, no explanation text."
            })

        response: ChatCompletion = self._client.chat.completions.create(
            model=mapped_model,
            messages=messages,
            temperature=temperature
        )

        content = response.choices[0].message.content

        if response_mime_type == "application/json" and content:
            content = self._extract_json_from_markdown(content)

        return LLMResponse(
            text=content,
            raw_response=response,
            model=mapped_model,
            provider=self.name
        )

    def _extract_json_from_markdown(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def create_chat(
        self,
        model: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3
    ) -> ChatSession:
        if not self.is_available():
            raise Exception("Deepseek provider is not available")

        mapped_model = self._map_model_name(model)

        return DeepseekChatSession(
            client=self._client,
            model=mapped_model,
            system_instruction=system_instruction,
            temperature=temperature
        )
