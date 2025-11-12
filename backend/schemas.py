from pydantic import BaseModel, field_validator
from typing import Optional

class ChatMessage(BaseModel):
    message: str
    session_id: str
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Message cannot be empty')
        if len(v) > 10000:  # Reasonable limit
            raise ValueError('Message too long (max 10000 characters)')
        return v.strip()
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Session ID cannot be empty')
        return v.strip()

class AuthResponse(BaseModel):
    session_id: str
    message: str = "Authentication successful"

class HealthResponse(BaseModel):
    status: str
    redis: str
    mcp: str
    ai_provider: str

class ErrorResponse(BaseModel):
    error: str
    message: str