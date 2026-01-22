"""Модели данных для системы логирования."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class LogLevel(str, Enum):
    """Уровни логирования."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogSource(str, Enum):
    """Источники событий в системе."""
    AGENT = "agent"
    SYSTEM = "system"
    UI = "ui"
    TOOL = "tool"
    VALIDATOR = "validator"
    INFRASTRUCTURE = "infrastructure"


class LogStage(str, Enum):
    """Этапы выполнения задачи."""
    PLANNING = "planning"
    RESEARCH = "research"
    CODING = "coding"
    TESTING = "testing"
    VALIDATION = "validation"
    REFLECTION = "reflection"
    INTENT = "intent"
    MEMORY = "memory"


@dataclass
class LogEvent:
    """Типизированная модель лог-события.
    
    Атрибуты:
        timestamp: Время создания события (UTC)
        level: Уровень логирования
        source: Источник события (агент, система, UI и т.п.)
        stage: Этап выполнения задачи
        message: Человекочитаемое сообщение на русском языке
        payload: Произвольные структурированные данные (не строка)
        task_id: Уникальный идентификатор задачи
        iteration: Номер итерации (опционально)
    """
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    level: LogLevel = LogLevel.INFO
    source: LogSource = LogSource.SYSTEM
    stage: Optional[LogStage] = None
    message: str = ""
    payload: Optional[Dict[str, Any]] = None
    task_id: Optional[str] = None
    iteration: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует событие в словарь для сериализации.
        
        Returns:
            Словарь с данными события
        """
        result: Dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "source": self.source.value,
            "message": self.message,
        }
        
        if self.stage is not None:
            result["stage"] = self.stage.value
        
        if self.payload is not None:
            result["payload"] = self.payload
        
        if self.task_id is not None:
            result["task_id"] = self.task_id
        
        if self.iteration is not None:
            result["iteration"] = self.iteration
        
        return result