import os
from typing import Optional
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.providers.azure import AzureProvider
from config import settings

def get_ai_model():
    """Get the appropriate AI model based on configuration"""
    
    if settings.ai_provider == "azure":
        if not settings.azure_openai_key or not settings.azure_openai_endpoint:
            raise ValueError("Azure OpenAI configuration missing")
        
        return OpenAIChatModel(
            settings.azure_openai_deployment,
            provider=AzureProvider(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_key
            )
        )
    
    elif settings.ai_provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ValueError("OpenRouter API key missing")
        
        return OpenAIChatModel(
            settings.openrouter_model,
            provider=OpenRouterProvider(api_key=settings.openrouter_api_key)
        )
    
    elif settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key missing")
        
        return OpenAIChatModel(
            settings.openai_model,
            provider=OpenAIProvider(api_key=settings.openai_api_key)
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