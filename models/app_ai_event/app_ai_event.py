from uuid import UUID, uuid4
from db import saveDataModel
from sqlmodel import SQLModel, Field, Column, String
from models.mixins import BaseMixin

from typing import Optional, List
from datetime import datetime

from sqlalchemy.dialects import postgresql
from ..enums import LLM, AIEventType, AIEventStatus, AIEvent


class App_AI_Event(BaseMixin, SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    app_ai_id: UUID  # the id of app_ai
    model: LLM  # the type of the model, gpt3,gpt4, claud3_opus
    temperature: float  # the temerature of the model
    event_type: AIEventType
    event: AIEvent
    event_status: AIEventStatus

    event_utc: int = Field(
        default_factory=lambda: int(datetime.now().timestamp()), nullable=False
    )
    estimated_tokens: Optional[int]
    file_source: Optional[str]
    url: Optional[str]
    messages: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )

    user_id: Optional[UUID]  # the issuer of the event IE human ai or system
    user_event_id: Optional[UUID]
    # the unique id that triggered the AI Event IE session button push etc
    # associated_ai_event_ids: Optional[List]  # any associated ai_events
    # parent_ai_event_ids: Optional[List]  # any parent ai_events
    # child_ai_event_ids: Optional[List]  # any child ai_events

    function_start_utc: Optional[int]
    response_id: Optional[str] = Field(
        default=None, description="Response ID of the model"
    )
    stop_reason: Optional[str] = Field(
        default=None, description="Reason why the model stopped"
    )
    stop_sequence: Optional[str] = Field(
        default=None, description="Sequence at which the model stopped"
    )
    input_tokens: Optional[int] = Field(
        default=0, description="Number of input tokens used"
    )
    output_tokens: Optional[int] = Field(
        default=0, description="Number of output tokens generated"
    )
    parsing_error: Optional[str] = Field(
        default=0, description="Parsing Errors Encountered"
    )

    # context_items: Optional[List[UUID]]  ## list of context_ids used
    def saveModel(self):
        saveDataModel(self)
