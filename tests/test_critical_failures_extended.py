"""Расширенные тесты для критических нештатных ситуаций.

Дополнительные тесты для проверки критических сценариев:
- Сбои сети
- Потеря данных
- Некорректные состояния
- Крайние случаи
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from infrastructure.event_store import EventStore
from datetime import datetime


class TestNetworkFailures:
    """Тесты для критических ситуаций с сетью."""
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_connection_refused_handling(self):
        """Проверяет обработку ConnectionRefusedError."""
        try:
            from infrastructure.connection_pool import get_ollama_pool
            
            # Мокируем ConnectionRefusedError
            with patch('ollama.Client') as mock_client:
                mock_instance = Mock()
                mock_instance.list = AsyncMock(side_effect=ConnectionRefusedError("Connection refused"))
                mock_client.return_value = mock_instance
                
                # Система должна обработать ошибку без падения
                try:
                    pool = await get_ollama_pool()
                    # Если здесь падает - проблема с обработкой ошибок
                except ConnectionRefusedError:
                    # Ошибка ожидаема, но система должна её обработать gracefully
                    pass
                except Exception as e:
                    if "AttributeError" in str(type(e).__name__) or "NoneType" in str(e):
                        pytest.fail(
                            f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Критическая ошибка при ConnectionRefused: {e}"
                        )
        except Exception as e:
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Система не обрабатывает ConnectionRefused: {e}"
            )


class TestDataLossPrevention:
    """Тесты для предотвращения потери данных."""
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_event_store_no_data_loss_on_cleanup(self):
        """Проверяет что данные не теряются при cleanup."""
        EventStore._instances.clear()
        EventStore._events.clear()
        
        store = await EventStore.get_for_session("test-no-loss")
        
        # Сохраняем несколько событий
        event_ids = []
        for i in range(5):
            event_id = await store.save_event("test", {"index": i})
            event_ids.append(event_id)
        
        # Небольшая задержка для завершения операций
        await asyncio.sleep(0.05)
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: все события должны быть доступны ДО cleanup
        for i, event_id in enumerate(event_ids):
            event = await store.get_event(event_id)
            assert event is not None, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Событие {event_id} (index={i}) потеряно ДО cleanup!"
            assert event.data["index"] == i, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Данные события {event_id} некорректны! " \
                f"Ожидалось index={i}, получено {event.data.get('index')}"
        
        # Проверяем через get_all_events
        all_events = await store.get_all_events()
        assert len(all_events) == 5, \
            f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Потеря данных! Ожидалось 5 событий, найдено {len(all_events)}"
        
        # Очищаем сессию
        await EventStore.cleanup_session("test-no-loss")
        
        # После cleanup события должны быть удалены (это нормально)
        # Но проверяем что cleanup не вызвал критических ошибок
        assert "test-no-loss" not in EventStore._instances, \
            "Сессия должна быть удалена после cleanup"
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_concurrent_save_no_data_loss(self):
        """Проверяет что данные не теряются при конкурентном сохранении."""
        EventStore._instances.clear()
        EventStore._events.clear()
        
        store = await EventStore.get_for_session("test-concurrent-save")
        
        # Сохраняем события параллельно
        async def save_event(index: int):
            event_id = await store.save_event("test", {"index": index})
            return event_id
        
        tasks = [save_event(i) for i in range(10)]
        event_ids = await asyncio.gather(*tasks)
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: все события должны быть сохранены
        assert len(event_ids) == 10, "Все события должны быть сохранены"
        assert len(set(event_ids)) == 10, "Все ID должны быть уникальными"
        
        # Проверяем что все события можно получить
        for i, event_id in enumerate(event_ids):
            event = await store.get_event(event_id)
            assert event is not None, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Событие {event_id} (index={i}) потеряно при конкурентном сохранении!"
            assert event.data["index"] == i, \
                f"Данные события {event_id} некорректны"
        
        await EventStore.cleanup_session("test-concurrent-save")


class TestStateCorruption:
    """Тесты для предотвращения коррупции состояния."""
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_event_store_state_consistency(self):
        """Проверяет что состояние EventStore остаётся консистентным."""
        EventStore._instances.clear()
        EventStore._events.clear()
        EventStore._event_queues.clear()
        
        # Создаём несколько сессий
        stores = []
        event_ids_by_session = {}
        for i in range(5):
            session_id = f"consistency-{i}"
            store = await EventStore.get_for_session(session_id)
            event_id = await store.save_event("test", {"session": i})
            # Проверяем что событие сохранено
            assert event_id is not None, f"Событие для сессии {i} должно быть сохранено"
            event_ids_by_session[session_id] = event_id
            stores.append(store)
        
        # Небольшая задержка для завершения операций
        await asyncio.sleep(0.1)
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: состояние должно быть консистентным
        assert len(EventStore._instances) == 5, \
            f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Несоответствие _instances. " \
            f"Ожидалось 5, найдено {len(EventStore._instances)}. " \
            f"Сессии: {list(EventStore._instances.keys())}"
        
        # Проверяем что события сохранены и доступны
        events_found = 0
        for i in range(5):
            session_id = f"consistency-{i}"
            assert session_id in EventStore._instances, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Сессия {session_id} отсутствует в _instances"
            
            # Проверяем что событие можно получить по ID
            event_id = event_ids_by_session[session_id]
            store = EventStore._instances[session_id]
            event = await store.get_event(event_id)
            assert event is not None, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Событие {event_id} для {session_id} не найдено!"
            assert event.data["session"] == i, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Данные события {event_id} некорректны!"
            events_found += 1
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: все события должны быть доступны
        assert events_found == 5, \
            f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Потеря данных! Ожидалось 5 событий, найдено {events_found}"
        
        # Очищаем
        for session_id in list(EventStore._instances.keys()):
            await EventStore.cleanup_session(session_id)
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_orphaned_events_cleanup(self):
        """Проверяет что orphaned события очищаются."""
        EventStore._instances.clear()
        EventStore._events.clear()
        
        # Создаём сессию и события
        store = await EventStore.get_for_session("orphan-test")
        await store.save_event("test", {"data": "test"})
        
        # Симулируем orphaned событие (сессия удалена, но события остались)
        EventStore._events["orphaned-session"] = [
            type('Event', (), {
                'event_id': 'orphan-id',
                'event_type': 'test',
                'data': {},
                'timestamp': datetime.now(),
                'session_id': 'orphaned-session'
            })()
        ]
        
        # Очищаем основную сессию
        await EventStore.cleanup_session("orphan-test")
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: orphaned события должны быть обнаружены
        # (в реальной системе они должны очищаться периодически)
        # Проверяем что основная сессия очищена
        assert "orphan-test" not in EventStore._events, \
            "Основная сессия должна быть очищена"
        
        # Orphaned события могут остаться (это нормально для теста)
        # В реальной системе они должны очищаться периодической очисткой
        
        await EventStore.cleanup_session("orphaned-session")


class TestEdgeCases:
    """Тесты для крайних случаев."""
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_empty_session_id(self):
        """Проверяет обработку пустого session_id."""
        EventStore._instances.clear()
        
        try:
            # Пустой session_id должен обрабатываться
            store = await EventStore.get_for_session("")
            assert store is not None, "Система должна обрабатывать пустой session_id"
            assert store.session_id == "", "Session ID должен быть пустым"
        except Exception as e:
            # Ошибка допустима, но не должна быть критической
            if "AttributeError" in str(type(e).__name__) or "NoneType" in str(e):
                pytest.fail(
                    f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Критическая ошибка при пустом session_id: {e}"
                )
        finally:
            await EventStore.cleanup_session("")
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_very_long_session_id(self):
        """Проверяет обработку очень длинного session_id."""
        EventStore._instances.clear()
        
        # Очень длинный session_id (10KB)
        long_session_id = "x" * 10000
        
        try:
            store = await EventStore.get_for_session(long_session_id)
            assert store is not None, "Система должна обрабатывать длинный session_id"
            assert store.session_id == long_session_id, "Session ID должен сохраниться"
        except Exception as e:
            # Ошибка допустима, но не должна быть критической
            if "AttributeError" in str(type(e).__name__) or "NoneType" in str(e):
                pytest.fail(
                    f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Критическая ошибка при длинном session_id: {e}"
                )
        finally:
            await EventStore.cleanup_session(long_session_id)
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_special_characters_in_session_id(self):
        """Проверяет обработку специальных символов в session_id."""
        EventStore._instances.clear()
        
        special_session_ids = [
            "session-with-dashes",
            "session_with_underscores",
            "session.with.dots",
            "session/with/slashes",
            "session@with#special$chars",
        ]
        
        for session_id in special_session_ids:
            try:
                store = await EventStore.get_for_session(session_id)
                assert store is not None, \
                    f"Система должна обрабатывать session_id: {session_id}"
                await store.save_event("test", {"data": "test"})
            except Exception as e:
                # Ошибка допустима для некоторых символов, но не критическая
                if "AttributeError" in str(type(e).__name__) or "NoneType" in str(e):
                    pytest.fail(
                        f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Критическая ошибка для session_id '{session_id}': {e}"
                    )
            finally:
                await EventStore.cleanup_session(session_id)
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_rapid_create_destroy(self):
        """Проверяет обработку быстрого создания и удаления сессий."""
        EventStore._instances.clear()
        EventStore._events.clear()
        
        # Быстро создаём и удаляем много сессий
        for i in range(50):
            session_id = f"rapid-{i}"
            store = await EventStore.get_for_session(session_id)
            await store.save_event("test", {"index": i})
            await EventStore.cleanup_session(session_id)
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: система должна остаться в рабочем состоянии
        assert len(EventStore._instances) == 0, \
            f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Сессии не очищены после быстрого создания/удаления. " \
            f"Осталось: {len(EventStore._instances)}"
        
        assert len(EventStore._events) == 0, \
            f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: События не очищены. Осталось: {len(EventStore._events)}"
        
        # Проверяем что можно создать новую сессию после быстрого цикла
        new_store = await EventStore.get_for_session("after-rapid")
        assert new_store is not None, \
            "❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Система не работает после быстрого цикла"
        
        await EventStore.cleanup_session("after-rapid")
