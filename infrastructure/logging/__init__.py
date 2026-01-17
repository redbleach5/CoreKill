"""Инфраструктурный слой логирования для multi-agent системы.

Система логирования предоставляет:
- Структурированные события (event-based logging)
- Независимые sink-и (файл, консоль, память)
- Единую точку входа через LogManager
- Подготовку к UI/стримингу через подписки
"""
from infrastructure.logging.models import LogEvent, LogLevel, LogSource, LogStage
from infrastructure.logging.sink import LoggerSink
from infrastructure.logging.file_sink import FileLoggerSink
from infrastructure.logging.console_sink import ConsoleLoggerSink
from infrastructure.logging.memory_sink import MemoryLoggerSink
from infrastructure.logging.manager import LogManager
from infrastructure.logging.config import LoggingConfig
from infrastructure.logging.stream_adapter import LogStreamAdapter, create_sse_event

__all__ = [
    "LogEvent",
    "LogLevel",
    "LogSource",
    "LogStage",
    "LoggerSink",
    "FileLoggerSink",
    "ConsoleLoggerSink",
    "MemoryLoggerSink",
    "LogManager",
    "LoggingConfig",
    "LogStreamAdapter",
    "create_sse_event",
]