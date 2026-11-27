from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelephonySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    telephony_token: str = "local-development-token"
    call_database: str = "/data/calls.sqlite3"
    sip_directory: str = "/directory"
    esl_host: str = "127.0.0.1"
    esl_port: int = Field(default=8021, ge=1, le=65535)
    esl_password: str = Field(default="local-esl-password", pattern=r"^[A-Za-z0-9_-]{8,128}$")
    sip_domain: str = Field(default="localhost", pattern=r"^[A-Za-z0-9.-]+$")
    originate_timeout: int = Field(default=30, ge=1, le=120)
    answered_call_duration: int = Field(default=15, ge=1, le=120)
    caller_id_number: str = Field(default="9000", pattern=r"^[0-9]{2,10}$")
