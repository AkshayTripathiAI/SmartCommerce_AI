"""AI module configuration."""
from pydantic_settings import BaseSettings


class AISettings(BaseSettings):
    """AI-specific settings."""
    
    # Google Gemini
    google_api_key: str = ""
    embedding_model: str = "models/gemini-embedding-001"
    embedding_dimensions: int = 768  # truncated via output_dimensionality
    chat_model: str = "gemini-3.5-flash-lite"
    
    # Provider Selection
    ai_provider: str = "gemini"  # "gemini" or "ollama"
    
    # Ollama Settings
    ollama_base_url: str = "http://host.docker.internal:11434/v1"  # Access host's Ollama from container
    ollama_model: str = "llama3.2"
    
    # Qdrant
    qdrant_url: str = "http://localhost:6333"  # or ":memory:" for an in-process index
    qdrant_api_key: str = ""
    qdrant_collection_products: str = "products"
    qdrant_collection_policies: str = "policies"
    
    class Config:
        env_file = ".env"
        extra = "ignore"
        case_sensitive = False


ai_settings = AISettings()
