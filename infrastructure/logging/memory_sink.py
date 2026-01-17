"""MemoryLoggerSink - хранение логов в памяти для UI/тестов."""
import threading
from typing import List, Optional, Callable

from infrastructure.logging.models import LogEvent
from infrastructure.logging.sink import LoggerSink


class MemoryLoggerSink(LoggerSink):
    """Sink для хранения логов в памяти.
    
    Используется для:
    - UI стриминга (SSE / WebSocket)
    - Тестирования (проверка залогированных событий)
    - Отладки без записи в файлы
    
    Особенности:
    - Потокобезопасное хранение
    - Ограничение размера буфера
    - Подписки на события через callback-и
    """
    
    def __init__(
        self,
        max_events: int = 1000,
        callbacks: Optional[List[Callable[[LogEvent], None]]] = None
    ) -> None:
        """Инициализация MemoryLoggerSink.
        
        Args:
            max_events: Максимальное количество событий в буфере
            callbacks: Список callback-функций для подписки на события
        """
        self.max_events = max_events
        self._events: List[LogEvent] = []
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[LogEvent], None]] = callbacks or []
    
    def emit(self, event: LogEvent) -> None:
        """Добавляет событие в память.
        
        Args:
            event: Событие для хранения
        """
        with self._lock:
            # Добавляем событие
            self._events.append(event)
            
            # Ограничиваем размер буфера (удаляем самые старые)
            if len(self._events) > self.max_events:
                self._events = self._events[-self.max_events:]
            
            # Вызываем callback-и
            for callback in self._callbacks:
                try:
                    callback(event)
                except Exception:
                    # Игнорируем ошибки в callback-ах
                    pass
    
    def subscribe(self, callback: Callable[[LogEvent], None]) -> None:
        """Подписывает callback на новые события.
        
        Args:
            callback: Функция, которая будет вызвана при каждом новом событии
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)
    
    def unsubscribe(self, callback: Callable[[LogEvent], None]) -> None:
        """Отписывает callback от событий.
        
        Args:
            callback: Функция для отписки
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
    
    def get_events(
        self,
        level: Optional[str] = None,
        source: Optional[str] = None,
        stage: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[LogEvent]:
        """Получает события из буфера с фильтрацией.
        
        Args:
            level: Фильтр по уровню
            source: Фильтр по источнику
            stage: Фильтр по этапу
            task_id: Фильтр по ID задачи
            limit: Максимальное количество событий (None = все)
            
        Returns:
            Список отфильтрованных событий
        """
        with self._lock:
            events = self._events.copy()
        
        # Фильтрация
        filtered = []
        for event in events:
            if level and event.level.value != level:
                continue
            if source and event.source.value != source:
                continue
            if stage and (not event.stage or event.stage.value != stage):
                continue
            if task_id and event.task_id != task_id:
                continue
            filtered.append(event)
        
        # Ограничение
        if limit is not None:
            filtered = filtered[-limit:]
        
        return filtered
    
    def clear(self) -> None:
        """Очищает буфер событий."""
        with self._lock:
            self._events.clear()
    
    def flush(self) -> None:
        """Для MemoryLoggerSink ничего не делает."""
        pass
    
    def close(self) -> None:
        """Закрывает sink и очищает callback-и."""
        with self._lock:
            self._callbacks.clear()