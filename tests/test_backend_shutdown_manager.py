"""Тесты для backend/shutdown_manager.py."""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from backend.shutdown_manager import ShutdownManager, get_shutdown_manager


class TestShutdownManagerInit:
    """Тесты инициализации ShutdownManager."""
    
    @pytest.mark.backend

    
    def test_init_default_timeout(self):
        """Тест инициализации с таймаутом по умолчанию."""
        manager = ShutdownManager()
        
        assert manager.shutdown_timeout == 30
        assert manager.active_requests == 0
        assert not manager.is_shutdown_requested()
    
    @pytest.mark.backend

    
    def test_init_custom_timeout(self):
        """Тест инициализации с кастомным таймаутом."""
        manager = ShutdownManager(shutdown_timeout=60)
        
        assert manager.shutdown_timeout == 60


class TestShutdownManagerShutdown:
    """Тесты для запроса shutdown."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_request_shutdown(self):
        """Тест запроса shutdown."""
        manager = ShutdownManager()
        
        assert not manager.is_shutdown_requested()
        
        await manager.request_shutdown()
        
        assert manager.is_shutdown_requested()
    
    @pytest.mark.backend

    
    def test_is_shutdown_requested(self):
        """Тест проверки статуса shutdown."""
        manager = ShutdownManager()
        
        assert not manager.is_shutdown_requested()
        
        manager.shutdown_event.set()
        
        assert manager.is_shutdown_requested()


class TestShutdownManagerActiveRequests:
    """Тесты для отслеживания активных запросов."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_increment_active_requests(self):
        """Тест увеличения счётчика активных запросов."""
        manager = ShutdownManager()
        
        assert manager.active_requests == 0
        
        await manager.increment_active_requests()
        
        assert manager.active_requests == 1
        
        await manager.increment_active_requests()
        
        assert manager.active_requests == 2
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_decrement_active_requests(self):
        """Тест уменьшения счётчика активных запросов."""
        manager = ShutdownManager()
        
        manager.active_requests = 2
        
        await manager.decrement_active_requests()
        
        assert manager.active_requests == 1
        
        await manager.decrement_active_requests()
        
        assert manager.active_requests == 0
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_decrement_below_zero(self):
        """Тест что счётчик не может быть отрицательным."""
        manager = ShutdownManager()
        
        assert manager.active_requests == 0
        
        await manager.decrement_active_requests()
        
        assert manager.active_requests == 0
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_wait_for_active_requests_no_requests(self):
        """Тест ожидания когда нет активных запросов."""
        manager = ShutdownManager()
        
        # Не должно быть блокировки
        await manager.wait_for_active_requests()
        
        assert manager.active_requests == 0
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_wait_for_active_requests_completes(self):
        """Тест ожидания завершения активных запросов."""
        manager = ShutdownManager()
        manager.active_requests = 2
        
        # Запускаем задачу которая уменьшит счётчик
        async def decrease_requests():
            await asyncio.sleep(0.1)
            await manager.decrement_active_requests()
            await asyncio.sleep(0.1)
            await manager.decrement_active_requests()
        
        # Запускаем обе задачи параллельно
        await asyncio.gather(
            manager.wait_for_active_requests(max_wait=5),
            decrease_requests()
        )
        
        assert manager.active_requests == 0
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_wait_for_active_requests_timeout(self):
        """Тест таймаута ожидания активных запросов."""
        manager = ShutdownManager()
        manager.active_requests = 1
        
        # Ожидаем с коротким таймаутом
        await manager.wait_for_active_requests(max_wait=0.5)
        
        # Счётчик должен остаться > 0 из-за таймаута
        assert manager.active_requests == 1


class TestShutdownManagerCleanupWithTimeout:
    """Тесты для cleanup операций с таймаутом."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_cleanup_with_timeout_success(self):
        """Тест успешного выполнения cleanup операции."""
        manager = ShutdownManager()
        
        async def success_operation():
            await asyncio.sleep(0.1)
            return True
        
        result = await manager.cleanup_with_timeout(
            "test_operation",
            success_operation,
            timeout=5
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_cleanup_with_timeout_timeout(self):
        """Тест таймаута cleanup операции."""
        manager = ShutdownManager()
        
        async def slow_operation():
            await asyncio.sleep(2)
            return True
        
        result = await manager.cleanup_with_timeout(
            "slow_operation",
            slow_operation,
            timeout=0.5
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_cleanup_with_timeout_error(self):
        """Тест обработки ошибки в cleanup операции."""
        manager = ShutdownManager()
        
        async def failing_operation():
            raise Exception("Test error")
        
        result = await manager.cleanup_with_timeout(
            "failing_operation",
            failing_operation,
            timeout=5
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_cleanup_with_timeout_default_timeout(self):
        """Тест использования таймаута по умолчанию."""
        manager = ShutdownManager(shutdown_timeout=10)
        
        async def slow_operation():
            await asyncio.sleep(15)
            return True
        
        result = await manager.cleanup_with_timeout(
            "slow_operation",
            slow_operation
        )
        
        assert result is False


class TestShutdownManagerCleanupAll:
    """Тесты для cleanup_all."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_cleanup_all_success(self):
        """Тест успешного выполнения всех cleanup операций."""
        manager = ShutdownManager()
        
        with patch('backend.shutdown_manager.close_ollama_pool', new_callable=AsyncMock) as mock_close_pool, \
             patch('backend.shutdown_manager.get_cache') as mock_get_cache, \
             patch('backend.shutdown_manager.get_task_checkpointer') as mock_get_checkpointer, \
             patch('backend.shutdown_manager.get_conversation_memory') as mock_get_conv, \
             patch('backend.shutdown_manager.shutdown_dependencies') as mock_shutdown, \
             patch('backend.shutdown_manager.LocalLLM') as mock_llm, \
             patch('backend.shutdown_manager.get_config') as mock_get_config:
            
            # Настраиваем моки
            mock_config = Mock()
            mock_config.persistence_enabled = True
            mock_get_config.return_value = mock_config
            
            mock_cache = Mock()
            mock_cache.clear = Mock()
            mock_get_cache.return_value = mock_cache
            
            mock_checkpointer = Mock()
            mock_checkpointer.list_active_tasks.return_value = []
            mock_get_checkpointer.return_value = mock_checkpointer
            
            mock_conv = Mock()
            mock_conv.cleanup.return_value = {"total": 0}
            mock_get_conv.return_value = mock_conv
            
            mock_llm.shutdown_executor = Mock()
            
            await manager.cleanup_all()
            
            # Проверяем что все операции были вызваны
            mock_close_pool.assert_called_once()
            mock_cache.clear.assert_called_once()
            mock_shutdown.assert_called_once()
            mock_llm.shutdown_executor.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_cleanup_all_with_active_checkpoints(self):
        """Тест cleanup_all с активными checkpoint."""
        manager = ShutdownManager()
        
        with patch('backend.shutdown_manager.get_task_checkpointer') as mock_get_checkpointer, \
             patch('backend.shutdown_manager.get_config') as mock_get_config, \
             patch('backend.shutdown_manager.close_ollama_pool', new_callable=AsyncMock), \
             patch('backend.shutdown_manager.get_cache'), \
             patch('backend.shutdown_manager.get_conversation_memory'), \
             patch('backend.shutdown_manager.shutdown_dependencies'), \
             patch('backend.shutdown_manager.LocalLLM'):
            
            mock_config = Mock()
            mock_config.persistence_enabled = True
            mock_get_config.return_value = mock_config
            
            mock_checkpointer = Mock()
            mock_checkpointer.list_active_tasks.return_value = ["task1", "task2"]
            mock_get_checkpointer.return_value = mock_checkpointer
            
            await manager.cleanup_all()
            
            mock_checkpointer.list_active_tasks.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_cleanup_all_with_conversations(self):
        """Тест cleanup_all с диалогами для очистки."""
        manager = ShutdownManager()
        
        with patch('backend.shutdown_manager.get_conversation_memory') as mock_get_conv, \
             patch('backend.shutdown_manager.close_ollama_pool', new_callable=AsyncMock), \
             patch('backend.shutdown_manager.get_cache'), \
             patch('backend.shutdown_manager.get_task_checkpointer'), \
             patch('backend.shutdown_manager.get_config'), \
             patch('backend.shutdown_manager.shutdown_dependencies'), \
             patch('backend.shutdown_manager.LocalLLM'):
            
            mock_conv = Mock()
            mock_conv.cleanup.return_value = {"total": 5, "deleted": 3}
            mock_get_conv.return_value = mock_conv
            
            await manager.cleanup_all()
            
            mock_conv.cleanup.assert_called_once()


class TestShutdownManagerSingleton:
    """Тесты singleton паттерна."""
    
    @pytest.mark.backend

    
    def test_get_shutdown_manager_singleton(self):
        """Тест что get_shutdown_manager возвращает singleton."""
        # Сбрасываем singleton
        import backend.shutdown_manager
        backend.shutdown_manager._shutdown_manager = None
        
        manager1 = get_shutdown_manager()
        manager2 = get_shutdown_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, ShutdownManager)


class TestShutdownManagerThreadSafety:
    """Тесты потокобезопасности."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_concurrent_increment_decrement(self):
        """Тест параллельного увеличения/уменьшения счётчика."""
        manager = ShutdownManager()
        
        async def increment_multiple():
            for _ in range(10):
                await manager.increment_active_requests()
        
        async def decrement_multiple():
            await asyncio.sleep(0.05)  # Небольшая задержка
            for _ in range(10):
                await manager.decrement_active_requests()
        
        await asyncio.gather(
            increment_multiple(),
            decrement_multiple()
        )
        
        # Счётчик должен быть 0 после всех операций
        assert manager.active_requests == 0
