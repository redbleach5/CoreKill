"""State схема для LangGraph workflow."""
from typing import TypedDict, Optional, Dict, Any
from agents.intent import IntentResult
from agents.debugger import DebugResult
from agents.reflection import ReflectionResult


class AgentState(TypedDict):
    """State для LangGraph workflow агентов.
    
    Содержит все данные, которые передаются между узлами графа.
    """
    # Входные данные
    task: str  # Исходная задача пользователя
    max_iterations: int  # Максимальное количество итераций self-healing
    disable_web_search: bool  # Отключить веб-поиск
    model: Optional[str]  # Модель Ollama (если None, выбирается автоматически)
    temperature: float  # Температура генерации
    
    # Результаты агентов
    intent_result: Optional[IntentResult]  # Результат Intent агента
    plan: str  # План от Planner
    context: str  # Контекст от Researcher
    tests: str  # Тесты от TestGenerator
    code: str  # Код от Coder
    validation_results: Dict[str, Any]  # Результаты валидации
    debug_result: Optional[DebugResult]  # Результат Debugger
    reflection_result: Optional[ReflectionResult]  # Результат Reflection
    
    # Метаданные workflow
    iteration: int  # Счетчик итераций self-healing
    task_id: str  # ID задачи для отслеживания
    enable_sse: bool  # Флаг для включения SSE стриминга (SSEManager - статический класс)
    
    # Дополнительные данные
    file_path: Optional[str]  # Путь к файлу для modify/debug режима
    file_context: Optional[str]  # Контекст файла для modify/debug
