"""Негативные тесты для EventStore - проверяют что тесты выявляют проблемы.

Эти тесты проверяют, что тесты действительно падают при неправильном поведении,
а не просто проходят из-за слабых проверок.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from infrastructure.event_store import EventStore, Event


class TestEventStoreNegative:
    """Негативные тесты - проверяют что тесты выявляют проблемы."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure
    async def test_max_sessions_limit_enforced(self):
        """Проверяет что лимит сессий действительно соблюдается.
        
        Этот тест должен ПРОВЕРИТЬ что система не позволяет превысить лимит.
        Если лимит не соблюдается - это проблема безопасности (утечка памяти).
        """
        # Останавливаем фоновую задачу
        if EventStore._cleanup_task and not EventStore._cleanup_task.done():
            EventStore._cleanup_task.cancel()
            try:
                await EventStore._cleanup_task
            except asyncio.CancelledError:
                pass
        
        EventStore._instances.clear()
        EventStore._events.clear()
        EventStore._event_queues.clear()
        EventStore._cleanup_task = None
        
        original_max = EventStore._max_sessions
        EventStore._max_sessions = 3  # Маленький лимит
        
        try:
            # Создаём сессии до лимита
            await EventStore.get_for_session("session-1")
            await EventStore.get_for_session("session-2")
            await EventStore.get_for_session("session-3")
            
            # Проверяем что лимит достигнут
            assert len(EventStore._instances) == 3, \
                f"Должно быть 3 сессии, но найдено {len(EventStore._instances)}"
            
            # Останавливаем фоновую задачу
            if EventStore._cleanup_task and not EventStore._cleanup_task.done():
                EventStore._cleanup_task.cancel()
                try:
                    await EventStore._cleanup_task
                except asyncio.CancelledError:
                    pass
                EventStore._cleanup_task = None
            
            # Создаём ещё одну сессию - должна удалиться самая старая
            await EventStore.get_for_session("session-4")
            await asyncio.sleep(0.1)  # Ждём завершения очистки
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: лимит не должен быть превышен
            # Если этот тест падает - значит лимит не соблюдается (ПРОБЛЕМА!)
            assert len(EventStore._instances) <= EventStore._max_sessions, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Лимит сессий ({EventStore._max_sessions}) превышен! " \
                f"Найдено {len(EventStore._instances)} сессий: {list(EventStore._instances.keys())}. " \
                f"Это утечка памяти!"
            
            # Проверяем что самая старая сессия удалена
            assert "session-1" not in EventStore._instances, \
                f"❌ ПРОБЛЕМА: Самая старая сессия (session-1) не была удалена. " \
                f"Сессии: {list(EventStore._instances.keys())}"
        finally:
            EventStore._max_sessions = original_max
            if EventStore._cleanup_task and not EventStore._cleanup_task.done():
                EventStore._cleanup_task.cancel()
                try:
                    await EventStore._cleanup_task
                except asyncio.CancelledError:
                    pass
                EventStore._cleanup_task = None
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure
    async def test_cleanup_removes_all_data(self):
        """Проверяет что cleanup_session удаляет ВСЕ данные сессии.
        
        Если cleanup_session не удаляет события или очереди - это утечка памяти.
        """
        EventStore._instances.clear()
        EventStore._events.clear()
        EventStore._event_queues.clear()
        
        # Создаём сессию с данными
        store = await EventStore.get_for_session("test-session")
        await store.save_event("test", {"data": "test"})
        queue = EventStore.get_event_queue("test-session")
        await queue.put(Event("id", "test", {}, datetime.now(), "test-session"))
        
        # Проверяем что данные есть
        assert "test-session" in EventStore._instances
        assert "test-session" in EventStore._events
        assert "test-session" in EventStore._event_queues
        
        # Очищаем сессию
        await EventStore.cleanup_session("test-session")
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: все данные должны быть удалены
        # Если этот тест падает - cleanup_session работает не полностью (ПРОБЛЕМА!)
        assert "test-session" not in EventStore._instances, \
            f"❌ ПРОБЛЕМА: Экземпляр сессии не удалён после cleanup"
        assert "test-session" not in EventStore._events, \
            f"❌ ПРОБЛЕМА: События сессии не удалены после cleanup. " \
            f"Остались события: {list(EventStore._events.keys())}"
        assert "test-session" not in EventStore._event_queues, \
            f"❌ ПРОБЛЕМА: Очередь сессии не удалена после cleanup. " \
            f"Остались очереди: {list(EventStore._event_queues.keys())}"
