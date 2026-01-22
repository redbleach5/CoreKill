"""State схема для LangGraph workflow."""
from typing import TypedDict, Optional, Dict, Any, List
from agents.intent import IntentResult
from agents.debugger import DebugResult
from agents.reflection import ReflectionResult
from agents.critic import CriticReport


class AgentState(TypedDict):
    """State для LangGraph workflow агентов.
    
    Содержит все данные, которые передаются между узлами графа.
    """
    # Входные данные
    task: str  # Исходная задача пользователя
    max_iterations: int  # Максимальное количество итераций self-healing
    disable_web_search: bool  # Отключить веб-поиск
    model: Optional[str]  # Модель Ollама (если None, выбирается автоматически)
    temperature: float  # Температура генерации
    
    # Режим и диалог
    interaction_mode: str  # Режим: auto, chat, plan, analyze, code
    conversation_id: Optional[str]  # ID диалога для сохранения контекста
    conversation_history: Optional[List[Dict[str, str]]]  # История для LLM [{role, content}]
    chat_response: Optional[str]  # Ответ в режиме chat (без workflow)
    
    # Codebase indexing
    project_path: Optional[str]  # Путь к проекту для индексации кодовой базы
    file_extensions: Optional[List[str]]  # Расширения файлов для индексации (по умолчанию ['.py'])
    
    # Результаты агентов
    intent_result: Optional[IntentResult]  # Результат Intent агента
    plan: str  # План от Planner
    context: str  # Контекст от Researcher
    tests: str  # Тесты от TestGenerator
    code: str  # Код от Coder
    validation_results: Dict[str, Any]  # Результаты валидации
    debug_result: Optional[DebugResult]  # Результат Debugger
    reflection_result: Optional[ReflectionResult]  # Результат Reflection
    critic_report: Optional[CriticReport]  # Результат Critic агента
    
    # Метаданные workflow
    iteration: int  # Счетчик итераций self-healing
    task_id: str  # ID задачи для отслеживания
    enable_sse: bool  # Флаг для включения SSE стриминга (SSEManager - статический класс)
    
    # SSE события для стриминга (используется когда use_streaming_agents = true)
    # DEPRECATED: Используйте event_references вместо sse_events
    sse_events: Optional[List[str]]  # Список SSE событий для отправки (thinking, code_chunk, etc.)
    
    # Ссылки на события в EventStore (для оптимизации памяти)
    event_references: Optional[List[str]]  # Список ID событий в EventStore
    
    # Дополнительные данные
    file_path: Optional[str]  # Путь к файлу для modify/debug режима
    file_context: Optional[str]  # Контекст файла для modify/debug
