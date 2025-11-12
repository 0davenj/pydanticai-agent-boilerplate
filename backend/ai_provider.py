import os
from typing import Optional
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel
from config import settings

def get_ai_model():
    """Get the appropriate AI model based on configuration"""
    
    if settings.ai_provider == "azure":
        if not settings.azure_openai_key or not settings.azure_openai_endpoint:
            raise ValueError("Azure OpenAI configuration missing")
        
        return OpenAIModel(
            settings.azure_openai_deployment,
            api_key=settings.azure_openai_key,
            base_url=f"{settings.azure_openai_endpoint}/openai/deployments/{settings.azure_openai_deployment}",
            api_type="azure"
        )
    
    elif settings.ai_provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ValueError("OpenRouter API key missing")
        
        return OpenAIModel(
            settings.openrouter_model,
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1"
        )
    
    elif settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key missing")
        
        return OpenAIModel(
            settings.openai_model,
            api_key=settings.openai_api_key
        )
    
    elif settings.ai_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key missing")
        
        return AnthropicModel(
            settings.anthropic_model,
            api_key=settings.anthropic_api_key
        )
    
    else:
        raise ValueError(f"Unsupported AI provider: {settings.ai_provider}")

def create_agent(system_prompt: str = "You are a helpful AI assistant."):
    """Create an AI agent with the configured model"""
    model = get_ai_model()
    return Agent(model=model, system_prompt=system_prompt)