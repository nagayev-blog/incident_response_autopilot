from pydantic import BaseModel, Field


class ResponseOutput(BaseModel):
    immediate_actions: list[str] = Field(
        description="Немедленные шаги — что сделать прямо сейчас (3–5 пунктов)"
    )
    runbook_steps: list[str] = Field(
        description="Пошаговый runbook для устранения инцидента"
    )
    escalation: str = Field(
        description="Кого уведомить и по каким каналам"
    )
    estimated_resolution_time: str = Field(
        description="Ожидаемое время восстановления (например: 30–60 минут)"
    )
