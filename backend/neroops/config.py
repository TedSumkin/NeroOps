from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NEROOPS_",
        extra="ignore",
    )

    app_name: str = "NeroOps"
    data_dir: Path = Path("./data")
    timezone: str = "Europe/Moscow"
    cors_origins: str = "http://localhost:5173"

    @property
    def database_url(self) -> str:
        database_path = (self.data_dir / "neroops.sqlite3").resolve()
        return f"sqlite:///{database_path}"

    @property
    def attachment_dir(self) -> Path:
        return self.data_dir / "attachments"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def prepare_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.attachment_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.prepare_directories()
    return settings
