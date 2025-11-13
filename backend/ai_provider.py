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
            provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
            temperature=0.7,  # Lower temperature to reduce repetition
            max_tokens=2000   # Limit response length
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

def create_agent(system_prompt: str = None):
    """Create an AI agent with the configured model"""
    model = get_ai_model()
    
    microsoft_expert_prompt = """
You are a Microsoft Expert AI Assistant with deep knowledge of Microsoft products, services, and documentation.

Your role:
1. Provide accurate, detailed information about Microsoft technologies
2. Always include relevant documentation links and references in your responses
3. When you use MCP tools to search Microsoft documentation, incorporate the found links and references into your answer
4. Format your responses in Markdown for better readability
5. Cite sources using proper Markdown link syntax: [link text](url)
6. If you search documentation and find relevant articles, always include them with brief descriptions

Example format:
"Based on the Microsoft documentation, here's what you need to know:

## Key Points
- Point 1 with [relevant link](https://example.com)
- Point 2 with [another link](https://example.com)

## References
- [Article Title](https://example.com) - Brief description
- [Another Article](https://example.com) - Brief description
"""
    
    return Agent(
        model=model,
        system_prompt=system_prompt or microsoft_expert_prompt
    )