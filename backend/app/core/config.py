import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Contract & Invoice Leakage Finder"
    ENVIRONMENT: str = Field(default="development")
    API_V1_STR: str = "/v1"
    
    # Absolute path to disk database (zero in-memory reliance)
    DATABASE_URL: str = Field(
        default=f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../leakage_finder.db')).replace(chr(92), '/')}"
    )
    
    # Security
    SECRET_KEY: str = Field(default="dev-super-secret-key-change-in-production-1234567890")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # LLM / AI Configuration (Gemini API or OpenAI API)
    LLM_PROVIDER: str = Field(default="gemini")  # "gemini" or "openai"
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Storage
    STORAGE_BACKEND: str = Field(default="local")  # "local" or "gcs"
    LOCAL_STORAGE_DIR: str = Field(default="./storage/uploads")
    LOCAL_EXPORT_DIR: str = Field(default="./storage/exports")
    GCS_BUCKET_NAME: str = Field(default="")
    MAX_FILE_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "csv", "xlsx", "xls"]
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "*"
    ]

    class Config:
        env_file = (
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.env")),
            ".env"
        )
        extra = "ignore"

settings = Settings()

