"""Система кэширования для результатов."""
import hashlib
import json
import time
from typing import Any, Optional, Dict, Callable
from functools import wraps
from utils.logger import get_logger

logger = get_logger()


class CacheEntry:
    """Запись в кэше."""
    
    def __init__(self, value: Any, ttl: int = 3600):
        """Инициализация записи кэша.
        
        Args:
            value: Значение для кэширования
            ttl: Время жизни (секунды)
        """
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """Проверяет, истёк ли срок действия записи.
        
        Returns:
            True если истёк, False иначе
        """
        return time.time() - self.created_at > self.ttl
    
    def get(self) -> Optional[Any]:
        """Возвращает значение если оно ещё валидно.
        
        Returns:
            Значение или None если истёк срок
        """
        if self.is_expired():
            return None
        return self.value


class SimpleCache:
    """Простой в памяти кэш."""
    
    def __init__(self, max_size: int = 1000):
        """Инициализация кэша.
        
        Args:
            max_size: Максимальное количество записей
        """
        self.max_size = max_size
        self.cache: Dict[str, CacheEntry] = {}
    
    def _generate_key(self, *args: Any, **kwargs: Any) -> str:
        """Генерирует ключ кэша из аргументов.
        
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Ключ кэша
        """
        key_data = json.dumps({
            'args': str(args),
            'kwargs': str(sorted(kwargs.items()))
        }, sort_keys=True, default=str)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Получает значение из кэша.
        
        Args:
            key: Ключ кэша
            
        Returns:
            Значение или None
        """
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        value = entry.get()
        
        if value is None:
            del self.cache[key]
            return None
        
        return value
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Устанавливает значение в кэш.
        
        Args:
            key: Ключ кэша
            value: Значение
            ttl: Время жизни (секунды)
        """
        # Удаляем старые записи если кэш переполнен
        if len(self.cache) >= self.max_size:
            # Удаляем половину самых старых записей
            sorted_keys = sorted(
                self.cache.keys(),
                key=lambda k: self.cache[k].created_at
            )
            for k in sorted_keys[:len(self.cache) // 2]:
                del self.cache[k]
        
        self.cache[key] = CacheEntry(value, ttl)
    
    def clear(self) -> None:
        """Очищает кэш."""
        self.cache.clear()
    
    def cleanup_expired(self) -> int:
        """Удаляет истёкшие записи.
        
        Returns:
            Количество удалённых записей
        """
        expired_keys = [
            k for k, v in self.cache.items()
            if v.is_expired()
        ]
        
        for k in expired_keys:
            del self.cache[k]
        
        if expired_keys:
            logger.debug(f"🧹 Очищено {len(expired_keys)} истёкших записей кэша")
        
        return len(expired_keys)


# Глобальный кэш
_global_cache = SimpleCache()


def get_cache() -> SimpleCache:
    """Возвращает глобальный кэш.
    
    Returns:
        Экземпляр SimpleCache
    """
    return _global_cache


def cached(ttl: int = 3600) -> Callable:
    """Декоратор для кэширования результатов функции.
    
    Args:
        ttl: Время жизни кэша (секунды)
        
    Returns:
        Декоратор
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = get_cache()
            
            # Генерируем ключ
            key_data = json.dumps({
                'func': func.__name__,
                'args': str(args),
                'kwargs': str(sorted(kwargs.items()))
            }, sort_keys=True, default=str)
            key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Проверяем кэш
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"💾 Попадание в кэш для {func.__name__}")
                return cached_value
            
            # Вычисляем результат
            result = func(*args, **kwargs)
            
            # Сохраняем в кэш
            cache.set(key, result, ttl)
            return result
        
        return wrapper
    
    return decorator


def async_cached(ttl: int = 3600) -> Callable:
    """Декоратор для кэширования результатов асинхронной функции.
    
    Args:
        ttl: Время жизни кэша (секунды)
        
    Returns:
        Декоратор
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = get_cache()
            
            # Генерируем ключ
            key_data = json.dumps({
                'func': func.__name__,
                'args': str(args),
                'kwargs': str(sorted(kwargs.items()))
            }, sort_keys=True, default=str)
            key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Проверяем кэш
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"💾 Попадание в кэш для {func.__name__}")
                return cached_value
            
            # Вычисляем результат
            result = await func(*args, **kwargs)
            
            # Сохраняем в кэш
            cache.set(key, result, ttl)
            return result
        
        return wrapper
    
    return decorator
