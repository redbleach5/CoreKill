"""Адаптер для стриминга событий в UI (SSE / WebSocket).

Адаптер позволяет подписаться на события LogManager и получать поток LogEvent
для SSE или WebSocket, не встраивая FastAPI внутрь логгера.
"""
import asyncio
import queue
import threading
from typing import AsyncGenerator, Optional, Callable

from infrastructure.logging.models import LogEvent
from infrastructure.logging.manager import LogManager
from infrastructure.logging.memory_sink import MemoryLoggerSink


class LogStreamAdapter:
    """Адаптер для стриминга событий логов.
    
    Адаптер:
    - Подписывается на MemoryLoggerSink через callback
    - Буферизует события в очереди
    - Предоставляет async генератор для SSE/WebSocket
    - Не зависит от FastAPI или конкретного транспорта
    """
    
    def __init__(self, log_manager: LogManager) -> None:
        """Инициализация адаптера.
        
        Args:
            log_manager: Менеджер логирования
        """
        self.log_manager = log_manager
        self._event_queue: queue.Queue[Optional[LogEvent]] = queue.Queue()
        self._is_active = False
        self._callback: Optional[Callable[[LogEvent], None]] = None
        
        # Получаем MemoryLoggerSink и подписываемся
        memory_sink = log_manager.get_memory_sink()
        if memory_sink is not None:
            self._callback = self._on_event
            memory_sink.subscribe(self._callback)
            self._is_active = True
        else:
            raise ValueError(
                "MemoryLoggerSink не включён в LogManager. "
                "Используйте LoggingConfig с enable_memory=True"
            )
    
    def _on_event(self, event: LogEvent) -> None:
        """Callback для обработки нового события.
        
        Args:
            event: Новое событие
        """
        if self._is_active:
            try:
                self._event_queue.put_nowait(event)
            except queue.Full:
                # Если очередь переполнена, пропускаем старое событие
                try:
                    self._event_queue.get_nowait()
                    self._event_queue.put_nowait(event)
                except queue.Empty:
                    pass
    
    async def stream_events(
        self,
        task_id: Optional[str] = None,
        level: Optional[str] = None,
        source: Optional[str] = None,
        stage: Optional[str] = None
    ) -> AsyncGenerator[LogEvent, None]:
        """Генерирует поток событий с фильтрацией.
        
        Args:
            task_id: Фильтр по ID задачи
            level: Фильтр по уровню
            source: Фильтр по источнику
            stage: Фильтр по этапу
            
        Yields:
            Отфильтрованные события
        """
        # Отправляем исторические события из MemoryLoggerSink
        memory_sink = self.log_manager.get_memory_sink()
        if memory_sink is not None:
            historical_events = memory_sink.get_events(
                level=level,
                source=source,
                stage=stage,
                task_id=task_id,
                limit=100  # Последние 100 событий
            )
            for event in historical_events:
                yield event
        
        # Отправляем новые события в реальном времени
        while self._is_active:
            try:
                # Ждём событие с таймаутом для проверки активности
                event = await asyncio.to_thread(
                    self._event_queue.get,  # type: ignore[arg-type]
                    timeout=1.0
                )
                
                # Применяем фильтры
                if event is None:  # Sentinel для остановки
                    break
                
                if task_id and event.task_id != task_id:
                    continue
                if level and event.level.value != level:
                    continue
                if source and event.source.value != source:
                    continue
                if stage and (not event.stage or event.stage.value != stage):
                    continue
                
                yield event
                
            except queue.Empty:
                # Таймаут - продолжаем ждать
                continue
            except asyncio.CancelledError:
                break
    
    def stop(self) -> None:
        """Останавливает стриминг событий."""
        self._is_active = False
        
        # Отписываемся от MemoryLoggerSink
        memory_sink = self.log_manager.get_memory_sink()
        if memory_sink is not None and self._callback is not None:
            memory_sink.unsubscribe(self._callback)
        
        # Отправляем sentinel в очередь для завершения генератора
        try:
            self._event_queue.put_nowait(None)
        except queue.Full:
            pass
    
    def __aenter__(self) -> 'LogStreamAdapter':
        """Поддержка async контекстного менеджера."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Автоматическая остановка при выходе из контекста."""
        self.stop()


def create_sse_event(log_event: LogEvent) -> str:
    """Преобразует LogEvent в строку SSE события.
    
    Используется для интеграции с FastAPI SSE endpoint.
    Не является частью логирования, только адаптер форматов.
    
    Args:
        log_event: Событие логирования
        
    Returns:
        Строка в формате SSE (text/event-stream)
    """
    import json
    from datetime import datetime
    
    event_type = "log"
    if log_event.stage:
        event_type = f"stage_{log_event.stage.value}"
    
    data = log_event.to_dict()
    
    lines = [
        f"event: {event_type}",
        f"data: {json.dumps(data, ensure_ascii=False)}",
        ""  # Пустая строка для завершения события
    ]
    
    return "\n".join(lines)