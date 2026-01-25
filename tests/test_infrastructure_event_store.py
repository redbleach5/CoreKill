"""Тесты для infrastructure/event_store.py."""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from infrastructure.event_store import EventStore, Event


class TestEvent:
    """Тесты для класса Event."""
    
    @pytest.mark.infrastructure

    
    def test_event_creation(self):
        """Тест создания события."""
        event = Event(
            event_id="test-id",
            event_type="thinking",
            data={"content": "test"},
            timestamp=datetime.now(),
            session_id="session-1"
        )
        
        assert event.event_id == "test-id"
        assert event.event_type == "thinking"
        assert event.data == {"content": "test"}
        assert event.session_id == "session-1"


class TestEventStoreInit:
    """Тесты инициализации EventStore."""
    
    @pytest.mark.infrastructure

    
    def test_init_with_session_id(self):
        """Тест инициализации с session_id."""
        store = EventStore("session-123")
        
        assert store.session_id == "session-123"


class TestEventStoreGetForSession:
    """Тесты для get_for_session."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_for_session_creates_new(self):
        """Тест создания нового хранилища для сессии."""
        # Очищаем кэш
        EventStore._instances.clear()
        
        store = await EventStore.get_for_session("new-session")
        
        assert store.session_id == "new-session"
        assert "new-session" in EventStore._instances
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_for_session_returns_existing(self):
        """Тест возврата существующего хранилища."""
        # Очищаем кэш
        EventStore._instances.clear()
        
        store1 = await EventStore.get_for_session("session-1")
        store2 = await EventStore.get_for_session("session-1")
        
        assert store1 is store2
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_for_session_max_sessions(self):
        """Тест ограничения максимального количества сессий.
        
        Проверяет что:
        1. При достижении лимита удаляется самая старая сессия (LRU)
        2. Количество сессий не превышает лимит
        3. Удаляются не только экземпляры, но и события/очереди
        """
        # Останавливаем фоновую задачу очистки если она запущена
        if EventStore._cleanup_task and not EventStore._cleanup_task.done():
            EventStore._cleanup_task.cancel()
            try:
                await EventStore._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Очищаем кэш и события
        EventStore._instances.clear()
        EventStore._events.clear()
        EventStore._event_queues.clear()
        EventStore._cleanup_task = None
        
        # Устанавливаем маленький лимит для теста
        original_max = EventStore._max_sessions
        EventStore._max_sessions = 2
        
        try:
            # Создаём две сессии
            store1 = await EventStore.get_for_session("session-1")
            store2 = await EventStore.get_for_session("session-2")
            
            # Проверяем что созданы обе сессии
            assert len(EventStore._instances) == 2
            assert "session-1" in EventStore._instances
            assert "session-2" in EventStore._instances
            
            # Добавляем события для сессий (session-1 старше)
            EventStore._events["session-1"] = [
                Event("id1", "test", {}, datetime.now() - timedelta(hours=2), "session-1")
            ]
            EventStore._events["session-2"] = [
                Event("id2", "test", {}, datetime.now() - timedelta(hours=1), "session-2")
            ]
            
            # Создаём очереди для обеих сессий
            queue1 = EventStore.get_event_queue("session-1")
            queue2 = EventStore.get_event_queue("session-2")
            
            # Останавливаем фоновую задачу перед созданием третьей сессии
            if EventStore._cleanup_task and not EventStore._cleanup_task.done():
                EventStore._cleanup_task.cancel()
                try:
                    await EventStore._cleanup_task
                except asyncio.CancelledError:
                    pass
                EventStore._cleanup_task = None
            
            # Создаём третью сессию - должна удалиться session-1 (самая старая)
            store3 = await EventStore.get_for_session("session-3")
            
            # Ждём немного для завершения асинхронной очистки
            await asyncio.sleep(0.1)
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: session-1 должна быть полностью удалена
            # Это проверяет что LRU логика работает правильно
            assert "session-1" not in EventStore._instances, \
                f"❌ ПРОБЛЕМА: session-1 должна быть удалена (самая старая), но осталась. " \
                f"Сессии: {list(EventStore._instances.keys())}, лимит: {EventStore._max_sessions}"
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: количество сессий не должно превышать лимит
            # Это проверяет что лимит действительно соблюдается
            assert len(EventStore._instances) <= EventStore._max_sessions, \
                f"❌ ПРОБЛЕМА: Количество сессий ({len(EventStore._instances)}) превышает лимит ({EventStore._max_sessions}). " \
                f"Сессии: {list(EventStore._instances.keys())}"
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: session-1 должна быть удалена из всех хранилищ
            # Это проверяет что cleanup_session работает полностью, а не частично
            assert "session-1" not in EventStore._events, \
                f"❌ ПРОБЛЕМА: События session-1 должны быть удалены, но остались. " \
                f"События: {list(EventStore._events.keys())}"
            assert "session-1" not in EventStore._event_queues, \
                f"❌ ПРОБЛЕМА: Очередь session-1 должна быть удалена, но осталась. " \
                f"Очереди: {list(EventStore._event_queues.keys())}"
            
            # Проверяем что session-2 и session-3 остались
            assert "session-2" in EventStore._instances, "session-2 должна остаться"
            assert "session-3" in EventStore._instances, "session-3 должна быть создана"
            
            # Останавливаем фоновую задачу после теста
            if EventStore._cleanup_task and not EventStore._cleanup_task.done():
                EventStore._cleanup_task.cancel()
                try:
                    await EventStore._cleanup_task
                except asyncio.CancelledError:
                    pass
                EventStore._cleanup_task = None
        finally:
            EventStore._max_sessions = original_max
            # Убеждаемся что фоновая задача остановлена
            if EventStore._cleanup_task and not EventStore._cleanup_task.done():
                EventStore._cleanup_task.cancel()
                try:
                    await EventStore._cleanup_task
                except asyncio.CancelledError:
                    pass
                EventStore._cleanup_task = None


class TestEventStoreSaveEvent:
    """Тесты для save_event."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_save_event(self):
        """Тест сохранения события."""
        # Очищаем события
        EventStore._events.clear()
        EventStore._instances.clear()
        
        store = await EventStore.get_for_session("test-session")
        
        event_id = await store.save_event("thinking", {"content": "test"})
        
        assert event_id is not None
        assert len(EventStore._events["test-session"]) == 1
        
        event = EventStore._events["test-session"][0]
        assert event.event_type == "thinking"
        assert event.data == {"content": "test"}
        assert event.session_id == "test-session"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_save_event_to_queue(self):
        """Тест отправки события в очередь."""
        # Очищаем события и очереди
        EventStore._events.clear()
        EventStore._event_queues.clear()
        EventStore._instances.clear()
        
        store = await EventStore.get_for_session("test-session")
        # Создаем очередь ДО сохранения события, чтобы событие попало в очередь
        queue = EventStore.get_event_queue("test-session")
        
        event_id = await store.save_event("thinking", {"content": "test"})
        
        # Проверяем что событие попало в очередь
        assert not queue.empty()
        queued_event = await queue.get()
        assert queued_event.event_type == "thinking"
        assert queued_event.data == {"content": "test"}


class TestEventStoreGetEvent:
    """Тесты для get_event."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_event_by_id(self):
        """Тест получения события по ID."""
        # Очищаем события
        EventStore._events.clear()
        EventStore._instances.clear()
        
        store = await EventStore.get_for_session("test-session")
        
        event_id = await store.save_event("thinking", {"content": "test"})
        
        event = await store.get_event(event_id)
        
        assert event is not None
        assert event.event_id == event_id
        assert event.event_type == "thinking"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_event_not_found(self):
        """Тест получения несуществующего события."""
        # Очищаем события
        EventStore._events.clear()
        EventStore._instances.clear()
        
        store = await EventStore.get_for_session("test-session")
        
        event = await store.get_event("non-existent-id")
        
        assert event is None


class TestEventStoreGetEvents:
    """Тесты для get_events."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_events_multiple(self):
        """Тест получения нескольких событий."""
        # Очищаем события
        EventStore._events.clear()
        EventStore._instances.clear()
        
        store = await EventStore.get_for_session("test-session")
        
        event_id1 = await store.save_event("thinking", {"content": "test1"})
        event_id2 = await store.save_event("plan", {"content": "test2"})
        
        events = await store.get_events([event_id1, event_id2])
        
        assert len(events) == 2
        assert events[0].event_id == event_id1
        assert events[1].event_id == event_id2
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_events_partial(self):
        """Тест получения части событий (некоторые не найдены)."""
        # Очищаем события
        EventStore._events.clear()
        EventStore._instances.clear()
        
        store = await EventStore.get_for_session("test-session")
        
        event_id1 = await store.save_event("thinking", {"content": "test1"})
        
        events = await store.get_events([event_id1, "non-existent"])
        
        assert len(events) == 1
        assert events[0].event_id == event_id1


class TestEventStoreGetAllEvents:
    """Тесты для get_all_events."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_all_events(self):
        """Тест получения всех событий сессии."""
        # Очищаем события
        EventStore._events.clear()
        EventStore._instances.clear()
        
        store = await EventStore.get_for_session("test-session")
        
        await store.save_event("thinking", {"content": "test1"})
        await store.save_event("plan", {"content": "test2"})
        await store.save_event("code", {"content": "test3"})
        
        events = await store.get_all_events()
        
        assert len(events) == 3
        assert all(e.session_id == "test-session" for e in events)
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_all_events_empty(self):
        """Тест получения всех событий когда их нет."""
        # Очищаем события
        EventStore._events.clear()
        EventStore._instances.clear()
        
        store = await EventStore.get_for_session("test-session")
        
        events = await store.get_all_events()
        
        assert len(events) == 0


class TestEventStoreEventQueue:
    """Тесты для работы с очередями событий."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_event_queue_creates_new(self):
        """Тест создания новой очереди."""
        EventStore._event_queues.clear()
        
        queue = EventStore.get_event_queue("new-session")
        
        assert "new-session" in EventStore._event_queues
        assert queue is EventStore._event_queues["new-session"]
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_event_queue_returns_existing(self):
        """Тест возврата существующей очереди."""
        EventStore._event_queues.clear()
        
        queue1 = EventStore.get_event_queue("session-1")
        queue2 = EventStore.get_event_queue("session-1")
        
        assert queue1 is queue2
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_remove_event_queue(self):
        """Тест удаления очереди."""
        EventStore._event_queues.clear()
        
        queue = EventStore.get_event_queue("session-1")
        assert "session-1" in EventStore._event_queues
        
        EventStore.remove_event_queue("session-1")
        
        assert "session-1" not in EventStore._event_queues


class TestEventStoreCleanup:
    """Тесты для очистки событий."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_cleanup_old_events(self):
        """Тест очистки старых событий."""
        # Очищаем события
        EventStore._events.clear()
        EventStore._instances.clear()
        
        store = await EventStore.get_for_session("test-session")
        
        # ИСПРАВЛЕНИЕ: Создаём список событий для сессии если его нет
        if "test-session" not in EventStore._events:
            EventStore._events["test-session"] = []
        
        # Создаём старое событие (больше TTL)
        old_event = Event(
            "old-id",
            "test",
            {},
            datetime.now() - timedelta(hours=2),
            "test-session"
        )
        EventStore._events["test-session"].append(old_event)
        
        # Создаём новое событие
        await store.save_event("test", {"content": "new"})
        
        # Очищаем старые события
        await store._cleanup_old_events()
        
        # Старое событие должно быть удалено
        events = EventStore._events.get("test-session", [])
        assert len(events) == 1
        assert events[0].event_id != "old-id"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_cleanup_session(self):
        """Тест полной очистки сессии."""
        # Очищаем всё
        EventStore._instances.clear()
        EventStore._events.clear()
        EventStore._event_queues.clear()
        
        store = await EventStore.get_for_session("test-session")
        queue = EventStore.get_event_queue("test-session")
        
        await store.save_event("test", {"content": "test"})
        await queue.put(Event("id", "test", {}, datetime.now(), "test-session"))
        
        # Очищаем сессию
        await EventStore.cleanup_session("test-session")
        
        assert "test-session" not in EventStore._instances
        assert "test-session" not in EventStore._events
        assert "test-session" not in EventStore._event_queues
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_cleanup_all_old_events(self):
        """Тест очистки всех старых событий во всех сессиях."""
        # Очищаем всё
        EventStore._instances.clear()
        EventStore._events.clear()
        
        store1 = await EventStore.get_for_session("session-1")
        store2 = await EventStore.get_for_session("session-2")
        
        # Создаём старые события
        old_event1 = Event(
            "old-1",
            "test",
            {},
            datetime.now() - timedelta(hours=2),
            "session-1"
        )
        old_event2 = Event(
            "old-2",
            "test",
            {},
            datetime.now() - timedelta(hours=2),
            "session-2"
        )
        
        # ИСПРАВЛЕНИЕ: Создаём списки событий для сессий если их нет
        if "session-1" not in EventStore._events:
            EventStore._events["session-1"] = []
        if "session-2" not in EventStore._events:
            EventStore._events["session-2"] = []
        
        EventStore._events["session-1"].append(old_event1)
        EventStore._events["session-2"].append(old_event2)
        
        # Очищаем все старые события
        await EventStore.cleanup_all_old_events()
        
        # Старые события должны быть удалены
        assert len(EventStore._events.get("session-1", [])) == 0
        assert len(EventStore._events.get("session-2", [])) == 0


class TestEventStoreIsolation:
    """Тесты изоляции между сессиями."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_session_isolation(self):
        """Тест что события разных сессий изолированы."""
        # Очищаем всё
        EventStore._instances.clear()
        EventStore._events.clear()
        
        store1 = await EventStore.get_for_session("session-1")
        store2 = await EventStore.get_for_session("session-2")
        
        await store1.save_event("test", {"content": "session1"})
        await store2.save_event("test", {"content": "session2"})
        
        events1 = await store1.get_all_events()
        events2 = await store2.get_all_events()
        
        assert len(events1) == 1
        assert len(events2) == 1
        assert events1[0].data["content"] == "session1"
        assert events2[0].data["content"] == "session2"
