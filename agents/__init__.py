"""Агенты для многоагентной системы генерации кода.

Включает синхронные и стриминговые версии агентов.
Стриминговые версии (Streaming*) поддерживают real-time вывод <think> блоков
reasoning моделей и возможность прерывания.
"""
from agents.intent import IntentAgent, IntentResult
from agents.chat import ChatAgent, get_chat_agent
from agents.conversation import ConversationMemory, get_conversation_memory

# Синхронные агенты
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.test_generator import TestGeneratorAgent
from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from agents.reflection import ReflectionAgent
from agents.critic import CriticAgent
from agents.memory import MemoryAgent

# Стриминговые агенты (с поддержкой <think> блоков)
from agents.streaming_planner import StreamingPlannerAgent, get_streaming_planner_agent
from agents.streaming_test_generator import StreamingTestGeneratorAgent, get_streaming_test_generator_agent
from agents.streaming_coder import StreamingCoderAgent, get_streaming_coder_agent
from agents.streaming_debugger import StreamingDebuggerAgent, get_streaming_debugger_agent
from agents.streaming_reflection import StreamingReflectionAgent, get_streaming_reflection_agent
from agents.streaming_critic import StreamingCriticAgent, get_streaming_critic_agent

__all__ = [
    # Core
    "IntentAgent",
    "IntentResult",
    "ChatAgent",
    "get_chat_agent",
    "ConversationMemory",
    "get_conversation_memory",
    "MemoryAgent",
    
    # Синхронные агенты
    "PlannerAgent",
    "ResearcherAgent",
    "TestGeneratorAgent",
    "CoderAgent",
    "DebuggerAgent",
    "ReflectionAgent",
    "CriticAgent",
    
    # Стриминговые агенты
    "StreamingPlannerAgent",
    "get_streaming_planner_agent",
    "StreamingTestGeneratorAgent",
    "get_streaming_test_generator_agent",
    "StreamingCoderAgent",
    "get_streaming_coder_agent",
    "StreamingDebuggerAgent",
    "get_streaming_debugger_agent",
    "StreamingReflectionAgent",
    "get_streaming_reflection_agent",
    "StreamingCriticAgent",
    "get_streaming_critic_agent",
]
