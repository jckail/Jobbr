"""Strict bounded extension protocol, with no client-supplied grant authority."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .schemas import JobCreate

Opaque = Annotated[str, Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")]
ExtensionID = Annotated[str, Field(min_length=32, max_length=32, pattern=r"^[a-p]{32}$")]


class PairingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extension_id: ExtensionID
    challenge: Opaque
    challenge_method: Literal["S256"]


class ApproveIn(PairingIn):
    model_config = ConfigDict(extra="forbid")
    challenge_method: Literal["S256"]
    ai_provider: Literal["openai", "anthropic"]
    ai_model: str = Field(min_length=1, max_length=200)
    llm_enabled: bool


class ExchangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extension_id: ExtensionID
    challenge: Opaque
    verifier: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9._~-]+$")


class CaptureIn(JobCreate):
    model_config = ConfigDict(extra="forbid")
    company: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=500)
