from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str
    environment: str = "development"
    log_level: str = "debug"
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_verify_token: str = "saludcopilot_verify"
    llm_api_key: str = ""
    cors_allowed_origins: str = "http://localhost:3000"
    bot_base_url: str = "http://localhost:8001"
    internal_bot_token: str = "saludcopilot-internal-token-change-in-prod"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
