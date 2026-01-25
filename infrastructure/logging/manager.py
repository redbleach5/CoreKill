"""LogManager - единая точка входа для системы логирования."""
import sys
import threading
from typing import List, Optional

from infrastructure.logging.models import LogEvent, LogLevel, LogSource, LogStage
from infrastructure.logging.sink import LoggerSink
from infrastructure.logging.file_sink import FileLoggerSink
from infrastructure.logging.console_sink import ConsoleLoggerSink
from infrastructure.logging.memory_sink import MemoryLoggerSink
from infrastructure.logging.config import LoggingConfig


class LogManager:
    """Менеджер логирования - единая точка входа.
    
    LogManager:
    - Управляет несколькими sink-ами одновременно
    - Предоставляет удобные методы логирования
    - Фильтрует события по уровню
    - Не знает ничего о UI или FastAPI
    """
    
    def __init__(self, config: LoggingConfig) -> None:
        """Инициализация LogManager.
        
        Args:
            config: Конфигурация логирования
        """
        self.config = config
        self.sinks: List[LoggerSink] = []
        self._lock = threading.Lock()
        
        # Создаём sink-и согласно конфигурации
        self._setup_sinks()
    
    def _setup_sinks(self) -> None:
        """Настраивает sink-и согласно конфигурации."""
        if self.config.enable_file:
            try:
                file_sink = FileLoggerSink(
                    log_file=self.config.log_file,
                    max_size_mb=self.config.max_file_size_mb,
                    backup_count=self.config.file_backup_count
                )
                self.sinks.append(file_sink)
            except Exception as e:
                # Если не можем создать файловый sink, продолжаем без него
                # Используем sys.stderr так как это инфраструктурный слой
                # и сама система логирования ещё не работает
                sys.stderr.write(f"⚠️ Не удалось создать файловый sink: {e}\n")
        
        if self.config.enable_console:
            try:
                console_sink = ConsoleLoggerSink(
                    use_colors=self.config.console_colors
                )
                self.sinks.append(console_sink)
            except Exception as e:
                # Используем sys.stderr так как это инфраструктурный слой
                sys.stderr.write(f"⚠️ Не удалось создать консольный sink: {e}\n")
        
        if self.config.enable_memory:
            try:
                memory_sink = MemoryLoggerSink(
                    max_events=self.config.memory_max_events
                )
                self.sinks.append(memory_sink)
            except Exception:
                pass
    
    def _should_log(self, level: LogLevel) -> bool:
        """Проверяет, нужно ли логировать событие с данным уровнем.
        
        Args:
            level: Уровень события
            
        Returns:
            True если событие нужно залогировать
        """
        level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
        }
        return level_order.get(level, 1) >= level_order.get(self.config.level, 1)
    
    def _emit(self, event: LogEvent) -> None:
        """Отправляет событие во все sink-и.
        
        Args:
            event: Событие для логирования
        """
        if not self._should_log(event.level):
            return
        
        with self._lock:
            for sink in self.sinks:
                try:
                    sink.emit(event)
                except Exception:
                    # Игнорируем ошибки в sink-ах, чтобы не сломать приложение
                    pass
    
    def log(
        self,
        level: LogLevel,
        message: str,
        source: LogSource = LogSource.SYSTEM,
        stage: Optional[LogStage] = None,
        payload: Optional[dict] = None,
        task_id: Optional[str] = None,
        iteration: Optional[int] = None
    ) -> None:
        """Логирует событие.
        
        Args:
            level: Уровень логирования
            message: Сообщение на русском языке
            source: Источник события
            stage: Этап выполнения
            payload: Произвольные структурированные данные
            task_id: ID задачи
            iteration: Номер итерации
        """
        event = LogEvent(
            level=level,
            message=message,
            source=source,
            stage=stage,
            payload=payload,
            task_id=task_id,
            iteration=iteration
        )
        self._emit(event)
    
    def log_debug(
        self,
        message: str,
        source: LogSource = LogSource.SYSTEM,
        stage: Optional[LogStage] = None,
        payload: Optional[dict] = None,
        task_id: Optional[str] = None,
        iteration: Optional[int] = None
    ) -> None:
        """Логирует DEBUG событие."""
        self.log(
            level=LogLevel.DEBUG,
            message=message,
            source=source,
            stage=stage,
            payload=payload,
            task_id=task_id,
            iteration=iteration
        )
    
    def log_info(
        self,
        message: str,
        source: LogSource = LogSource.SYSTEM,
        stage: Optional[LogStage] = None,
        payload: Optional[dict] = None,
        task_id: Optional[str] = None,
        iteration: Optional[int] = None
    ) -> None:
        """Логирует INFO событие."""
        self.log(
            level=LogLevel.INFO,
            message=message,
            source=source,
            stage=stage,
            payload=payload,
            task_id=task_id,
            iteration=iteration
        )
    
    def log_warning(
        self,
        message: str,
        source: LogSource = LogSource.SYSTEM,
        stage: Optional[LogStage] = None,
        payload: Optional[dict] = None,
        task_id: Optional[str] = None,
        iteration: Optional[int] = None
    ) -> None:
        """Логирует WARNING событие."""
        self.log(
            level=LogLevel.WARNING,
            message=message,
            source=source,
            stage=stage,
            payload=payload,
            task_id=task_id,
            iteration=iteration
        )
    
    def log_error(
        self,
        message: str,
        source: LogSource = LogSource.SYSTEM,
        stage: Optional[LogStage] = None,
        payload: Optional[dict] = None,
        task_id: Optional[str] = None,
        iteration: Optional[int] = None,
        error: Optional[Exception] = None
    ) -> None:
        """Логирует ERROR событие.
        
        Args:
            message: Сообщение на русском языке
            source: Источник события
            stage: Этап выполнения
            payload: Произвольные структурированные данные
            task_id: ID задачи
            iteration: Номер итерации
            error: Исключение (если есть), будет добавлено в payload
        """
        error_payload = dict(payload) if payload else {}
        if error is not None:
            error_payload.update({
                "error_type": type(error).__name__,
                "error_message": str(error),
            })
            # Добавляем traceback если есть
            import traceback
            error_payload["traceback"] = traceback.format_exc()
        
        self.log(
            level=LogLevel.ERROR,
            message=message,
            source=source,
            stage=stage,
            payload=error_payload,
            task_id=task_id,
            iteration=iteration
        )
    
    def log_stage_start(
        self,
        task_id: str,
        stage: LogStage,
        message: str,
        payload: Optional[dict] = None,
        iteration: Optional[int] = None,
        source: LogSource = LogSource.AGENT
    ) -> None:
        """Логирует начало этапа выполнения задачи.
        
        Args:
            task_id: ID задачи
            stage: Этап выполнения
            message: Сообщение на русском языке
            payload: Произвольные структурированные данные
            iteration: Номер итерации
            source: Источник события
        """
        self.log_info(
            message=message,
            source=source,
            stage=stage,
            payload=payload or {},
            task_id=task_id,
            iteration=iteration
        )
    
    def log_stage_end(
        self,
        task_id: str,
        stage: LogStage,
        message: str,
        payload: Optional[dict] = None,
        iteration: Optional[int] = None,
        source: LogSource = LogSource.AGENT
    ) -> None:
        """Логирует завершение этапа выполнения задачи.
        
        Args:
            task_id: ID задачи
            stage: Этап выполнения
            message: Сообщение на русском языке
            payload: Произвольные структурированные данные
            iteration: Номер итерации
            source: Источник события
        """
        self.log_info(
            message=message,
            source=source,
            stage=stage,
            payload=payload or {},
            task_id=task_id,
            iteration=iteration
        )
    
    def get_memory_sink(self) -> Optional[MemoryLoggerSink]:
        """Получает MemoryLoggerSink если он включён.
        
        Returns:
            MemoryLoggerSink или None если не включён
        """
        with self._lock:
            for sink in self.sinks:
                if isinstance(sink, MemoryLoggerSink):
                    return sink
        return None
    
    def flush(self) -> None:
        """Сбрасывает буферы всех sink-ов."""
        with self._lock:
            for sink in self.sinks:
                try:
                    sink.flush()
                except Exception:
                    pass
    
    def close(self) -> None:
        """Закрывает все sink-и."""
        with self._lock:
            for sink in self.sinks:
                try:
                    sink.close()
                except Exception:
                    pass
            self.sinks.clear()
    
    def __enter__(self) -> 'LogManager':
        """Поддержка контекстного менеджера."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Автоматическое закрытие при выходе из контекста."""
        self.close()