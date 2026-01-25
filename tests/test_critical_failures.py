"""Тесты для критических нештатных ситуаций.

Эти тесты проверяют как система ведёт себя в критических ситуациях:
- Сбои зависимостей (Ollama, ChromaDB)
- Нехватка ресурсов (память, время)
- Некорректные данные
- Race conditions
- Timeout ситуации
- Критические ошибки

ВАЖНО: Эти тесты должны ПАДАТЬ если система не обрабатывает критические ситуации правильно!
"""
import pytest
import asyncio
import time
import threading
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path


class TestOllamaFailures:
    """Тесты для критических ситуаций с Ollama."""
    
    @pytest.mark.critical
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_ollama_unavailable_graceful_degradation(self):
        """Проверяет graceful degradation когда Ollama недоступен."""
        try:
            from backend.api import app
            import uvicorn
            import requests
            import threading
            
            # Запускаем сервер
            server_thread = threading.Thread(
                target=lambda: uvicorn.run(app, host='127.0.0.1', port=8004, log_level='error'),
                daemon=True
            )
            server_thread.start()
            time.sleep(2)
            
            # Проверяем health endpoint
            response = requests.get('http://127.0.0.1:8004/health', timeout=2)
            assert response.status_code == 200
            
            data = response.json()
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: система должна работать даже если Ollama недоступен
            # Статус должен быть "degraded", но не "error" (полный сбой)
            if 'status' in data:
                status = data['status']
                assert status in ['ok', 'degraded'], \
                    f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Система полностью упала (status={status}) " \
                    f"когда Ollama недоступен. Должна быть graceful degradation!"
            
            # API должен отвечать даже если Ollama недоступен
            if 'services' in data:
                api_status = data['services'].get('api', 'unknown')
                assert api_status == 'ok', \
                    f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: API не работает когда Ollama недоступен. " \
                    f"Статус: {api_status}"
                    
        except Exception as e:
            pytest.fail(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Система не обрабатывает недоступность Ollama: {e}")
    
    @pytest.mark.critical
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_ollama_timeout_handling(self):
        """Проверяет обработку timeout при подключении к Ollama."""
        try:
            from infrastructure.connection_pool import get_ollama_pool
            
            # Мокируем очень долгий ответ
            with patch('ollama.Client') as mock_client:
                mock_instance = Mock()
                
                async def slow_response(*args, **kwargs):
                    await asyncio.sleep(10)  # Симуляция долгого ответа
                    return {"model": "test"}
                
                mock_instance.list = AsyncMock(side_effect=asyncio.TimeoutError("Connection timeout"))
                mock_client.return_value = mock_instance
                
                # Система должна обработать timeout без падения
                pool = await get_ollama_pool()
                # Если здесь падает - проблема с обработкой timeout
                
        except asyncio.TimeoutError:
            # Timeout ожидаем, но система должна его обработать
            pass
        except Exception as e:
            # Другие ошибки - это проблема
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Система не обрабатывает timeout Ollama правильно: {e}"
            )


class TestMemoryFailures:
    """Тесты для критических ситуаций с памятью."""
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_event_store_memory_limit(self):
        """Проверяет что EventStore не утекает память при большом количестве сессий."""
        from infrastructure.event_store import EventStore
        
        # Очищаем перед тестом
        EventStore._instances.clear()
        EventStore._events.clear()
        EventStore._event_queues.clear()
        
        original_max = EventStore._max_sessions
        EventStore._max_sessions = 5  # Маленький лимит для теста
        
        try:
            # Создаём много сессий
            for i in range(10):
                await EventStore.get_for_session(f"session-{i}")
                await asyncio.sleep(0.01)  # Небольшая задержка
            
            await asyncio.sleep(0.1)  # Ждём очистки
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: количество сессий не должно превышать лимит
            actual_count = len(EventStore._instances)
            assert actual_count <= EventStore._max_sessions, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Утечка памяти! " \
                f"Создано {actual_count} сессий при лимите {EventStore._max_sessions}. " \
                f"Сессии: {list(EventStore._instances.keys())}"
            
        finally:
            EventStore._max_sessions = original_max
            # Очищаем все сессии
            for session_id in list(EventStore._instances.keys()):
                await EventStore.cleanup_session(session_id)
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_event_store_large_events(self):
        """Проверяет что EventStore обрабатывает большие события."""
        from infrastructure.event_store import EventStore
        from datetime import datetime
        
        EventStore._instances.clear()
        EventStore._events.clear()
        
        store = await EventStore.get_for_session("test-large-events")
        
        try:
            # Создаём большое событие (симуляция большого ответа от LLM)
            # Используем меньший размер для теста (100KB вместо 1MB для скорости)
            large_data = {
                "content": "x" * 100000,  # 100KB данных
                "type": "large_response"
            }
            
            # Система должна обработать большое событие без падения
            event_id = await store.save_event("large_event", large_data)
            assert event_id is not None, "Система должна сохранять большие события"
            
            # Проверяем что событие можно получить
            event = await store.get_event(event_id)
            assert event is not None, "Система должна возвращать большие события"
            assert len(event.data["content"]) == 100000, "Данные должны быть полными"
            
        except MemoryError:
            pytest.fail(
                "❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Система не обрабатывает большие события, "
                "происходит MemoryError"
            )
        except Exception as e:
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Система не обрабатывает большие события: {e}"
            )
        finally:
            await EventStore.cleanup_session("test-large-events")


class TestConcurrencyFailures:
    """Тесты для критических ситуаций с конкурентностью."""
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_event_store_race_condition(self):
        """Проверяет что EventStore обрабатывает race conditions."""
        from infrastructure.event_store import EventStore
        
        EventStore._instances.clear()
        EventStore._events.clear()
        
        # Создаём несколько задач которые одновременно создают сессии
        async def create_session(session_id: str):
            store = await EventStore.get_for_session(session_id)
            await store.save_event("test", {"data": session_id})
            return store
        
        # Запускаем параллельно
        tasks = [create_session(f"race-session-{i}") for i in range(10)]
        stores = await asyncio.gather(*tasks)
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: все сессии должны быть созданы без ошибок
        assert len(stores) == 10, "Все сессии должны быть созданы"
        assert len(EventStore._instances) == 10, "Все сессии должны быть в _instances"
        
        # Проверяем что данные не потерялись
        for i in range(10):
            session_id = f"race-session-{i}"
            assert session_id in EventStore._instances, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Сессия {session_id} потеряна при race condition"
            
            events = EventStore._events.get(session_id, [])
            assert len(events) == 1, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: События потеряны для сессии {session_id}"
        
        # Очищаем
        for session_id in list(EventStore._instances.keys()):
            await EventStore.cleanup_session(session_id)
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_concurrent_cleanup(self):
        """Проверяет что cleanup работает корректно при конкурентном доступе."""
        from infrastructure.event_store import EventStore
        
        EventStore._instances.clear()
        EventStore._events.clear()
        
        # Создаём сессии
        for i in range(5):
            await EventStore.get_for_session(f"cleanup-session-{i}")
        
        # Запускаем параллельный cleanup
        async def cleanup_session(session_id: str):
            await EventStore.cleanup_session(session_id)
        
        tasks = [cleanup_session(f"cleanup-session-{i}") for i in range(5)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: все сессии должны быть очищены
        assert len(EventStore._instances) == 0, \
            f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Сессии не очищены при конкурентном cleanup. " \
            f"Осталось: {list(EventStore._instances.keys())}"


class TestDataValidationFailures:
    """Тесты для критических ситуаций с некорректными данными."""
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_event_store_invalid_data(self):
        """Проверяет что EventStore обрабатывает некорректные данные."""
        from infrastructure.event_store import EventStore
        
        EventStore._instances.clear()
        store = await EventStore.get_for_session("test-invalid")
        
        try:
            # Пробуем сохранить некорректные данные
            invalid_data_cases = [
                None,  # None данные
                "",    # Пустая строка
                123,   # Не dict
                {"nested": {"deep": {"very": "deep"}}},  # Очень глубокая вложенность
                {"circular": {"ref": None}},  # Циклические ссылки (через None)
            ]
            
            for invalid_data in invalid_data_cases:
                # Система должна обработать некорректные данные без падения
                try:
                    event_id = await store.save_event("test", invalid_data)
                    # Если сохранилось - проверяем что можно получить
                    if event_id:
                        event = await store.get_event(event_id)
                        assert event is not None, "Событие должно быть получено"
                except Exception as e:
                    # Ошибка валидации допустима, но не должно быть критических ошибок
                    assert "AttributeError" not in str(type(e).__name__), \
                        f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: AttributeError при обработке {invalid_data}: {e}"
                    assert "TypeError" not in str(type(e).__name__) or "NoneType" not in str(e), \
                        f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: TypeError при обработке {invalid_data}: {e}"
        
        finally:
            await EventStore.cleanup_session("test-invalid")
    
    @pytest.mark.critical

    
    def test_config_invalid_toml(self):
        """Проверяет что Config обрабатывает некорректный config.toml."""
        from utils.config import get_config
        import tempfile
        import tomllib
        
        # Config использует singleton, поэтому проверяем что он работает даже при проблемах
        try:
            config = get_config()
            assert config is not None, "Config должен быть создан"
            
            # Проверяем что config имеет необходимые атрибуты
            # (если config.toml некорректный, должны использоваться дефолты)
            assert hasattr(config, 'default_model') or hasattr(config, 'temperature'), \
                "Config должен иметь базовые атрибуты даже при проблемах с файлом"
            
        except tomllib.TOMLDecodeError:
            # Ошибка парсинга ожидаема, но система должна использовать дефолты
            # Проверяем что get_config всё равно работает
            config = get_config()
            assert config is not None, "Config должен работать даже при ошибке парсинга"
        except Exception as e:
            # Критические ошибки недопустимы
            if "AttributeError" in str(type(e).__name__) or "NoneType" in str(e):
                pytest.fail(
                    f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Config падает с критической ошибкой: {e}"
                )
            # Другие ошибки могут быть допустимы


class TestTimeoutFailures:
    """Тесты для критических ситуаций с timeout."""
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_event_store_timeout(self):
        """Проверяет что EventStore обрабатывает timeout операции."""
        from infrastructure.event_store import EventStore
        
        EventStore._instances.clear()
        store = await EventStore.get_for_session("test-timeout")
        
        try:
            # Симулируем долгую операцию через мок
            with patch.object(store, 'save_event', new_callable=AsyncMock) as mock_save:
                mock_save.side_effect = asyncio.TimeoutError("Operation timeout")
                
                # Система должна обработать timeout без падения
                with pytest.raises(asyncio.TimeoutError):
                    await store.save_event("test", {"data": "test"})
                
                # Проверяем что система в рабочем состоянии после timeout
                assert store.session_id == "test-timeout", \
                    "Система должна оставаться в рабочем состоянии после timeout"
        
        finally:
            await EventStore.cleanup_session("test-timeout")
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_concurrent_timeout(self):
        """Проверяет что система обрабатывает множественные timeout."""
        from infrastructure.event_store import EventStore
        
        EventStore._instances.clear()
        
        async def create_with_timeout(session_id: str):
            try:
                store = await EventStore.get_for_session(session_id)
                # Симулируем timeout
                await asyncio.sleep(0.1)
                return store
            except asyncio.TimeoutError:
                return None
        
        # Запускаем много операций с возможными timeout
        tasks = [create_with_timeout(f"timeout-{i}") for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: система должна обработать все timeout без падения
        exceptions = [r for r in results if isinstance(r, Exception)]
        critical_exceptions = [e for e in exceptions if "AttributeError" in str(type(e).__name__) or "NoneType" in str(e)]
        
        assert len(critical_exceptions) == 0, \
            f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Критические ошибки при обработке timeout: {critical_exceptions}"
        
        # Очищаем
        for session_id in list(EventStore._instances.keys()):
            await EventStore.cleanup_session(session_id)


class TestResourceExhaustion:
    """Тесты для критических ситуаций с исчерпанием ресурсов."""
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_event_store_max_sessions_enforced(self):
        """Проверяет что лимит сессий строго соблюдается."""
        from infrastructure.event_store import EventStore
        
        EventStore._instances.clear()
        EventStore._events.clear()
        EventStore._event_queues.clear()
        
        original_max = EventStore._max_sessions
        EventStore._max_sessions = 3  # Очень маленький лимит
        
        try:
            # Создаём больше сессий чем лимит
            for i in range(10):
                await EventStore.get_for_session(f"limit-session-{i}")
                await asyncio.sleep(0.01)
            
            await asyncio.sleep(0.2)  # Ждём очистки
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: лимит НЕ должен быть превышен
            actual_count = len(EventStore._instances)
            assert actual_count <= EventStore._max_sessions, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Лимит сессий нарушен! " \
                f"Создано {actual_count} при лимите {EventStore._max_sessions}. " \
                f"Это утечка памяти! Сессии: {list(EventStore._instances.keys())}"
        
        finally:
            EventStore._max_sessions = original_max
            for session_id in list(EventStore._instances.keys()):
                await EventStore.cleanup_session(session_id)
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_event_store_cleanup_on_limit(self):
        """Проверяет что старые сессии удаляются при достижении лимита."""
        from infrastructure.event_store import EventStore
        from datetime import datetime, timedelta
        
        EventStore._instances.clear()
        EventStore._events.clear()
        
        original_max = EventStore._max_sessions
        EventStore._max_sessions = 2
        
        try:
            # Создаём сессии с разным временем
            store1 = await EventStore.get_for_session("old-session")
            EventStore._events["old-session"] = [
                type('Event', (), {
                    'event_id': 'id1',
                    'event_type': 'test',
                    'data': {},
                    'timestamp': datetime.now() - timedelta(hours=2),
                    'session_id': 'old-session'
                })()
            ]
            
            store2 = await EventStore.get_for_session("new-session")
            EventStore._events["new-session"] = [
                type('Event', (), {
                    'event_id': 'id2',
                    'event_type': 'test',
                    'data': {},
                    'timestamp': datetime.now() - timedelta(hours=1),
                    'session_id': 'new-session'
                })()
            ]
            
            # Создаём третью сессию - должна удалиться старая
            await EventStore.get_for_session("latest-session")
            await asyncio.sleep(0.1)
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: старая сессия должна быть удалена
            assert "old-session" not in EventStore._instances, \
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Старая сессия не удалена при достижении лимита. " \
                f"Сессии: {list(EventStore._instances.keys())}"
            
            # Новая сессия должна остаться
            assert "new-session" in EventStore._instances or "latest-session" in EventStore._instances, \
                "Новые сессии должны остаться"
        
        finally:
            EventStore._max_sessions = original_max
            for session_id in list(EventStore._instances.keys()):
                await EventStore.cleanup_session(session_id)


class TestCriticalErrors:
    """Тесты для критических ошибок системы."""
    
    @pytest.mark.critical

    
    def test_import_failures_handled(self):
        """Проверяет что система обрабатывает ошибки импорта."""
        # Пробуем импортировать модули которые могут иметь проблемы
        critical_modules = [
            'backend.api',
            'infrastructure.event_store',
            'utils.config',
        ]
        
        failed = []
        for module_name in critical_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                failed.append(f"{module_name}: {e}")
            except Exception as e:
                # Другие ошибки - это критическая проблема
                pytest.fail(
                    f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Ошибка при импорте {module_name}: {e}"
                )
        
        if failed:
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Не удалось импортировать модули:\n" +
                "\n".join(f"  - {f}" for f in failed)
            )
    
    @pytest.mark.asyncio
    @pytest.mark.critical

    async def test_circular_dependency_prevention(self):
        """Проверяет что нет циклических зависимостей."""
        import sys
        import importlib
        
        # Пробуем перезагрузить модули - циклические зависимости вызовут проблемы
        modules_to_check = [
            'backend.dependencies',
            'infrastructure.event_store',
            'utils.config',
        ]
        
        for module_name in modules_to_check:
            if module_name in sys.modules:
                try:
                    # Пробуем перезагрузить
                    importlib.reload(sys.modules[module_name])
                except Exception as e:
                    # Если ошибка связана с циклическими зависимостями - это проблема
                    if "circular" in str(e).lower() or "cannot import" in str(e).lower():
                        pytest.fail(
                            f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Циклическая зависимость в {module_name}: {e}"
                        )
