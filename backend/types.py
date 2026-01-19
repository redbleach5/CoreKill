"""Типы и модели данных для backend."""
from typing import TypedDict, Optional, List, Dict, Any
from enum import Enum


class IntentType(str, Enum):
    """Типы намерений."""
    CREATE = "create"
    MODIFY = "modify"
    DEBUG = "debug"
    OPTIMIZE = "optimize"
    EXPLAIN = "explain"
    TEST = "test"
    REFACTOR = "refactor"
    GREETING = "greeting"
    HELP = "help"


class StageStatus(str, Enum):
    """Статусы этапов выполнения."""
    IDLE = "idle"
    START = "start"
    PROGRESS = "progress"
    END = "end"
    ERROR = "error"


class StageResult(TypedDict, total=False):
    """Результат выполнения этапа."""
    stage: str
    status: str
    message: str
    progress: Optional[float]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    timestamp: str


class WorkflowMetrics(TypedDict):
    """Метрики выполнения workflow."""
    planning: float
    research: float
    testing: float
    coding: float
    critic: float
    overall: float


class TaskResult(TypedDict, total=False):
    """Результат выполнения задачи."""
    task_id: str
    task: str
    intent: Dict[str, Any]
    plan: Optional[str]
    context: Optional[str]
    tests: Optional[str]
    code: Optional[str]
    validation: Optional[Dict[str, Any]]
    reflection: Optional[Dict[str, Any]]
    critic: Optional[Dict[str, Any]]
    metrics: WorkflowMetrics
    tokens_used: Optional[int]
    error: Optional[str]
    timestamp: str


class SSEEvent(TypedDict, total=False):
    """SSE событие."""
    id: str
    event: str
    data: Dict[str, Any]
    timestamp: str


class HealthCheckResponse(TypedDict):
    """Ответ health check endpoint."""
    status: str
    timestamp: str
    services: Dict[str, str]
    ollama_models: Optional[int]
    ollama_error: Optional[str]


class ModelInfo(TypedDict):
    """Информация о модели."""
    name: str
    size: Optional[int]
    modified_at: Optional[str]
    digest: Optional[str]
