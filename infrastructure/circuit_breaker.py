"""Circuit Breaker для агентов.

Предотвращает каскадные сбои при повторяющихся ошибках агентов,
временно отключая вызовы при превышении порога ошибок.
"""
import asyncio
import time
from enum import Enum
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from utils.logger import get_logger
from utils.config import get_config

logger = get_logger()


class CircuitState(Enum):
    """Состояния circuit breaker."""
    CLOSED = "closed"  # Нормальная работа
    OPEN = "open"  # Отключен из-за ошибок
    HALF_OPEN = "half_open"  # Тестирование восстановления


@dataclass
class CircuitBreakerStats:
    """Статистика circuit breaker."""
    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state: CircuitState = CircuitState.CLOSED
    opened_at: Optional[datetime] = None


class CircuitBreaker:
    """Circuit Breaker для защиты от каскадных сбоев.
    
    При превышении порога ошибок временно отключает вызовы,
    позволяя системе восстановиться.
    
    Особенности:
    - Отслеживание ошибок и успешных вызовов
    - Автоматическое переключение состояний
    - Настраиваемые пороги через config.toml
    """
    
    _breakers: Dict[str, 'CircuitBreaker'] = {}
    _lock = asyncio.Lock()
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2
    ):
        """Инициализирует circuit breaker.
        
        Args:
            name: Имя circuit breaker (обычно имя агента)
            failure_threshold: Порог ошибок для открытия (default: 5)
            recovery_timeout: Время ожидания перед попыткой восстановления (секунды, default: 30)
            success_threshold: Количество успешных вызовов для закрытия (default: 2)
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.stats = CircuitBreakerStats()
    
    @classmethod
    async def get_breaker(
        cls,
        name: str,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[float] = None,
        success_threshold: Optional[int] = None
    ) -> 'CircuitBreaker':
        """Возвращает circuit breaker для имени.
        
        Args:
            name: Имя circuit breaker
            failure_threshold: Порог ошибок (если None, берётся из config)
            recovery_timeout: Время восстановления (если None, берётся из config)
            success_threshold: Порог успешных вызовов (если None, берётся из config)
            
        Returns:
            Экземпляр CircuitBreaker
        """
        if name not in cls._breakers:
            async with cls._lock:
                if name not in cls._breakers:
                    # Получаем настройки из config.toml
                    config = get_config()
                    circuit_config = config._config_data.get("circuit_breaker", {})
                    
                    failure_threshold = failure_threshold or circuit_config.get("failure_threshold", 5)
                    recovery_timeout = recovery_timeout or circuit_config.get("recovery_timeout", 30.0)
                    success_threshold = success_threshold or circuit_config.get("success_threshold", 2)
                    
                    cls._breakers[name] = cls(
                        name=name,
                        failure_threshold=failure_threshold,
                        recovery_timeout=recovery_timeout,
                        success_threshold=success_threshold
                    )
        return cls._breakers[name]
    
    def _should_attempt_call(self) -> bool:
        """Проверяет, можно ли выполнить вызов.
        
        Returns:
            True если вызов разрешён, False если circuit открыт
        """
        now = datetime.now()
        
        if self.stats.state == CircuitState.CLOSED:
            return True
        
        elif self.stats.state == CircuitState.OPEN:
            # Проверяем, прошло ли достаточно времени для попытки восстановления
            if self.stats.opened_at:
                elapsed = (now - self.stats.opened_at).total_seconds()
                if elapsed >= self.recovery_timeout:
                    # Переходим в HALF_OPEN для тестирования
                    self.stats.state = CircuitState.HALF_OPEN
                    logger.info(f"🔄 Circuit breaker '{self.name}' переходит в HALF_OPEN")
                    return True
            return False
        
        elif self.stats.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Выполняет функцию через circuit breaker.
        
        Args:
            func: Функция для выполнения
            *args: Аргументы функции
            **kwargs: Ключевые аргументы функции
            
        Returns:
            Результат выполнения функции
            
        Raises:
            CircuitBreakerOpenError: Если circuit открыт
            Exception: Ошибка выполнения функции
        """
        if not self._should_attempt_call():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' открыт. "
                f"Ошибок: {self.stats.failures}/{self.failure_threshold}"
            )
        
        try:
            # Выполняем функцию
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Успешный вызов
            self._on_success()
            return result
            
        except Exception as e:
            # Ошибка при вызове
            self._on_failure()
            raise
    
    def _on_success(self) -> None:
        """Обрабатывает успешный вызов."""
        self.stats.successes += 1
        self.stats.last_success_time = datetime.now()
        
        if self.stats.state == CircuitState.HALF_OPEN:
            # Если достаточно успешных вызовов, закрываем circuit
            if self.stats.successes >= self.success_threshold:
                self.stats.state = CircuitState.CLOSED
                self.stats.failures = 0
                self.stats.opened_at = None
                logger.info(f"✅ Circuit breaker '{self.name}' закрыт (восстановлен)")
        
        elif self.stats.state == CircuitState.CLOSED:
            # Сбрасываем счётчик ошибок при успешных вызовах
            if self.stats.failures > 0:
                self.stats.failures = 0
    
    def _on_failure(self) -> None:
        """Обрабатывает ошибку."""
        self.stats.failures += 1
        self.stats.last_failure_time = datetime.now()
        
        if self.stats.state == CircuitState.CLOSED:
            # Проверяем, не превышен ли порог
            if self.stats.failures >= self.failure_threshold:
                self.stats.state = CircuitState.OPEN
                self.stats.opened_at = datetime.now()
                logger.warning(
                    f"⚠️ Circuit breaker '{self.name}' открыт "
                    f"(ошибок: {self.stats.failures}/{self.failure_threshold})"
                )
        
        elif self.stats.state == CircuitState.HALF_OPEN:
            # При ошибке в HALF_OPEN возвращаемся в OPEN
            self.stats.state = CircuitState.OPEN
            self.stats.opened_at = datetime.now()
            self.stats.successes = 0
            logger.warning(f"⚠️ Circuit breaker '{self.name}' снова открыт после ошибки")
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику circuit breaker.
        
        Returns:
            Словарь со статистикой
        """
        return {
            "name": self.name,
            "state": self.stats.state.value,
            "failures": self.stats.failures,
            "successes": self.stats.successes,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": (
                self.stats.last_failure_time.isoformat()
                if self.stats.last_failure_time else None
            ),
            "last_success_time": (
                self.stats.last_success_time.isoformat()
                if self.stats.last_success_time else None
            ),
            "opened_at": (
                self.stats.opened_at.isoformat()
                if self.stats.opened_at else None
            )
        }
    
    def reset(self) -> None:
        """Сбрасывает circuit breaker в начальное состояние."""
        self.stats = CircuitBreakerStats()
        logger.info(f"🔄 Circuit breaker '{self.name}' сброшен")


class CircuitBreakerOpenError(Exception):
    """Исключение при открытом circuit breaker."""
    pass


# === Удобные функции для импорта ===

async def get_circuit_breaker(
    name: str,
    failure_threshold: Optional[int] = None,
    recovery_timeout: Optional[float] = None
) -> CircuitBreaker:
    """Возвращает circuit breaker для имени.
    
    Args:
        name: Имя circuit breaker
        failure_threshold: Порог ошибок
        recovery_timeout: Время восстановления
        
    Returns:
        Экземпляр CircuitBreaker
    """
    return await CircuitBreaker.get_breaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout
    )
