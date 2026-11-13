from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "FastForge"
    debug: bool = False

    # Database connection string. Defaults to a local SQLite file so the app
    # runs with no external services; override via DATABASE_URL in the env.
    database_url: str = "sqlite:///./fastforge.db"

    # Secret used to sign authentication tokens. MUST be overridden in any
    # real deployment via SECRET_KEY in the environment.
    secret_key: str = "dev-insecure-change-me"


settings = Settings()
