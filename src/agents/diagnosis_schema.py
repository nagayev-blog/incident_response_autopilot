from pydantic import BaseModel, Field


class DiagnosisOutput(BaseModel):
    root_cause: str = Field(
        description="Вероятная первопричина инцидента (1–2 предложения)"
    )
    affected_components: list[str] = Field(
        description="Список затронутых компонентов или сервисов"
    )
    evidence: str = Field(
        description="Наблюдаемые симптомы и метрики, подтверждающие диагноз"
    )
    recommended_checks: list[str] = Field(
        description="Что проверить инженеру в первую очередь (3–5 пунктов)"
    )
