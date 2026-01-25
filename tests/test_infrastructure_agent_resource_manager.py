"""Тесты для infrastructure/agent_resource_manager.py."""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from infrastructure.agent_resource_manager import (
    AgentResourceManager,
    AgentResourceContext,
    AgentUsage,
    get_resource_manager,
    acquire_agent_resource
)


class TestAgentUsage:
    """Тесты для AgentUsage."""
    
    @pytest.mark.infrastructure

    
    def test_agent_usage_creation(self):
        """Тест создания AgentUsage."""
        usage = AgentUsage(
            agent_name="test-agent",
            started_at=datetime.now(),
            task_id="task-123"
        )
        
        assert usage.agent_name == "test-agent"
        assert usage.task_id == "task-123"
        assert isinstance(usage.started_at, datetime)


class TestAgentResourceManagerInit:
    """Тесты инициализации AgentResourceManager."""
    
    @pytest.mark.infrastructure

    
    def test_init_default_max_concurrent(self):
        """Тест инициализации с дефолтным max_concurrent."""
        manager = AgentResourceManager()
        
        assert manager.max_concurrent == 5
        assert len(manager.active_agents) == 0
        assert manager._total_acquired == 0
        assert manager._total_released == 0
    
    @pytest.mark.infrastructure

    
    def test_init_custom_max_concurrent(self):
        """Тест инициализации с кастомным max_concurrent."""
        manager = AgentResourceManager(max_concurrent=10)
        
        assert manager.max_concurrent == 10
        assert manager.semaphore._value == 10


class TestAgentResourceManagerSingleton:
    """Тесты singleton паттерна."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_instance_creates_once(self):
        """Тест что get_instance создаёт экземпляр один раз."""
        # Сбрасываем singleton
        AgentResourceManager._instance = None
        
        manager1 = await AgentResourceManager.get_instance()
        manager2 = await AgentResourceManager.get_instance()
        
        assert manager1 is manager2
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_instance_from_config(self):
        """Тест что get_instance читает конфигурацию."""
        # Сбрасываем singleton
        AgentResourceManager._instance = None
        
        with patch('infrastructure.agent_resource_manager.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config._config_data = {
                "agent_resources": {
                    "max_concurrent_agents": 10
                }
            }
            mock_get_config.return_value = mock_config
            
            manager = await AgentResourceManager.get_instance()
            
            assert manager.max_concurrent == 10
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_instance_default_config(self):
        """Тест что используется значение по умолчанию если конфиг не задан."""
        # Сбрасываем singleton
        AgentResourceManager._instance = None
        
        with patch('infrastructure.agent_resource_manager.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config._config_data = {}
            mock_get_config.return_value = mock_config
            
            manager = await AgentResourceManager.get_instance()
            
            assert manager.max_concurrent == 5  # Значение по умолчанию


class TestAgentResourceManagerAcquire:
    """Тесты для acquire."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_acquire_success(self):
        """Тест успешного получения ресурса."""
        manager = AgentResourceManager(max_concurrent=2)
        
        context = await manager.acquire("test-agent", "task-123")
        
        assert isinstance(context, AgentResourceContext)
        assert len(manager.active_agents) == 1
        assert manager._total_acquired == 1
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_acquire_tracks_usage(self):
        """Тест что использование отслеживается."""
        manager = AgentResourceManager(max_concurrent=2)
        
        context = await manager.acquire("test-agent", "task-123")
        
        assert len(manager.active_agents) == 1
        usage = list(manager.active_agents.values())[0]
        assert usage.agent_name == "test-agent"
        assert usage.task_id == "task-123"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_acquire_blocks_when_full(self):
        """Тест что acquire блокирует когда достигнут лимит."""
        manager = AgentResourceManager(max_concurrent=1)
        
        # Получаем первый ресурс
        context1 = await manager.acquire("agent-1")
        
        # Пытаемся получить второй - должен заблокироваться
        acquire_task = asyncio.create_task(manager.acquire("agent-2"))
        
        # Даём немного времени
        await asyncio.sleep(0.1)
        
        # Второй acquire должен быть в ожидании
        assert not acquire_task.done()
        
        # Освобождаем первый
        await context1.__aexit__(None, None, None)
        
        # Теперь второй должен завершиться
        await asyncio.sleep(0.1)
        assert acquire_task.done()


class TestAgentResourceManagerRelease:
    """Тесты для release."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_release_success(self):
        """Тест успешного освобождения ресурса."""
        manager = AgentResourceManager(max_concurrent=2)
        
        context = await manager.acquire("test-agent", "task-123")
        usage_key = context.usage_key
        
        manager._release(usage_key)
        
        assert len(manager.active_agents) == 0
        assert manager._total_released == 1
        assert manager.semaphore._value == 2  # Semaphore освобождён
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_release_unknown_key(self):
        """Тест освобождения несуществующего ключа."""
        manager = AgentResourceManager(max_concurrent=2)
        
        # Не должно падать
        manager._release("unknown-key")
        
        # Semaphore всё равно должен быть освобождён (проверяем через stats)
        stats = manager.get_stats()
        assert stats["available_slots"] == 2


class TestAgentResourceContext:
    """Тесты для AgentResourceContext."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_context_manager_enter_exit(self):
        """Тест работы контекстного менеджера."""
        manager = AgentResourceManager(max_concurrent=2)
        
        context = await manager.acquire("test-agent", "task-123")
        usage_key = context.usage_key
        
        assert len(manager.active_agents) == 1
        
        # Выходим из контекста
        await context.__aexit__(None, None, None)
        
        assert len(manager.active_agents) == 0
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_context_manager_async_with(self):
        """Тест использования в async with."""
        manager = AgentResourceManager(max_concurrent=2)
        
        async with await manager.acquire("test-agent", "task-123") as context:
            assert isinstance(context, AgentResourceContext)
            assert len(manager.active_agents) == 1
        
        # После выхода из контекста ресурс должен быть освобождён
        assert len(manager.active_agents) == 0


class TestAgentResourceManagerStats:
    """Тесты для get_stats."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_stats_empty(self):
        """Тест статистики когда нет активных агентов."""
        manager = AgentResourceManager(max_concurrent=5)
        
        stats = manager.get_stats()
        
        assert stats["max_concurrent"] == 5
        assert stats["active_agents"] == 0
        assert stats["available_slots"] == 5
        assert stats["total_acquired"] == 0
        assert stats["total_released"] == 0
        assert len(stats["active_usage"]) == 0
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_stats_with_active(self):
        """Тест статистики с активными агентами."""
        manager = AgentResourceManager(max_concurrent=5)
        
        context = await manager.acquire("test-agent", "task-123")
        
        stats = manager.get_stats()
        
        assert stats["active_agents"] == 1
        assert stats["available_slots"] == 4
        assert stats["total_acquired"] == 1
        assert len(stats["active_usage"]) == 1
        assert stats["active_usage"][0]["agent_name"] == "test-agent"
        assert stats["active_usage"][0]["task_id"] == "task-123"


class TestAgentResourceManagerCleanup:
    """Тесты для cleanup_oldest."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_cleanup_oldest_empty(self):
        """Тест cleanup когда нет активных агентов."""
        manager = AgentResourceManager(max_concurrent=2)
        
        # Не должно падать
        await manager.cleanup_oldest()
        
        assert len(manager.active_agents) == 0
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_cleanup_oldest_removes_oldest(self):
        """Тест что cleanup удаляет самый старый агент."""
        manager = AgentResourceManager(max_concurrent=5)
        
        # Создаём несколько агентов с небольшой задержкой
        context1 = await manager.acquire("agent-1", "task-1")
        await asyncio.sleep(0.01)  # Небольшая задержка
        context2 = await manager.acquire("agent-2", "task-2")
        
        assert len(manager.active_agents) == 2
        
        # Очищаем самый старый
        await manager.cleanup_oldest()
        
        # Должен остаться только agent-2
        assert len(manager.active_agents) == 1
        remaining_usage = list(manager.active_agents.values())[0]
        assert remaining_usage.agent_name == "agent-2"


class TestConvenienceFunctions:
    """Тесты для удобных функций."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_resource_manager(self):
        """Тест функции get_resource_manager."""
        # Сбрасываем singleton
        AgentResourceManager._instance = None
        
        with patch('infrastructure.agent_resource_manager.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config._config_data = {}
            mock_get_config.return_value = mock_config
            
            manager = await get_resource_manager()
            
            assert isinstance(manager, AgentResourceManager)
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_acquire_agent_resource_function(self):
        """Тест функции acquire_agent_resource."""
        # Сбрасываем singleton
        AgentResourceManager._instance = None
        
        with patch('infrastructure.agent_resource_manager.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config._config_data = {}
            mock_get_config.return_value = mock_config
            
            context = await acquire_agent_resource("test-agent", "task-123")
            
            assert isinstance(context, AgentResourceContext)
            
            # Проверяем что ресурс получен
            manager = await get_resource_manager()
            assert len(manager.active_agents) == 1


class TestAgentResourceManagerConcurrency:
    """Тесты для конкурентного доступа."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_concurrent_acquire(self):
        """Тест параллельного получения ресурсов."""
        manager = AgentResourceManager(max_concurrent=3)
        
        async def acquire_agent(name):
            async with await manager.acquire(name, f"task-{name}"):
                await asyncio.sleep(0.1)
        
        # Запускаем несколько параллельных acquire
        await asyncio.gather(
            acquire_agent("agent-1"),
            acquire_agent("agent-2"),
            acquire_agent("agent-3")
        )
        
        # Все должны завершиться успешно
        assert manager._total_acquired == 3
        assert manager._total_released == 3
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_concurrent_acquire_with_limit(self):
        """Тест что лимит соблюдается при параллельном доступе."""
        manager = AgentResourceManager(max_concurrent=2)
        
        acquired_count = 0
        
        async def acquire_and_count(name):
            nonlocal acquired_count
            async with await manager.acquire(name, f"task-{name}"):
                acquired_count += 1
                await asyncio.sleep(0.1)
                acquired_count -= 1
        
        # Запускаем 5 агентов, но лимит только 2
        tasks = [acquire_and_count(f"agent-{i}") for i in range(5)]
        await asyncio.gather(*tasks)
        
        # Все должны завершиться, но одновременно работало максимум 2
        assert manager._total_acquired == 5
        assert manager._total_released == 5
