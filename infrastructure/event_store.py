"""Хранилище событий для стриминговых узлов.

Позволяет хранить SSE события вне AgentState для предотвращения
раздувания состояния при длительных задачах.
"""
import asyncio
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from utils.logger import get_logger

logger = get_logger()


@dataclass
class Event:
    """Событие для хранения."""
    event_id: str
    event_type: str
    data: Any
    timestamp: datetime
    session_id: str


class EventStore:
    """Хранилище событий для сессий.
    
    Хранит события в памяти с автоматической очисткой старых событий.
    События привязаны к session_id для изоляции между запросами.
    
    Особенности:
    - Хранение событий в памяти (можно расширить до Redis/DB)
    - Автоматическая очистка старых событий
    - Изоляция по session_id
    - Настраиваемый TTL для событий
    - Ограничение максимального количества сессий (LRU)
    - Периодическая автоматическая очистка
    """
    
    _instances: Dict[str, 'EventStore'] = {}
    _lock = asyncio.Lock()
    
    # Глобальное хранилище событий (session_id -> events)
    # Используем обычный dict вместо defaultdict для лучшей изоляции в тестах
    _events: Dict[str, List[Event]] = {}
    
    # Очереди событий для реального времени (session_id -> asyncio.Queue)
    _event_queues: Dict[str, asyncio.Queue] = {}
    
    # TTL для событий (по умолчанию 1 час)
    _event_ttl = timedelta(hours=1)
    
    # Максимальное количество сессий (для предотвращения утечек памяти)
    _max_sessions = 1000
    
    # Флаг для периодической очистки
    _cleanup_task: Optional[asyncio.Task] = None
    _cleanup_interval = timedelta(minutes=5)  # Очистка каждые 5 минут
    
    def __init__(self, session_id: str):
        """Инициализирует хранилище для сессии.
        
        Args:
            session_id: ID сессии для изоляции событий
        """
        self.session_id = session_id
    
    @classmethod
    async def get_for_session(cls, session_id: str) -> 'EventStore':
        """Возвращает хранилище для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Экземпляр EventStore для сессии
        """
        if session_id not in cls._instances:
            oldest_session = None
            async with cls._lock:
                if session_id not in cls._instances:
                    # Проверяем лимит сессий
                    if len(cls._instances) >= cls._max_sessions:
                        # Находим самую старую сессию (LRU) внутри блокировки
                        oldest_timestamp = datetime.now()
                        
                        for sid, events in cls._events.items():
                            if events:
                                last_event_time = max(e.timestamp for e in events)
                                if last_event_time < oldest_timestamp:
                                    oldest_timestamp = last_event_time
                                    oldest_session = sid
                        
                        # Если нет событий, удаляем первую сессию из _instances
                        if not oldest_session and cls._instances:
                            oldest_session = next(iter(cls._instances.keys()))
                    
                    cls._instances[session_id] = cls(session_id)
                    
                    # ИСПРАВЛЕНИЕ: Запускаем периодическую очистку если ещё не запущена
                    # Но только если не в тестовом режиме (чтобы не мешать тестам)
                    from utils.test_mode import is_test_mode
                    if not is_test_mode() and (cls._cleanup_task is None or cls._cleanup_task.done()):
                        cls._cleanup_task = asyncio.create_task(cls._periodic_cleanup())
            
            # Вызываем cleanup_session ВНЕ блокировки чтобы избежать deadlock
            if oldest_session:
                logger.debug(f"🗑️ Удаляю самую старую сессию {oldest_session[:8]}... (лимит сессий достигнут)")
                await cls.cleanup_session(oldest_session)
        
        return cls._instances[session_id]
    
    @classmethod
    async def _remove_oldest_session(cls) -> None:
        """Удаляет самую старую сессию (LRU)."""
        if not cls._instances:
            return
        
        # Находим сессию с самым старым последним событием
        oldest_session = None
        oldest_timestamp = datetime.now()
        
        for session_id, events in cls._events.items():
            if events:
                last_event_time = max(e.timestamp for e in events)
                if last_event_time < oldest_timestamp:
                    oldest_timestamp = last_event_time
                    oldest_session = session_id
        
        # Если нет событий, удаляем первую сессию из _instances
        if not oldest_session and cls._instances:
            oldest_session = next(iter(cls._instances.keys()))
        
        if oldest_session:
            logger.debug(f"🗑️ Удаляю самую старую сессию {oldest_session[:8]}... (лимит сессий достигнут)")
            # Используем cleanup_session, но вне блокировки чтобы избежать deadlock
            # (cleanup_session сам использует _lock)
            await cls.cleanup_session(oldest_session)
    
    @classmethod
    async def _periodic_cleanup(cls) -> None:
        """Периодическая очистка старых событий и сессий."""
        while True:
            try:
                await asyncio.sleep(cls._cleanup_interval.total_seconds())
                await cls.cleanup_all_old_events()
                logger.debug("🧹 Периодическая очистка EventStore выполнена")
            except asyncio.CancelledError:
                logger.debug("🛑 Периодическая очистка отменена")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в периодической очистке: {e}", error=e)
                # Продолжаем работу даже при ошибке
                await asyncio.sleep(60)  # Ждём минуту перед следующей попыткой
    
    async def save_event(self, event_type: str, data: Any) -> str:
        """Сохраняет событие и возвращает его ID.
        
        Также отправляет событие в очередь для реального времени, если очередь существует.
        
        Args:
            event_type: Тип события (thinking, plan_chunk, etc.)
            data: Данные события
            
        Returns:
            ID сохранённого события
        """
        event_id = str(uuid.uuid4())
        event = Event(
            event_id=event_id,
            event_type=event_type,
            data=data,
            timestamp=datetime.now(),
            session_id=self.session_id
        )
        
        # Создаем список если его еще нет
        if self.session_id not in EventStore._events:
            EventStore._events[self.session_id] = []
        EventStore._events[self.session_id].append(event)
        
        # Отправляем событие в очередь для реального времени
        # ИСПРАВЛЕНИЕ: Проверяем наличие очереди и отправляем событие
        if self.session_id in EventStore._event_queues:
            try:
                queue = EventStore._event_queues[self.session_id]
                # Используем await для асинхронной отправки
                await queue.put(event)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось отправить событие в очередь: {e}")
        
        # ИСПРАВЛЕНИЕ: Очищаем старые события для этой сессии, но НЕ сразу после сохранения
        # чтобы только что сохраненное событие не было удалено. Очистка происходит периодически.
        # await self._cleanup_old_events()  # Убрано - очистка происходит периодически
        
        # ОПТИМИЗАЦИЯ: Логируем только периодически (каждые 10 событий) или при ошибках
        # Это значительно уменьшает объем логов
        event_count = len(EventStore._events.get(self.session_id, []))
        if event_count % 10 == 0 or event_type == "error":
            logger.debug(f"💾 Событие #{event_count} сохранено: {event_type} (ID: {event_id[:8]}...)")
        
        return event_id
    
    @classmethod
    def get_event_queue(cls, session_id: str) -> asyncio.Queue:
        """Получает или создаёт очередь событий для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Очередь событий для сессии
        """
        if session_id not in cls._event_queues:
            cls._event_queues[session_id] = asyncio.Queue()
        return cls._event_queues[session_id]
    
    @classmethod
    def remove_event_queue(cls, session_id: str) -> None:
        """Удаляет очередь событий для сессии.
        
        Args:
            session_id: ID сессии
        """
        if session_id in cls._event_queues:
            del cls._event_queues[session_id]
            logger.debug(f"🗑️ Очередь событий удалена для сессии {session_id[:8]}...")
    
    @classmethod
    async def cleanup_session(cls, session_id: str) -> None:
        """Полностью очищает сессию (события, очередь, экземпляр).
        
        Используется при закрытии SSE соединения для предотвращения утечек памяти.
        
        Args:
            session_id: ID сессии для очистки
        """
        async with cls._lock:
            # Очищаем события
            if session_id in cls._events:
                del cls._events[session_id]
            
            # Удаляем очередь
            if session_id in cls._event_queues:
                # Очищаем очередь от оставшихся событий
                queue = cls._event_queues[session_id]
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                del cls._event_queues[session_id]
            
            # Удаляем экземпляр
            if session_id in cls._instances:
                del cls._instances[session_id]
            
            logger.debug(f"🧹 Сессия {session_id[:8]}... полностью очищена")
    
    async def get_event(self, event_id: str) -> Optional[Event]:
        """Получает событие по ID.
        
        Args:
            event_id: ID события
            
        Returns:
            Событие или None если не найдено
        """
        events = EventStore._events.get(self.session_id, [])
        for event in events:
            if event.event_id == event_id:
                return event
        return None
    
    async def get_events(self, event_ids: List[str]) -> List[Event]:
        """Получает несколько событий по ID.
        
        Args:
            event_ids: Список ID событий
            
        Returns:
            Список событий (в порядке запроса)
        """
        events = EventStore._events.get(self.session_id, [])
        event_map = {e.event_id: e for e in events}
        return [event_map[eid] for eid in event_ids if eid in event_map]
    
    async def get_all_events(self) -> List[Event]:
        """Возвращает все события для сессии.
        
        Returns:
            Список всех событий сессии
        """
        return EventStore._events.get(self.session_id, []).copy()
    
    async def clear_events(self) -> None:
        """Очищает все события для сессии."""
        if self.session_id in EventStore._events:
            del EventStore._events[self.session_id]
            logger.debug(f"🗑️ События очищены для сессии {self.session_id[:8]}...")
    
    async def _cleanup_old_events(self) -> None:
        """Очищает старые события (старше TTL)."""
        now = datetime.now()
        events = EventStore._events.get(self.session_id, [])
        
        # Фильтруем события, оставляя только свежие
        fresh_events = [
            e for e in events
            if now - e.timestamp < EventStore._event_ttl
        ]
        
        if len(fresh_events) != len(events):
            if fresh_events:
                EventStore._events[self.session_id] = fresh_events
            elif self.session_id in EventStore._events:
                # Удаляем ключ если список пустой
                del EventStore._events[self.session_id]
            logger.debug(
                f"🧹 Очищено {len(events) - len(fresh_events)} старых событий "
                f"для сессии {self.session_id[:8]}..."
            )
    
    @classmethod
    async def cleanup_all_old_events(cls) -> None:
        """Очищает старые события для всех сессий.
        
        Также очищает пустые очереди событий для предотвращения утечек памяти.
        """
        async with cls._lock:
            now = datetime.now()
            sessions_to_remove = []
            
            # Очищаем старые события
            # Создаем копию списка ключей для безопасной итерации
            session_ids = list(EventStore._events.keys())
            for session_id in session_ids:
                events = EventStore._events.get(session_id, [])
                fresh_events = [
                    e for e in events
                    if now - e.timestamp < EventStore._event_ttl
                ]
                
                if not fresh_events:
                    sessions_to_remove.append(session_id)
                else:
                    EventStore._events[session_id] = fresh_events
            
            # Удаляем пустые сессии
            for session_id in sessions_to_remove:
                if session_id in EventStore._events:
                    del EventStore._events[session_id]
                if session_id in EventStore._instances:
                    del EventStore._instances[session_id]
                # Также удаляем очередь если она пустая
                if session_id in EventStore._event_queues:
                    queue = EventStore._event_queues[session_id]
                    if queue.empty():
                        del EventStore._event_queues[session_id]
                        logger.debug(f"🗑️ Удалена пустая очередь для сессии {session_id[:8]}...")
            
            # Очищаем пустые очереди (даже если сессия ещё существует)
            queues_to_remove = []
            for session_id, queue in list(EventStore._event_queues.items()):
                if queue.empty() and session_id not in EventStore._events:
                    queues_to_remove.append(session_id)
            
            for session_id in queues_to_remove:
                del EventStore._event_queues[session_id]
                logger.debug(f"🗑️ Удалена orphan очередь для сессии {session_id[:8]}...")
            
            if sessions_to_remove or queues_to_remove:
                logger.debug(
                    f"🧹 Очищено {len(sessions_to_remove)} пустых сессий, "
                    f"{len(queues_to_remove)} orphan очередей"
                )


# === Удобные функции для импорта ===

async def get_event_store(session_id: str) -> EventStore:
    """Возвращает хранилище событий для сессии.
    
    Args:
        session_id: ID сессии
        
    Returns:
        Экземпляр EventStore
    """
    return await EventStore.get_for_session(session_id)
