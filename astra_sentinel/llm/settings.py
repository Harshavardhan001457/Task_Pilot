"""External, secret-free configuration for the selected LLM provider."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from astra_sentinel.llm.providers import GroqProvider, LLMProvider, LLMProviderError, OpenRouterProvider


def load_dotenv(dotenv_path: str | Path | None = None, *, override: bool = True) -> None:
    """Load environment variables from a .env file into os.environ.

    Searches current working directory, project root, and ancestor directories.
    """
    target: Path | None = None
    if dotenv_path is not None:
        target = Path(dotenv_path)
    else:
        current = Path.cwd().resolve()
        for folder in [current, *current.parents]:
            candidate = folder / ".env"
            if candidate.is_file():
                target = candidate
                break
        if target is None:
            pkg_root = Path(__file__).resolve().parent.parent.parent
            candidate = pkg_root / ".env"
            if candidate.is_file():
                target = candidate

    if target is None or not target.is_file():
        return

    try:
        with open(target, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                if override or key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


@dataclass(frozen=True, slots=True)
class LLMSettings:
    provider: str
    api_key: str
    model: str

    @classmethod
    def from_environment(cls, dotenv_path: str | Path | None = None, *, override: bool = True) -> "LLMSettings":
        load_dotenv(dotenv_path, override=override)
        provider = os.environ.get("LLM_PROVIDER", "").strip().casefold()
        if not provider:
            if os.environ.get("OPENROUTER_API_KEY"):
                provider = "openrouter"
            elif os.environ.get("GROQ_API_KEY"):
                provider = "groq"

        if provider == "openrouter":
            api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
            model = os.environ.get("OPENROUTER_MODEL", "").strip() or "openai/gpt-4o-mini"
            return cls(provider, api_key, model)
        if provider == "groq":
            api_key = os.environ.get("GROQ_API_KEY", "").strip()
            model = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile"
            return cls(provider, api_key, model)
        raise LLMProviderError("LLM provider must be configured as 'openrouter' or 'groq' in .env or environment")


def create_provider(settings: LLMSettings) -> LLMProvider:
    if settings.provider == "openrouter":
        return OpenRouterProvider(settings.api_key, settings.model)
    if settings.provider == "groq":
        return GroqProvider(settings.api_key, settings.model)
    raise LLMProviderError(f"Unsupported LLM provider: {settings.provider}")
