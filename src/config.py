import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=True)  # перезаписываем os.environ из .env, включая пустые shell-переменные


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"  # legacy, оставлен для совместимости с .env
    triage_model: str = "claude-haiku-4-5"
    agent_model: str = "claude-haiku-4-5"
    triage_temperature: float = 0.3
    agent_temperature: float = 0.4
    max_tokens: int = 2048

    # LangSmith
    langsmith_api_key: str = ""
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_project: str = "incident-autopilot"
    langsmith_tracing: bool = False

    # ChromaDB
    chroma_db_path: str = "./data/chroma_db"
    chroma_collection_name: str = "knowledge_base"
    rag_top_k: int = 5
    rag_min_chunk_len: int = 80

    # Timeouts / retries
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3


settings = Settings()

# Прокидываем LangSmith-переменные в окружение — LangGraph читает их напрямую из os.environ
if settings.langsmith_tracing and settings.langsmith_api_key:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_ENDPOINT", settings.langsmith_endpoint)
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
