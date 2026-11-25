from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'yida.db').as_posix()}"
    upload_dir: Path = BACKEND_DIR / "data" / "uploads"
    max_image_bytes: int = 10 * 1024 * 1024
    wardrobe_ai_provider: str = "disabled"

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
