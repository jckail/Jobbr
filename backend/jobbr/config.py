from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOBBR_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./jobbr.db"
    base_path: str = "/jobbr"  # where the app is mounted (https://jckail.com/jobbr)
    static_dir: str = "../web/dist"
    api_token: str | None = None  # if set, mutating requests need X-Jobbr-Token
    private_instance: bool = False
    seed_demo: bool = False  # load demo data when the database is empty

    openai_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("JOBBR_OPENAI_API_KEY", "OPENAI_API_KEY")
    )
    model: str = "gpt-4.1-mini"
    ai_timeout_s: float = Field(default=45.0, gt=0, le=120)
    ai_max_turns: int = Field(default=2, ge=1, le=5)
    ai_max_output_tokens: int = Field(default=3000, ge=256, le=8000)
    max_input_chars: int = Field(default=60_000, ge=1000, le=200_000)
    fetch_timeout_s: float = Field(default=15.0, gt=0, le=60)
    allow_private_fetch: bool = False  # SSRF guard; only enable in tests

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.strip())

    @property
    def base(self) -> str:
        b = "/" + self.base_path.strip("/")
        return "" if b == "/" else b


@lru_cache
def get_settings() -> Settings:
    return Settings()
