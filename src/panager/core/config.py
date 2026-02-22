from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Discord
    discord_token: str

    # LLM
    llm_base_url: str
    llm_api_key: str
    llm_model: str = "minimax-m2.5-free"

    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int = 5432

    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    # 로그
    log_file_path: str
    log_max_bytes: int = 10_485_760
    log_backup_count: int = 5

    # Checkpoint
    checkpoint_max_tokens: int = 4000  # LLM에 전달할 messages 최대 토큰 수
    checkpoint_ttl_days: int = 30  # checkpoint 보관 기간 (일)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn_asyncpg(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
