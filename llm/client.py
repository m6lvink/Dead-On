import os
import time
from typing import Optional, List, Dict, Tuple
from collections import OrderedDict
from .base import LLMProvider
from .models import LLMResponse, ChatSession, ChatMessage
from .gemini_provider import GeminiProvider
from .deepseek_provider import DeepseekProvider


class UnifiedLLMClient:
    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        deepseek_api_key: Optional[str] = None,
        deepseek_base_url: Optional[str] = None,
        max_chat_sessions: int = 1000
    ):
        self._providers: Dict[str, LLMProvider] = {}
        self._chat_sessions: OrderedDict[str, Tuple[ChatSession, str]] = OrderedDict()
        self._max_chat_sessions = max_chat_sessions

        gemini = GeminiProvider(api_key=gemini_api_key)
        if gemini.is_available():
            self._providers["gemini"] = gemini
        else:
            print("WARNING: Gemini provider is not available")

        deepseek = DeepseekProvider(api_key=deepseek_api_key, base_url=deepseek_base_url)
        if deepseek.is_available():
            self._providers["deepseek"] = deepseek
        else:
            print("WARNING: Deepseek provider is not available")

        if not self._providers:
            print("CRITICAL WARNING: No LLM providers are available")

    def is_available(self) -> bool:
        return len(self._providers) > 0

    def _get_primary_provider(self) -> Optional[LLMProvider]:
        return self._providers.get("gemini") or self._providers.get("deepseek")

    def _get_fallback_provider(self) -> Optional[LLMProvider]:
        return self._providers.get("deepseek")

    def _is_rate_limit_error(self, error: Exception) -> bool:
        error_str = str(error)
        return (
            "429" in error_str or
            "RESOURCE_EXHAUSTED" in error_str or
            "rate limit" in error_str.lower() or
            "quota exceeded" in error_str.lower()
        )

    def generate_content(
        self,
        model: str,
        contents: str,
        system_instruction: Optional[str] = None,
        response_mime_type: Optional[str] = None,
        temperature: float = 0.1,
        retries: int = 3,
        delay: int = 2
    ) -> LLMResponse:
        if not self.is_available():
            raise Exception("No LLM providers are available")

        last_error = None

        primary = self._get_primary_provider()
        if primary:
            for attempt in range(retries):
                try:
                    return primary.generate_content(
                        model=model,
                        contents=contents,
                        system_instruction=system_instruction,
                        response_mime_type=response_mime_type,
                        temperature=temperature
                    )
                except Exception as e:
                    last_error = e
                    if self._is_rate_limit_error(e):
                        print(f"DEBUG: Gemini rate limit hit. Retrying in {delay}s...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        break

        fallback = self._get_fallback_provider()
        if fallback and fallback != primary:
            print(f"DEBUG: Falling back to Deepseek")
            for attempt in range(retries):
                try:
                    return fallback.generate_content(
                        model=model,
                        contents=contents,
                        system_instruction=system_instruction,
                        response_mime_type=response_mime_type,
                        temperature=temperature
                    )
                except Exception as e:
                    last_error = e
                    if self._is_rate_limit_error(e):
                        print(f"DEBUG: Deepseek rate limit hit. Retrying in {delay}s...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        raise e

        raise last_error or Exception("All providers failed")

    def _evict_oldest_session(self):
        if len(self._chat_sessions) > 0:
            oldest_key = next(iter(self._chat_sessions))
            del self._chat_sessions[oldest_key]
            print(f"DEBUG: Evicted oldest chat session: {oldest_key}")

    def get_or_create_chat(
        self,
        user_id: str,
        model: str = "gemini-2.5-flash",
        system_instruction: Optional[str] = None,
        temperature: float = 0.3
    ) -> ChatSession:
        if not self.is_available():
            raise Exception("No LLM providers are available")

        if len(self._chat_sessions) >= self._max_chat_sessions:
            self._evict_oldest_session()

        if user_id in self._chat_sessions:
            session, session_model = self._chat_sessions[user_id]
            if session_model == model:
                self._chat_sessions.move_to_end(user_id)
                return session

        provider = self._get_primary_provider()
        if not provider:
            provider = self._get_fallback_provider()

        if not provider:
            raise Exception("No LLM providers are available")

        session = provider.create_chat(
            model=model,
            system_instruction=system_instruction,
            temperature=temperature
        )

        self._chat_sessions[user_id] = (session, model)
        self._chat_sessions.move_to_end(user_id)

        return session

    def send_chat_message(
        self,
        user_id: str,
        message: str,
        model: str = "gemini-2.5-flash",
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
        retries: int = 3,
        delay: int = 2
    ) -> LLMResponse:
        chat = self.get_or_create_chat(
            user_id=user_id,
            model=model,
            system_instruction=system_instruction,
            temperature=temperature
        )

        for attempt in range(retries):
            try:
                return chat.send_message(message)
            except Exception as e:
                if self._is_rate_limit_error(e):
                    print(f"DEBUG: Rate limit hit. Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                elif "Gemini provider is not available" in str(e) or "Deepseek provider is not available" in str(e):
                    print(f"DEBUG: Primary provider unavailable, trying fallback...")
                    fallback = self._get_fallback_provider()
                    if fallback:
                        session = fallback.create_chat(
                            model=model,
                            system_instruction=system_instruction,
                            temperature=temperature
                        )
                        self._chat_sessions[user_id] = (session, model)
                        return session.send_message(message)
                    raise e
                else:
                    raise e

        raise Exception("Chat message failed after max retries")

    def get_chat_history(self, user_id: str) -> List[ChatMessage]:
        if user_id in self._chat_sessions:
            session, _ = self._chat_sessions[user_id]
            return session.get_history()
        return []
