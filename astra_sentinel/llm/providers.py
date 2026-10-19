"""Minimal replaceable OpenRouter and Groq structured-output providers."""
from __future__ import annotations

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMProviderError(RuntimeError):
    """Controlled provider/network failure; never a valid goal."""


class LLMProvider(Protocol):
    def generate_structured_goal(self, prompt: str) -> str: ...


class _OpenAICompatibleProvider:
    endpoint: str

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 15.0) -> None:
        api_key = api_key.strip() if api_key else ""
        model = model.strip() if model else ""
        if not api_key:
            raise LLMProviderError("LLM API key is not configured")
        if not model:
            raise LLMProviderError("LLM model is not configured")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def generate_structured_goal(self, prompt: str) -> str:
        body = json.dumps({
            "model": self._model,
            "messages": [{"role": "system", "content": prompt}],
            "temperature": 0,
        }).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ASTRA-Sentinel",
            "X-Title": "ASTRA Sentinel",
            "User-Agent": "ASTRA-Sentinel/0.1.0",
        }
        request = Request(self.endpoint, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
        except HTTPError as error:
            detail = ""
            try:
                err_data = json.loads(error.read().decode("utf-8"))
                if isinstance(err_data, dict):
                    err_obj = err_data.get("error", err_data)
                    if isinstance(err_obj, dict):
                        detail = err_obj.get("message") or err_obj.get("detail") or str(err_obj)
                    else:
                        detail = str(err_obj)
            except Exception:
                pass
            error_msg = f"HTTP {error.code}" + (f": {detail}" if detail else f" {error.reason}")
            raise LLMProviderError(f"LLM provider error ({error_msg})") from error
        except (URLError, TimeoutError, OSError) as error:
            raise LLMProviderError(f"LLM provider is unavailable: {error}") from error
        except (KeyError, IndexError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LLMProviderError("LLM provider returned an invalid response") from error
        if not isinstance(content, str):
            raise LLMProviderError("LLM provider returned an invalid response")
        return content


class OpenRouterProvider(_OpenAICompatibleProvider):
    endpoint = "https://openrouter.ai/api/v1/chat/completions"


class GroqProvider(_OpenAICompatibleProvider):
    endpoint = "https://api.groq.com/openai/v1/chat/completions"
