from pydantic import BaseModel, Field


class PostmortemOutput(BaseModel):
    title: str = Field(description="Краткое название инцидента")
    impact: str = Field(description="Описание влияния на пользователей и бизнес")
    root_cause: str = Field(description="Подтверждённая первопричина")
    timeline: list[str] = Field(description="Хронология ключевых событий инцидента")
    resolution: str = Field(description="Как был устранён инцидент")
    action_items: list[str] = Field(description="Задачи для предотвращения повторения (с ответственным)")
