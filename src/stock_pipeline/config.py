from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    polygon_api_key: str = Field(..., min_length=1)
    polygon_base_url: str = "https://api.polygon.io"
    data_dir: Path = Path("./data")

    @field_validator("data_dir", mode="before")
    @classmethod
    def resolve_data_dir(cls, value: str | Path) -> Path:
        return Path(value)

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"


def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing_key = any(error["loc"] == ("polygon_api_key",) for error in exc.errors())
        if missing_key:
            raise RuntimeError(
                "POLYGON_API_KEY is not set. Run: cp .env.example .env "
                "then add your Polygon API key to .env"
            ) from exc
        raise
