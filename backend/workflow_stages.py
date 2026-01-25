"""Enum для этапов workflow.

Убирает магические строки и улучшает типизацию.
"""
from enum import Enum


class WorkflowStage(str, Enum):
    """Этапы workflow графа."""
    
    INTENT = "intent"
    PLANNING = "planning"
    RESEARCH = "research"
    TESTING = "testing"
    CODING = "coding"
    VALIDATION = "validation"
    DEBUG = "debug"
    FIXING = "fixing"
    REFLECTION = "reflection"
    CRITIC = "critic"
    RESUME = "resume"
    
    @classmethod
    def from_node_name(cls, node_name: str) -> "WorkflowStage":
        """Преобразует имя нода в WorkflowStage.
        
        Args:
            node_name: Имя нода из графа (например, "planner", "coder")
            
        Returns:
            Соответствующий WorkflowStage
        """
        mapping = {
            "intent": cls.INTENT,
            "planner": cls.PLANNING,
            "researcher": cls.RESEARCH,
            "test_generator": cls.TESTING,
            "coder": cls.CODING,
            "validator": cls.VALIDATION,
            "debugger": cls.DEBUG,
            "fixer": cls.FIXING,
            "reflection": cls.REFLECTION,
            "critic": cls.CRITIC,
        }
        return mapping.get(node_name, cls.INTENT)  # Fallback на INTENT
