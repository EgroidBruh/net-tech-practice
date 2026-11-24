from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://duty:duty_dev_password@localhost:5432/duty"
    ui_timezone: str = "Asia/Yekaterinburg"

settings = Settings()
