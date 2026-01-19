"""Управление зависимостями и инъекция зависимостей для backend.

Централизованный контейнер для создания и получения shared-компонентов.
Следует принципу Dependency Inversion — все модули используют этот контейнер
вместо создания собственных экземпляров.
"""
from typing import Optional, TYPE_CHECKING
from functools import lru_cache
from utils.logger import get_logger

if TYPE_CHECKING:
    from agents.memory import MemoryAgent
    from infrastructure.rag import RAGSystem

logger = get_logger()


class DependencyContainer:
    """Контейнер для управления зависимостями приложения.
    
    Использует паттерн Singleton для гарантии единственного экземпляра
    критических компонентов. Все агенты и модули должны использовать
    этот контейнер для получения shared-зависимостей.
    
    Использование:
        from backend.dependencies import get_memory_agent
        
        memory = get_memory_agent()
    """
    
    _instance: Optional['DependencyContainer'] = None
    _memory_agent: Optional['MemoryAgent'] = None
    _rag_system: Optional['RAGSystem'] = None
    
    def __new__(cls) -> 'DependencyContainer':
        """Реализация паттерна Singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_memory_agent(cls) -> 'MemoryAgent':
        """Возвращает глобальный MemoryAgent, создавая его при необходимости.
        
        Returns:
            Экземпляр MemoryAgent (Singleton)
        """
        if cls._memory_agent is None:
            from agents.memory import MemoryAgent
            cls._memory_agent = MemoryAgent()
            logger.info("✅ MemoryAgent инициализирован (Singleton)")
        return cls._memory_agent
    
    @classmethod
    def get_rag_system(cls, collection_name: str = "code_knowledge") -> 'RAGSystem':
        """Возвращает глобальный RAGSystem, создавая его при необходимости.
        
        Args:
            collection_name: Название коллекции ChromaDB
            
        Returns:
            Экземпляр RAGSystem (Singleton)
        """
        if cls._rag_system is None:
            from infrastructure.rag import RAGSystem
            cls._rag_system = RAGSystem(
                collection_name=collection_name,
                persist_directory=".chromadb"
            )
            logger.info("✅ RAGSystem инициализирован (Singleton)")
        return cls._rag_system
    
    @classmethod
    def reset(cls) -> None:
        """Сбрасывает все зависимости (для тестирования)."""
        cls._memory_agent = None
        cls._rag_system = None
        logger.info("🔄 DependencyContainer сброшен")


# === Удобные функции для импорта ===

def get_memory_agent() -> 'MemoryAgent':
    """Возвращает глобальный MemoryAgent.
    
    Удобная функция для импорта:
        from backend.dependencies import get_memory_agent
        memory = get_memory_agent()
    
    Returns:
        Экземпляр MemoryAgent
    """
    return DependencyContainer.get_memory_agent()


def get_rag_system(collection_name: str = "code_knowledge") -> 'RAGSystem':
    """Возвращает глобальный RAGSystem.
    
    Args:
        collection_name: Название коллекции
        
    Returns:
        Экземпляр RAGSystem
    """
    return DependencyContainer.get_rag_system(collection_name)


def reset_dependencies() -> None:
    """Сбрасывает все зависимости (для тестирования)."""
    DependencyContainer.reset()


@lru_cache(maxsize=1)
def get_dependency_container() -> DependencyContainer:
    """Возвращает глобальный контейнер зависимостей.
    
    Returns:
        Экземпляр DependencyContainer
    """
    return DependencyContainer()
