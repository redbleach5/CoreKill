"""Управление зависимостями и инъекция зависимостей для backend."""
from typing import Optional
from functools import lru_cache
from agents.memory import MemoryAgent


class DependencyContainer:
    """Контейнер для управления зависимостями приложения.
    
    Использует паттерн Singleton для гарантии единственного экземпляра
    критических компонентов.
    """
    
    _instance: Optional['DependencyContainer'] = None
    _memory_agent: Optional[MemoryAgent] = None
    
    def __new__(cls) -> 'DependencyContainer':
        """Реализация паттерна Singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_memory_agent(cls) -> MemoryAgent:
        """Возвращает глобальный MemoryAgent, создавая его при необходимости.
        
        Returns:
            Экземпляр MemoryAgent
        """
        if cls._memory_agent is None:
            cls._memory_agent = MemoryAgent()
        return cls._memory_agent
    
    @classmethod
    def reset(cls) -> None:
        """Сбрасывает все зависимости (для тестирования)."""
        cls._memory_agent = None


@lru_cache(maxsize=1)
def get_dependency_container() -> DependencyContainer:
    """Возвращает глобальный контейнер зависимостей.
    
    Использует LRU кэш для оптимизации.
    
    Returns:
        Экземпляр DependencyContainer
    """
    return DependencyContainer()
