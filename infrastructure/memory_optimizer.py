"""Оптимизация использования памяти."""
import gc
import sys
from typing import Optional, Dict, Any
from functools import wraps
from utils.logger import get_logger

logger = get_logger()


class MemoryOptimizer:
    """Оптимизатор использования памяти."""
    
    def __init__(self, max_memory_mb: int = 2048):
        """Инициализация оптимизатора.
        
        Args:
            max_memory_mb: Максимальное использование памяти (МБ)
        """
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.gc_threshold = 0.8  # Запускать GC когда использовано 80%
    
    def get_memory_usage(self) -> int:
        """Возвращает текущее использование памяти (байты).
        
        Returns:
            Использование памяти в байтах
        """
        import psutil
        import os
        
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss
        except Exception:
            # Fallback если psutil не доступен
            return sys.getsizeof(gc.get_objects())
    
    def get_memory_percentage(self) -> float:
        """Возвращает процент использованной памяти.
        
        Returns:
            Процент использованной памяти (0-100)
        """
        usage = self.get_memory_usage()
        return (usage / self.max_memory_bytes) * 100
    
    def should_cleanup(self) -> bool:
        """Проверяет, нужна ли очистка памяти.
        
        Returns:
            True если нужна очистка
        """
        return self.get_memory_percentage() > (self.gc_threshold * 100)
    
    def cleanup(self) -> int:
        """Выполняет очистку памяти.
        
        Returns:
            Количество собранных объектов
        """
        logger.info("🧹 Запускаю очистку памяти...")
        
        # Отключаем автоматический GC
        gc.disable()
        
        try:
            # Выполняем полную сборку мусора
            collected = gc.collect()
            logger.info(f"✅ Собрано {collected} объектов")
            
            # Возвращаем использование памяти
            usage_mb = self.get_memory_usage() / (1024 * 1024)
            percentage = self.get_memory_percentage()
            logger.info(f"📊 Использование памяти: {usage_mb:.1f} МБ ({percentage:.1f}%)")
            
            return collected
        finally:
            # Включаем автоматический GC обратно
            gc.enable()
    
    def optimize_list(self, items: list) -> list:
        """Оптимизирует список, удаляя дубликаты и None.
        
        Args:
            items: Исходный список
            
        Returns:
            Оптимизированный список
        """
        # Удаляем None и дубликаты (сохраняя порядок)
        seen = set()
        result = []
        
        for item in items:
            if item is not None and item not in seen:
                seen.add(item)
                result.append(item)
        
        return result
    
    def optimize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Оптимизирует словарь, удаляя пустые значения.
        
        Args:
            data: Исходный словарь
            
        Returns:
            Оптимизированный словарь
        """
        return {
            k: v for k, v in data.items()
            if v is not None and v != "" and v != [] and v != {}
        }


# Глобальный оптимизатор
_optimizer: Optional[MemoryOptimizer] = None


def get_memory_optimizer(max_memory_mb: int = 2048) -> MemoryOptimizer:
    """Возвращает глобальный оптимизатор памяти.
    
    Args:
        max_memory_mb: Максимальное использование памяти (МБ)
        
    Returns:
        Экземпляр MemoryOptimizer
    """
    global _optimizer
    
    if _optimizer is None:
        _optimizer = MemoryOptimizer(max_memory_mb)
    
    return _optimizer


def memory_efficient(func):
    """Декоратор для оптимизации памяти функции.
    
    Args:
        func: Функция для оптимизации
        
    Returns:
        Обёрнутая функция
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        optimizer = get_memory_optimizer()
        
        # Проверяем память перед выполнением
        if optimizer.should_cleanup():
            optimizer.cleanup()
        
        # Выполняем функцию
        result = func(*args, **kwargs)
        
        # Проверяем память после выполнения
        if optimizer.should_cleanup():
            optimizer.cleanup()
        
        return result
    
    return wrapper


def async_memory_efficient(func):
    """Декоратор для оптимизации памяти асинхронной функции.
    
    Args:
        func: Асинхронная функция для оптимизации
        
    Returns:
        Обёрнутая функция
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        optimizer = get_memory_optimizer()
        
        # Проверяем память перед выполнением
        if optimizer.should_cleanup():
            optimizer.cleanup()
        
        # Выполняем функцию
        result = await func(*args, **kwargs)
        
        # Проверяем память после выполнения
        if optimizer.should_cleanup():
            optimizer.cleanup()
        
        return result
    
    return wrapper
