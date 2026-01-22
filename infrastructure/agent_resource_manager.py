"""Управление ресурсами агентов.

Ограничивает количество одновременных вызовов агентов для предотвращения
перегрузки системы и исчерпания ресурсов.
"""
import asyncio
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from utils.logger import get_logger
from utils.config import get_config

logger = get_logger()


@dataclass
class AgentUsage:
    """Информация об использовании агента."""
    agent_name: str
    started_at: datetime
    task_id: Optional[str] = None


class AgentResourceManager:
    """Менеджер ресурсов для контроля одновременных вызовов агентов.
    
    Использует asyncio.Semaphore для ограничения количества одновременных
    вызовов агентов. Поддерживает мониторинг использования ресурсов.
    
    Особенности:
    - Ограничение количества одновременных агентов
    - Отслеживание активных вызовов
    - Автоматическая очистка при превышении лимита
    - Настраивается через config.toml
    """
    
    _instance: Optional['AgentResourceManager'] = None
    _lock = asyncio.Lock()
    
    def __init__(self, max_concurrent: int = 5):
        """Инициализирует менеджер ресурсов.
        
        Args:
            max_concurrent: Максимальное количество одновременных агентов
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_agents: Dict[str, AgentUsage] = {}
        self._total_acquired = 0
        self._total_released = 0
        
        logger.info(f"✅ AgentResourceManager инициализирован (max_concurrent: {max_concurrent})")
    
    @classmethod
    async def get_instance(cls) -> 'AgentResourceManager':
        """Возвращает глобальный экземпляр менеджера ресурсов.
        
        Создаёт экземпляр при первом вызове на основе конфигурации.
        
        Returns:
            Экземпляр AgentResourceManager
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    config = get_config()
                    # Получаем настройки из config.toml
                    resource_config = config._config_data.get("agent_resources", {})
                    max_concurrent = resource_config.get("max_concurrent_agents", 5)
                    cls._instance = cls(max_concurrent=max_concurrent)
        return cls._instance
    
    async def acquire(
        self,
        agent_name: str,
        task_id: Optional[str] = None
    ) -> 'AgentResourceContext':
        """Получает доступ к агенту (acquire semaphore).
        
        Блокирует выполнение если достигнут лимит одновременных агентов.
        Автоматически освобождает ресурс при выходе из контекста.
        
        Args:
            agent_name: Имя агента (intent, planner, coder, etc.)
            task_id: ID задачи для отслеживания (опционально)
            
        Returns:
            AgentResourceContext для использования в async with
            
        Example:
            async with await resource_manager.acquire("coder", task_id="task_123"):
                # Выполнение работы агента
                result = await agent.generate_code(...)
        """
        await self.semaphore.acquire()
        self._total_acquired += 1
        
        # Создаём уникальный ключ для отслеживания
        usage_key = f"{agent_name}_{int(time.time() * 1000000)}"
        usage = AgentUsage(
            agent_name=agent_name,
            started_at=datetime.now(),
            task_id=task_id
        )
        self.active_agents[usage_key] = usage
        
        logger.debug(
            f"🔒 Ресурс агента '{agent_name}' получен "
            f"(активных: {len(self.active_agents)}/{self.max_concurrent})"
        )
        
        return AgentResourceContext(self, usage_key)
    
    def _release(self, usage_key: str) -> None:
        """Освобождает ресурс агента.
        
        Args:
            usage_key: Ключ использования для освобождения
        """
        if usage_key in self.active_agents:
            usage = self.active_agents.pop(usage_key)
            duration = (datetime.now() - usage.started_at).total_seconds()
            self._total_released += 1
            
            logger.debug(
                f"🔓 Ресурс агента '{usage.agent_name}' освобождён "
                f"(длительность: {duration:.2f}s, активных: {len(self.active_agents)}/{self.max_concurrent})"
            )
        
        self.semaphore.release()
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику использования ресурсов.
        
        Returns:
            Словарь со статистикой
        """
        return {
            "max_concurrent": self.max_concurrent,
            "active_agents": len(self.active_agents),
            "available_slots": self.max_concurrent - len(self.active_agents),
            "total_acquired": self._total_acquired,
            "total_released": self._total_released,
            "active_usage": [
                {
                    "agent_name": usage.agent_name,
                    "task_id": usage.task_id,
                    "duration_seconds": (datetime.now() - usage.started_at).total_seconds()
                }
                for usage in self.active_agents.values()
            ]
        }
    
    async def cleanup_oldest(self) -> None:
        """Освобождает самый старый активный агент (если нужно).
        
        Используется при необходимости освободить ресурсы.
        """
        if not self.active_agents:
            return
        
        # Находим самый старый активный агент
        oldest_key = min(
            self.active_agents.items(),
            key=lambda x: x[1].started_at
        )[0]
        
        logger.warning(
            f"⚠️ Принудительное освобождение ресурса агента '{self.active_agents[oldest_key].agent_name}' "
            f"(превышен лимит)"
        )
        self._release(oldest_key)


class AgentResourceContext:
    """Контекстный менеджер для автоматического освобождения ресурсов.
    
    Используется в async with для гарантированного освобождения ресурса.
    """
    
    def __init__(self, manager: AgentResourceManager, usage_key: str):
        """Инициализирует контекст.
        
        Args:
            manager: Менеджер ресурсов
            usage_key: Ключ использования
        """
        self.manager = manager
        self.usage_key = usage_key
    
    async def __aenter__(self) -> 'AgentResourceContext':
        """Вход в контекст."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Выход из контекста - освобождаем ресурс."""
        self.manager._release(self.usage_key)


# === Удобные функции для импорта ===

async def get_resource_manager() -> AgentResourceManager:
    """Возвращает глобальный менеджер ресурсов.
    
    Returns:
        Экземпляр AgentResourceManager
    """
    return await AgentResourceManager.get_instance()


async def acquire_agent_resource(
    agent_name: str,
    task_id: Optional[str] = None
) -> AgentResourceContext:
    """Получает доступ к ресурсу агента.
    
    Args:
        agent_name: Имя агента
        task_id: ID задачи (опционально)
        
    Returns:
        AgentResourceContext для использования в async with
    """
    manager = await get_resource_manager()
    return await manager.acquire(agent_name, task_id)
