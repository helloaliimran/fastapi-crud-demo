from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    database_url: str
    openrouter_api_key: str
    openrouter_base_url: str
    zedex_api_base_url: str = "http://localhost:61815/api"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


settings = Settings()
