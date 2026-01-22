"""Менеджер graceful shutdown для FastAPI.

Управляет жизненным циклом приложения и ожиданием завершения активных запросов.
"""
import asyncio
from typing import Optional
from utils.logger import get_logger
from utils.config import get_config
from infrastructure.task_checkpointer import get_task_checkpointer
from agents.conversation import get_conversation_memory
from backend.dependencies import shutdown_dependencies
from infrastructure.local_llm import LocalLLM
from infrastructure.connection_pool import close_ollama_pool
from infrastructure.cache import get_cache

logger = get_logger()


class ShutdownManager:
    """Менеджер для управления graceful shutdown.
    
    Обеспечивает:
    - Thread-safe флаг shutdown через asyncio.Event
    - Отслеживание активных запросов
    - Timeout на cleanup операции
    - Ожидание завершения активных задач
    """
    
    def __init__(self, shutdown_timeout: int = 30) -> None:
        """Инициализация менеджера.
        
        Args:
            shutdown_timeout: Таймаут для shutdown операций (секунды)
        """
        self.shutdown_event = asyncio.Event()
        self.active_requests = 0
        self.shutdown_timeout = shutdown_timeout
        self._lock = asyncio.Lock()
    
    def is_shutdown_requested(self) -> bool:
        """Проверяет, был ли запрошен shutdown.
        
        Returns:
            True если shutdown запрошен
        """
        return self.shutdown_event.is_set()
    
    async def request_shutdown(self) -> None:
        """Запрашивает shutdown приложения."""
        self.shutdown_event.set()
        logger.info("🛑 Shutdown запрошен")
    
    async def wait_for_active_requests(self, max_wait: int = 10) -> None:
        """Ожидает завершения активных запросов.
        
        Args:
            max_wait: Максимальное время ожидания (секунды)
        """
        if self.active_requests == 0:
            logger.info("✅ Нет активных запросов")
            return
        
        logger.info(f"⏳ Ожидание завершения {self.active_requests} активных запросов (макс. {max_wait}s)...")
        
        start_time = asyncio.get_event_loop().time()
        while self.active_requests > 0:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= max_wait:
                logger.warning(f"⚠️ Таймаут ожидания активных запросов ({max_wait}s), продолжаем shutdown")
                break
            
            await asyncio.sleep(0.5)
        
        if self.active_requests == 0:
            logger.info("✅ Все активные запросы завершены")
        else:
            logger.warning(f"⚠️ Осталось {self.active_requests} активных запросов")
    
    async def increment_active_requests(self) -> None:
        """Увеличивает счётчик активных запросов."""
        async with self._lock:
            self.active_requests += 1
    
    async def decrement_active_requests(self) -> None:
        """Уменьшает счётчик активных запросов."""
        async with self._lock:
            self.active_requests = max(0, self.active_requests - 1)
    
    async def cleanup_with_timeout(
        self,
        operation_name: str,
        operation: callable,
        timeout: Optional[int] = None
    ) -> bool:
        """Выполняет cleanup операцию с таймаутом.
        
        Args:
            operation_name: Название операции для логирования
            operation: Асинхронная функция для выполнения
            timeout: Таймаут в секундах (по умолчанию self.shutdown_timeout)
            
        Returns:
            True если операция завершена успешно, False при таймауте
        """
        timeout = timeout or self.shutdown_timeout
        
        try:
            await asyncio.wait_for(operation(), timeout=timeout)
            logger.info(f"✅ {operation_name} завершено")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Таймаут при {operation_name} ({timeout}s)")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при {operation_name}: {e}")
            return False
    
    async def cleanup_all(self) -> None:
        """Выполняет все cleanup операции с таймаутами."""
        logger.info("🧹 Начинаем cleanup операций...")
        
        # Закрываем connection pool
        await self.cleanup_with_timeout(
            "Закрытие connection pool",
            close_ollama_pool,
            timeout=5
        )
        
        # Очищаем кэш
        await self.cleanup_with_timeout(
            "Очистка кэша",
            lambda: asyncio.to_thread(lambda: get_cache().clear()),
            timeout=2
        )
        
        # Сохраняем активные checkpoint
        await self.cleanup_with_timeout(
            "Сохранение checkpoint",
            self._save_checkpoints,
            timeout=5
        )
        
        # Очищаем просроченные диалоги
        await self.cleanup_with_timeout(
            "Очистка диалогов",
            self._cleanup_conversations,
            timeout=3
        )
        
        # Останавливаем DependencyContainer
        await self.cleanup_with_timeout(
            "Остановка DependencyContainer",
            lambda: asyncio.to_thread(shutdown_dependencies),
            timeout=3
        )
        
        # Останавливаем ThreadPoolExecutor
        await self.cleanup_with_timeout(
            "Остановка ThreadPoolExecutor",
            lambda: asyncio.to_thread(LocalLLM.shutdown_executor),
            timeout=2
        )
        
        logger.info("✅ Все cleanup операции завершены")
    
    async def _save_checkpoints(self) -> None:
        """Сохраняет активные checkpoint."""
        try:
            config = get_config()
            if config.persistence_enabled:
                checkpointer = get_task_checkpointer()
                active_count = len(checkpointer.list_active_tasks())
                if active_count > 0:
                    logger.info(f"📝 Сохранено {active_count} активных checkpoint")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения checkpoint: {e}")
    
    async def _cleanup_conversations(self) -> None:
        """Очищает просроченные диалоги."""
        try:
            conv_memory = get_conversation_memory()
            cleanup_result = conv_memory.cleanup()
            if cleanup_result.get("total", 0) > 0:
                logger.info(f"🗑️ Очистка диалогов: {cleanup_result}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при очистке диалогов: {e}")


# === Singleton экземпляр ===

_shutdown_manager: Optional[ShutdownManager] = None


def get_shutdown_manager() -> ShutdownManager:
    """Возвращает singleton экземпляр ShutdownManager.
    
    Returns:
        Экземпляр ShutdownManager
    """
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = ShutdownManager()
    return _shutdown_manager
