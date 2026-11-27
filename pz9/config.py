from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://duty:duty_dev_password@localhost:5432/duty"
    ui_timezone: str = "Asia/Yekaterinburg"
    telephony_url: str = "http://localhost:8001"
    telephony_token: str = "local-development-token"
    notification_poll_interval: float = 1.0
    telephony_http_timeout: float = 5.0

settings = Settings()
