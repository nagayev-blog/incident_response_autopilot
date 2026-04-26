from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=True)  # перезаписываем os.environ из .env, включая пустые shell-переменные


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"   # override из .env для быстрых экспериментов
    triage_model: str = "claude-haiku-4-5"
    agent_model: str = "claude-sonnet-4-5"
    max_tokens: int = 2048

    # LangSmith
    langsmith_api_key: str = ""
    langsmith_project: str = "incident-response-autopilot"
    langsmith_tracing: bool = False

    # ChromaDB
    chroma_db_path: str = "./data/chroma_db"
    rag_top_k: int = 5

    # Timeouts / retries
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3


settings = Settings()
