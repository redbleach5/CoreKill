"""Агенты для многоагентной системы генерации кода."""
from agents.intent import IntentAgent, IntentResult
from agents.chat import ChatAgent, get_chat_agent
from agents.conversation import ConversationMemory, get_conversation_memory
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.test_generator import TestGeneratorAgent
from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from agents.reflection import ReflectionAgent
from agents.critic import CriticAgent
from agents.memory import MemoryAgent

__all__ = [
    "IntentAgent",
    "IntentResult",
    "ChatAgent",
    "get_chat_agent",
    "ConversationMemory",
    "get_conversation_memory",
    "PlannerAgent",
    "ResearcherAgent",
    "TestGeneratorAgent",
    "CoderAgent",
    "DebuggerAgent",
    "ReflectionAgent",
    "CriticAgent",
    "MemoryAgent"
]
