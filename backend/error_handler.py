"""Утилиты для обработки ошибок и retry логики."""
import asyncio
import time
import functools
from typing import TypeVar, Callable, Any, Optional, Type
from utils.logger import get_logger

logger = get_logger()

T = TypeVar('T')


class RetryConfig:
    """Конфигурация для retry логики."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retriable_exceptions: tuple[Type[Exception], ...] = (Exception,)
    ):
        """Инициализация конфигурации retry.
        
        Args:
            max_attempts: Максимальное количество попыток
            initial_delay: Начальная задержка между попытками (секунды)
            max_delay: Максимальная задержка между попытками (секунды)
            exponential_base: Основание для экспоненциального увеличения задержки
            jitter: Добавлять ли случайное значение к задержке
            retriable_exceptions: Кортеж исключений, которые стоит повторить
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retriable_exceptions = retriable_exceptions
    
    def get_delay(self, attempt: int) -> float:
        """Вычисляет задержку для попытки.
        
        Args:
            attempt: Номер попытки (0-indexed)
            
        Returns:
            Задержка в секундах
        """
        delay = self.initial_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())
        
        return delay


def async_retry(config: Optional[RetryConfig] = None) -> Callable:
    """Декоратор для асинхронных функций с retry логикой.
    
    Args:
        config: Конфигурация retry (если None, используется default)
        
    Returns:
        Декоратор
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except config.retriable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"⚠️ Попытка {attempt + 1}/{config.max_attempts} не удалась: {e}. "
                            f"Повторная попытка через {delay:.2f}с..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"❌ Все {config.max_attempts} попытки исчерпаны для {func.__name__}"
                        )
            
            if last_exception:
                raise last_exception
            
            # На случай если что-то пошло не так
            raise RuntimeError(f"Неожиданная ошибка в retry логике для {func.__name__}")
        
        return wrapper
    
    return decorator


def sync_retry(config: Optional[RetryConfig] = None) -> Callable:
    """Декоратор для синхронных функций с retry логикой.
    
    Args:
        config: Конфигурация retry (если None, используется default)
        
    Returns:
        Декоратор
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except config.retriable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"⚠️ Попытка {attempt + 1}/{config.max_attempts} не удалась: {e}. "
                            f"Повторная попытка через {delay:.2f}с..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"❌ Все {config.max_attempts} попытки исчерпаны для {func.__name__}"
                        )
            
            if last_exception:
                raise last_exception
            
            raise RuntimeError(f"Неожиданная ошибка в retry логике для {func.__name__}")
        
        return wrapper
    
    return decorator
