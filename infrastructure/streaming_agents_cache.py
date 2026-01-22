"""Потокобезопасный кэш для стриминговых агентов.

Решает проблему race condition при параллельных запросах с разными моделями.
"""
import threading
from typing import Any, Callable, Dict, Tuple, Optional
from utils.logger import get_logger

logger = get_logger()


class StreamingAgentsCache:
    """Потокобезопасный кэш для стриминговых агентов.
    
    Кэширует агентов по ключу (agent_type, model, temperature, ...),
    предотвращая race condition при параллельных запросах.
    """
    
    _cache: Dict[Tuple[str, ...], Any] = {}
    _lock = threading.Lock()
    
    @classmethod
    def get_agent(
        cls,
        agent_type: str,
        model: str | None,
        temperature: float,
        factory: Callable[..., Any],
        **kwargs: Any
    ) -> Any:
        """Получает агента из кэша или создаёт новый.
        
        Args:
            agent_type: Тип агента (planner, coder, etc.)
            model: Модель для агента (может быть None)
            temperature: Температура генерации
            factory: Функция для создания агента
            **kwargs: Дополнительные параметры для factory
            
        Returns:
            Экземпляр агента
        """
        # Создаём ключ кэша из параметров
        cache_key = cls._make_cache_key(agent_type, model, temperature, **kwargs)
        
        with cls._lock:
            if cache_key not in cls._cache:
                logger.debug(f"🔨 Создаю нового стримингового агента: {agent_type} (модель: {model})")
                cls._cache[cache_key] = factory(**kwargs)
            else:
                logger.debug(f"♻️ Использую кэшированного агента: {agent_type} (модель: {model})")
            
            return cls._cache[cache_key]
    
    @classmethod
    def _make_cache_key(
        cls,
        agent_type: str,
        model: str | None,
        temperature: float,
        **kwargs: Any
    ) -> Tuple[str, ...]:
        """Создаёт ключ кэша из параметров.
        
        Args:
            agent_type: Тип агента
            model: Модель
            temperature: Температура
            **kwargs: Дополнительные параметры
            
        Returns:
            Кортеж для использования как ключ словаря
        """
        # Сортируем kwargs для стабильности ключа
        sorted_kwargs = tuple(sorted(kwargs.items()))
        return (agent_type, model or "None", temperature, sorted_kwargs)
    
    @classmethod
    def clear_cache(cls) -> None:
        """Очищает весь кэш агентов."""
        with cls._lock:
            count = len(cls._cache)
            cls._cache.clear()
            logger.info(f"🗑️ Кэш стриминговых агентов очищен ({count} агентов)")
    
    @classmethod
    def clear_agent_type(cls, agent_type: str) -> None:
        """Очищает кэш для конкретного типа агента.
        
        Args:
            agent_type: Тип агента для очистки
        """
        with cls._lock:
            keys_to_remove = [
                key for key in cls._cache.keys()
                if key[0] == agent_type
            ]
            for key in keys_to_remove:
                del cls._cache[key]
            
            if keys_to_remove:
                logger.info(f"🗑️ Очищен кэш для агента {agent_type} ({len(keys_to_remove)} экземпляров)")
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """Возвращает статистику кэша.
        
        Returns:
            Словарь со статистикой
        """
        with cls._lock:
            agent_types = {}
            for key in cls._cache.keys():
                agent_type = key[0]
                agent_types[agent_type] = agent_types.get(agent_type, 0) + 1
            
            return {
                "total_agents": len(cls._cache),
                "by_type": agent_types
            }


# === Удобные функции для импорта ===

def get_streaming_agent(
    agent_type: str,
    model: str | None,
    temperature: float,
    factory: Callable[..., Any],
    **kwargs: Any
) -> Any:
    """Получает стримингового агента из кэша.
    
    Args:
        agent_type: Тип агента (planner, coder, etc.)
        model: Модель для агента
        temperature: Температура генерации
        factory: Функция для создания агента
        **kwargs: Дополнительные параметры
        
    Returns:
        Экземпляр агента
    """
    return StreamingAgentsCache.get_agent(
        agent_type=agent_type,
        model=model,
        temperature=temperature,
        factory=factory,
        **kwargs
    )
