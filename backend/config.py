import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # AI Provider Configuration
    ai_provider: str = os.getenv("AI_PROVIDER", "azure")
    
    # Azure Configuration
    azure_openai_key: Optional[str] = os.getenv("AZURE_OPENAI_KEY")
    azure_openai_endpoint: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    # OpenRouter Configuration
    openrouter_api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    # Anthropic Configuration
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    
    # MCP Configuration
    mcp_http_url: Optional[str] = os.getenv("MCP_HTTP_URL")
    mcp_http_api_key: Optional[str] = os.getenv("MCP_HTTP_API_KEY")
    
    # Redis Configuration
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Application Configuration
    app_host: str = os.getenv("APP_HOST", "ai.yourcompany.com")
    app_secret: str = os.getenv("APP_SECRET", "change-this-secret-in-production")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"

settings = Settings()