"""Тест детекции проблем - проверяет что тесты выявляют проблемы.

Этот файл демонстрирует, что тесты правильно выявляют проблемы,
а не просто проходят.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from infrastructure.event_store import EventStore, Event


class TestEventStoreDetection:
    """Тесты для проверки что тесты выявляют проблемы."""
    
    @pytest.mark.asyncio
    async def test_detects_memory_leak_if_limit_not_enforced(self):
        """Проверяет что тест выявит проблему если лимит не соблюдается.
        
        Этот тест должен ПАДАТЬ если лимит не соблюдается.
        Если тест проходит когда лимит не соблюдается - тест плохой.
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
        EventStore._max_sessions = 2  # Лимит = 2
        
        try:
            # Создаём 2 сессии (достигаем лимита)
            await EventStore.get_for_session("session-1")
            await EventStore.get_for_session("session-2")
            
            assert len(EventStore._instances) == 2, "Должно быть 2 сессии"
            
            # Останавливаем фоновую задачу
            if EventStore._cleanup_task and not EventStore._cleanup_task.done():
                EventStore._cleanup_task.cancel()
                try:
                    await EventStore._cleanup_task
                except asyncio.CancelledError:
                    pass
                EventStore._cleanup_task = None
            
            # Создаём 3-ю сессию - должна удалиться session-1
            await EventStore.get_for_session("session-3")
            await asyncio.sleep(0.1)
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: лимит НЕ должен быть превышен
            # Если этот assert падает - значит есть ПРОБЛЕМА (утечка памяти)
            # Тест ДОЛЖЕН упасть если лимит превышен - это правильно!
            actual_count = len(EventStore._instances)
            max_allowed = EventStore._max_sessions
            
            if actual_count > max_allowed:
                pytest.fail(
                    f"❌ ОБНАРУЖЕНА ПРОБЛЕМА: Лимит сессий ({max_allowed}) превышен! "
                    f"Найдено {actual_count} сессий: {list(EventStore._instances.keys())}. "
                    f"Это утечка памяти - система не удаляет старые сессии!"
                )
            
            # Дополнительная проверка: самая старая сессия должна быть удалена
            if "session-1" in EventStore._instances:
                pytest.fail(
                    f"❌ ОБНАРУЖЕНА ПРОБЛЕМА: Самая старая сессия (session-1) не была удалена. "
                    f"Сессии: {list(EventStore._instances.keys())}. "
                    f"LRU логика не работает!"
                )
            
            # Если мы дошли сюда - всё хорошо, лимит соблюдается
            assert actual_count <= max_allowed, "Лимит должен соблюдаться"
            
        finally:
            EventStore._max_sessions = original_max
            if EventStore._cleanup_task and not EventStore._cleanup_task.done():
                EventStore._cleanup_task.cancel()
                try:
                    await EventStore._cleanup_task
                except asyncio.CancelledError:
                    pass
                EventStore._cleanup_task = None
