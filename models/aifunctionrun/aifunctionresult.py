from datetime import datetime

from sqlmodel import Field
from uuid import UUID, uuid4

from typing import Optional

from .aifunctionrunbase import AIFunctionRunBase


class AIFunctionResult(AIFunctionRunBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)  # backpopulates u
    AIFunctionRun_id: UUID
    success: bool
    message: str
    # Adding new fields to store additional metadata
    model: Optional[str] = Field(default=None, description="The model used for the run")
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
    run_completion_utc: int = Field(
        default_factory=lambda: int(datetime.now().timestamp()), nullable=False
    )
