from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Mapping Platform"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql://smart_mapping_user:dev_password_123@localhost:5432/smart_mapping",
        description="Database connection URL"
    )
    
    # Ollama Configuration
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL"
    )
    OLLAMA_MODEL: str = "llama3.2"
    
    # Qdrant Configuration
    QDRANT_HOST: str = Field(
        default="localhost",  
        description="Qdrant host"
    )
    QDRANT_PORT: int = Field(
        default=6333,
        description="Qdrant port"
    )
    
    # JWT
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    
    # File Upload
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024

    # Pipeline auto-consumption — how often (seconds) the background
    # scheduler polls each active Consommation pipeline's Config IN
    PIPELINE_POLL_INTERVAL_SECONDS: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()