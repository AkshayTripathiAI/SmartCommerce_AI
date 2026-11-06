from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App
    app_name: str = "SmartCommerce AI"
    debug: bool = False
    
    # Database
    database_url: str
    database_url_sync: str = ""
    
    # Redis (optional). Leave empty to use in-process caching and chat memory.
    redis_url: str = ""
    
    # Qdrant. Use ":memory:" to run an in-process index that is rebuilt on startup.
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    
    # Demo / free-tier hosting
    auto_bootstrap: bool = False  # seed DB + build vector index on startup when empty
    chat_rate_limit_per_hour: int = 30  # per user, 0 disables
    chat_daily_limit: int = 500  # whole app, protects the LLM quota; 0 disables
    
    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    
    # Google Gemini
    google_api_key: str = ""
    
    # CORS
    cors_origins: str = '["http://localhost:3000"]'
    
    @property
    def cors_origins_list(self) -> List[str]:
        value = self.cors_origins.strip()
        if value.startswith("["):
            return json.loads(value)
        return [o.strip() for o in value.split(",") if o.strip()]
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
