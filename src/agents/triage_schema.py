from typing import Literal

from pydantic import BaseModel, Field


class TriageOutput(BaseModel):
    severity: Literal["CRITICAL", "HIGH", "LOW"] = Field(
        description="Уровень серьёзности инцидента"
    )
    incident_type: Literal["performance", "availability", "data"] = Field(
        description="Тип инцидента"
    )
    reasoning: str = Field(
        description="Краткое объяснение классификации (1–2 предложения)"
    )
