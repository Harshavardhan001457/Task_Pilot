import os
import pytest
from astra_sentinel.llm import (
    GroqProvider,
    LLMProviderError,
    LLMSettings,
    OpenRouterProvider,
    create_provider,
    load_dotenv,
)


def test_load_dotenv_reads_file_into_environ(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    monkeypatch.delenv("TEST_QUOTED", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Comment\n"
        "TEST_KEY=hello_world\n"
        "export TEST_QUOTED=\"sample value\"\n"
        "EMPTY_LINE=\n",
        encoding="utf-8",
    )

    load_dotenv(env_file)
    assert os.environ.get("TEST_KEY") == "hello_world"
    assert os.environ.get("TEST_QUOTED") == "sample value"


def test_llm_settings_from_env_file_openrouter(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PROVIDER=openrouter\n"
        "OPENROUTER_API_KEY=sk-or-test123\n"
        "OPENROUTER_MODEL=inclusionai/ling-3.0-flash-vl\n",
        encoding="utf-8",
    )

    settings = LLMSettings.from_environment(env_file)
    assert settings.provider == "openrouter"
    assert settings.api_key == "sk-or-test123"
    assert settings.model == "inclusionai/ling-3.0-flash-vl"

    provider = create_provider(settings)
    assert isinstance(provider, OpenRouterProvider)


def test_llm_settings_from_env_file_groq(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PROVIDER=groq\n"
        "GROQ_API_KEY=gsk-test456\n"
        "GROQ_MODEL=llama-3.3-70b-versatile\n",
        encoding="utf-8",
    )

    settings = LLMSettings.from_environment(env_file)
    assert settings.provider == "groq"
    assert settings.api_key == "gsk-test456"
    assert settings.model == "llama-3.3-70b-versatile"

    provider = create_provider(settings)
    assert isinstance(provider, GroqProvider)


def test_llm_settings_missing_provider_raises_error(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(LLMProviderError):
        LLMSettings.from_environment("/nonexistent/.env")
