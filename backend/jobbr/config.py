from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOBBR_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./jobbr.db"
    base_path: str = "/jobbr"  # where the app is mounted (https://jckail.com/jobbr)
    static_dir: str = "../web/dist"
    api_token: str | None = None  # if set, mutating requests need X-Jobbr-Token
    seed_demo: bool = False  # load demo data when the database is empty

    anthropic_api_key: str | None = None
    model: str = "claude-haiku-4-5-20251001"
    max_input_chars: int = 60_000
    fetch_timeout_s: float = 15.0
    allow_private_fetch: bool = False  # SSRF guard; only enable in tests

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def base(self) -> str:
        b = "/" + self.base_path.strip("/")
        return "" if b == "/" else b


@lru_cache
def get_settings() -> Settings:
    return Settings()
