"""Pydantic модели для структурированных ответов агентов.

Этот модуль содержит типизированные модели для гарантированного
формата ответов от LLM через JSON Schema валидацию.
"""
from models.agent_responses import (
    # Intent
    IntentType,
    IntentResponse,
    
    # Plan
    PlanStep,
    PlanResponse,
    
    # Debug
    ErrorType,
    DebugResponse,
    
    # Critic
    IssueSeverity,
    CodeIssue,
    CriticResponse,
    
    # Reflection
    ReflectionResponse,
    
    # Analyze
    ProjectStructure,
    AnalyzeResponse,
)

__all__ = [
    # Intent
    "IntentType",
    "IntentResponse",
    
    # Plan
    "PlanStep",
    "PlanResponse",
    
    # Debug
    "ErrorType",
    "DebugResponse",
    
    # Critic
    "IssueSeverity",
    "CodeIssue",
    "CriticResponse",
    
    # Reflection
    "ReflectionResponse",
    
    # Analyze
    "ProjectStructure",
    "AnalyzeResponse",
]
