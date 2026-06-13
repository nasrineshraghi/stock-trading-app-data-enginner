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

    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_warehouse: str | None = None
    snowflake_database: str | None = None
    snowflake_schema: str | None = None
    snowflake_table: str = "STOCK_OHLCV"
    snowflake_role: str | None = None

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

    @property
    def snowflake_configured(self) -> bool:
        required = (
            self.snowflake_account,
            self.snowflake_user,
            self.snowflake_password,
            self.snowflake_warehouse,
            self.snowflake_database,
            self.snowflake_schema,
        )
        return all(value not in (None, "") for value in required)

    def require_snowflake_settings(self) -> None:
        missing = []
        for name in (
            "snowflake_account",
            "snowflake_user",
            "snowflake_password",
            "snowflake_warehouse",
            "snowflake_database",
            "snowflake_schema",
        ):
            if not getattr(self, name):
                missing.append(name.upper())
        if missing:
            raise RuntimeError(
                "Snowflake is not fully configured. Set these in .env: "
                + ", ".join(missing)
            )


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
