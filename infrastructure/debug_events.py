"""Debug события для Phase 7: Under The Hood Visualization.

Модуль для отправки debug-событий через SSE:
- LOG: записи логов в реальном времени
- TOOL_CALL_START/END: отслеживание вызовов LLM
- METRICS_UPDATE: обновление метрик

Особенности:
- Отключаемо через config.toml [debug] under_the_hood_enabled
- Минимальное влияние на производительность
- Thread-safe
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from utils.logger import get_logger

logger = get_logger()
from functools import wraps
import asyncio

from utils.config import get_config
from utils.logger import get_logger

logger = get_logger()


class LogLevel(str, Enum):
    """Уровни логирования для UI."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class LogEntry:
    """Запись лога для отправки на frontend."""
    timestamp: str
    level: LogLevel
    stage: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Сериализует в словарь для SSE."""
        return {
            "timestamp": self.timestamp,
            "level": self.level.value,
            "stage": self.stage,
            "message": self.message,
            "details": self.details
        }


@dataclass
class ToolCall:
    """Информация о вызове инструмента/LLM."""
    id: str
    type: str  # 'llm' | 'validation' | 'search' | 'file'
    name: str
    input_preview: str
    start_time: float
    tokens_in: int = 0
    tokens_out: int = 0
    output_preview: str = ""
    status: str = "running"  # running | success | error
    duration_ms: float = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Сериализует в словарь для SSE."""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "input_preview": self.input_preview[:500],
            "output_preview": self.output_preview[:500] if self.output_preview else "",
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 1)
        }


class DebugEventEmitter:
    """Эмиттер debug-событий для Under The Hood панели.
    
    Singleton для отправки событий через SSE.
    """
    
    _instance: "DebugEventEmitter | None" = None
    _initialized: bool = False
    
    def __new__(cls) -> "DebugEventEmitter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._initialized = True
        self._enabled = False
        self._log_level = LogLevel.INFO
        self._logs: list[LogEntry] = []
        self._tool_calls: dict[str, ToolCall] = {}
        self._max_logs = 1000
        self._sse_callback: Callable[[str, dict], None] | None = None
        
        self._load_config()
    
    def _load_config(self) -> None:
        """Загружает настройки из config.toml."""
        try:
            config = get_config()
            debug_config = config._config_data.get("debug", {})
            self._enabled = debug_config.get("under_the_hood_enabled", True)
            level_str = debug_config.get("log_level", "info")
            self._log_level = LogLevel(level_str.lower())
            self._max_logs = debug_config.get("max_logs_in_memory", 1000)
        except Exception as e:
            logger.debug(f"⚠️ Ошибка загрузки конфигурации debug_events, используем дефолты: {e}")
            self._enabled = True
            self._log_level = LogLevel.INFO
    
    @property
    def enabled(self) -> bool:
        """Проверяет включена ли функция."""
        return self._enabled
    
    def set_sse_callback(self, callback: Callable[[str, dict], None]) -> None:
        """Устанавливает callback для отправки SSE событий."""
        self._sse_callback = callback
    
    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Отправляет событие через SSE."""
        if not self._enabled or not self._sse_callback:
            return
        
        try:
            self._sse_callback(event_type, data)
        except Exception as e:
            logger.debug(f"Debug event emit failed: {e}")
    
    def log(
        self,
        stage: str,
        message: str,
        level: LogLevel = LogLevel.INFO,
        details: dict[str, Any] | None = None
    ) -> None:
        """Отправляет лог-запись на frontend.
        
        Args:
            stage: Этап workflow (intent, planning, coding, etc.)
            message: Сообщение лога
            level: Уровень важности
            details: Дополнительные данные
        """
        if not self._enabled:
            return
        
        # Фильтрация по уровню
        level_order = {LogLevel.DEBUG: 0, LogLevel.INFO: 1, LogLevel.WARNING: 2, LogLevel.ERROR: 3}
        if level_order.get(level, 1) < level_order.get(self._log_level, 1):
            return
        
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            stage=stage,
            message=message,
            details=details or {}
        )
        
        # Сохраняем в память
        self._logs.append(entry)
        if len(self._logs) > self._max_logs:
            self._logs = self._logs[-self._max_logs:]
        
        # Отправляем через SSE
        self._emit("log", entry.to_dict())
    
    def tool_call_start(
        self,
        call_id: str,
        tool_type: str,
        name: str,
        input_preview: str,
        tokens_in: int = 0
    ) -> None:
        """Регистрирует начало вызова инструмента.
        
        Args:
            call_id: Уникальный ID вызова
            tool_type: Тип (llm, validation, search, file)
            name: Название инструмента/модели
            input_preview: Превью входных данных
            tokens_in: Количество входных токенов (для LLM)
        """
        if not self._enabled:
            return
        
        call = ToolCall(
            id=call_id,
            type=tool_type,
            name=name,
            input_preview=input_preview,
            start_time=time.time(),
            tokens_in=tokens_in
        )
        
        self._tool_calls[call_id] = call
        self._emit("tool_call_start", call.to_dict())
    
    def tool_call_end(
        self,
        call_id: str,
        status: str = "success",
        output_preview: str = "",
        tokens_out: int = 0
    ) -> None:
        """Регистрирует завершение вызова инструмента.
        
        Args:
            call_id: Уникальный ID вызова
            status: Статус (success, error)
            output_preview: Превью выходных данных
            tokens_out: Количество выходных токенов
        """
        if not self._enabled:
            return
        
        call = self._tool_calls.get(call_id)
        if not call:
            return
        
        call.status = status
        call.output_preview = output_preview
        call.tokens_out = tokens_out
        call.duration_ms = (time.time() - call.start_time) * 1000
        
        self._emit("tool_call_end", call.to_dict())
        
        # Очищаем старые записи
        if len(self._tool_calls) > 100:
            oldest = sorted(self._tool_calls.values(), key=lambda x: x.start_time)[:50]
            for c in oldest:
                del self._tool_calls[c.id]
    
    def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Возвращает последние логи."""
        return [log.to_dict() for log in self._logs[-limit:]]
    
    def get_active_tool_calls(self) -> list[dict[str, Any]]:
        """Возвращает активные вызовы."""
        return [
            call.to_dict() 
            for call in self._tool_calls.values() 
            if call.status == "running"
        ]
    
    def clear(self) -> None:
        """Очищает все данные."""
        self._logs.clear()
        self._tool_calls.clear()


def get_debug_emitter() -> DebugEventEmitter:
    """Возвращает singleton эмиттера debug-событий."""
    return DebugEventEmitter()


def debug_log(stage: str, message: str, level: LogLevel = LogLevel.INFO, **details: Any) -> None:
    """Shortcut для логирования в Under The Hood.
    
    Args:
        stage: Этап workflow
        message: Сообщение
        level: Уровень
        **details: Дополнительные данные
    """
    get_debug_emitter().log(stage, message, level, details if details else None)


def track_tool_call(tool_type: str, name: str):
    """Декоратор для отслеживания вызовов инструментов.
    
    Автоматически отправляет события tool_call_start и tool_call_end.
    
    Args:
        tool_type: Тип инструмента (llm, validation, search, file)
        name: Название
    
    Example:
        @track_tool_call("llm", "generate")
        async def generate(self, prompt: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            emitter = get_debug_emitter()
            if not emitter.enabled:
                return await func(*args, **kwargs)
            
            import uuid
            call_id = str(uuid.uuid4())[:8]
            
            # Формируем превью входа
            input_preview = str(kwargs.get("prompt", kwargs.get("code", str(args)[:200])))[:500]
            
            emitter.tool_call_start(call_id, tool_type, name, input_preview)
            
            try:
                result = await func(*args, **kwargs)
                output_preview = str(result)[:500] if result else ""
                emitter.tool_call_end(call_id, "success", output_preview)
                return result
            except Exception as e:
                logger.debug(f"⚠️ Ошибка в async tool call {name}: {e}")
                emitter.tool_call_end(call_id, "error", str(e))
                raise
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            emitter = get_debug_emitter()
            if not emitter.enabled:
                return func(*args, **kwargs)
            
            import uuid
            call_id = str(uuid.uuid4())[:8]
            
            input_preview = str(kwargs.get("prompt", kwargs.get("code", str(args)[:200])))[:500]
            
            emitter.tool_call_start(call_id, tool_type, name, input_preview)
            
            try:
                result = func(*args, **kwargs)
                output_preview = str(result)[:500] if result else ""
                emitter.tool_call_end(call_id, "success", output_preview)
                return result
            except Exception as e:
                logger.debug(f"⚠️ Ошибка в sync tool call {name}: {e}")
                emitter.tool_call_end(call_id, "error", str(e))
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
