from pydantic import BaseModel, Field


class SuggestionOutput(BaseModel):
    summary: str = Field(description="Краткое описание ситуации (1–2 предложения)")
    recommendations: list[str] = Field(description="Рекомендации: что сделать до эскалации (3–5 пунктов)")
    priority: str = Field(description="Приоритет обработки: можно в рабочее время / до конца дня / в течение недели")
