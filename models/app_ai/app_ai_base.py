from sqlmodel import SQLModel
from models.mixins import BaseMixin
from ..enums import LLM
from typing import Optional
from uuid import UUID


class App_AI_Base(BaseMixin, SQLModel):

    model: LLM
    temperature: float  # the temerature of the model
    user_id: Optional[UUID] = None  # the creator of the ai
    ai_context_id: Optional[UUID] = None  ## the uuid of the context object created
