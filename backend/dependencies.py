"""Управление зависимостями и инъекция зависимостей для backend.

Централизованный контейнер для создания и получения shared-компонентов.
Следует принципу Dependency Inversion — все модули используют этот контейнер
вместо создания собственных экземпляров.
"""
import threading
from typing import Optional, TYPE_CHECKING, Dict, Any
from utils.logger import get_logger
from utils.config import get_config

if TYPE_CHECKING:
    from agents.memory import MemoryAgent
    from infrastructure.rag import RAGSystem
    from agents.intent import IntentAgent
    from agents.planner import PlannerAgent
    from agents.researcher import ResearcherAgent
    from agents.test_generator import TestGeneratorAgent
    from agents.coder import CoderAgent
    from agents.debugger import DebuggerAgent
    from agents.reflection import ReflectionAgent
    from agents.critic import CriticAgent

logger = get_logger()


class DependencyContainer:
    """Контейнер для управления зависимостями приложения.
    
    Использует паттерн Singleton для гарантии единственного экземпляра
    критических компонентов. Все агенты и модули должны использовать
    этот контейнер для получения shared-зависимостей.
    
    Потокобезопасен для использования в многопоточных окружениях (FastAPI).
    
    Использование:
        from backend.dependencies import get_memory_agent
        
        memory = get_memory_agent()
    """
    
    _instance: Optional['DependencyContainer'] = None
    _lock = threading.Lock()
    _memory_agent: Optional['MemoryAgent'] = None
    _rag_system: Optional['RAGSystem'] = None
    
    # Кэш агентов (thread-safe)
    _agents_cache: Dict[str, Any] = {}
    _agents_lock = threading.Lock()
    
    # Кэш стриминговых агентов (thread-safe)
    _streaming_agents_cache: Dict[str, Any] = {}
    _streaming_agents_lock = threading.Lock()
    
    def __new__(cls) -> 'DependencyContainer':
        """Реализация паттерна Singleton с потокобезопасностью."""
        if cls._instance is None:
            with cls._lock:
                # Двойная проверка для потокобезопасности
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
            with cls._lock:
                # Двойная проверка для потокобезопасности
                if cls._memory_agent is None:
                    from agents.memory import MemoryAgent
                    cls._memory_agent = MemoryAgent()
                    logger.info("✅ MemoryAgent инициализирован (Singleton)")
        return cls._memory_agent
    
    @classmethod
    def get_rag_system(cls, collection_name: Optional[str] = None) -> 'RAGSystem':
        """Возвращает глобальный RAGSystem, создавая его при необходимости.
        
        Args:
            collection_name: Название коллекции ChromaDB. Если None, используется
                           значение из конфигурации. Если указано и отличается
                           от текущего, создаётся новый экземпляр.
            
        Returns:
            Экземпляр RAGSystem (Singleton для конкретной коллекции)
        """
        config = get_config()
        collection_name = collection_name or config.rag_code_collection
        
        # Проверяем, нужно ли пересоздать RAGSystem для другой коллекции
        if cls._rag_system is None or cls._rag_system.collection_name != collection_name:
            with cls._lock:
                # Двойная проверка для потокобезопасности
                if cls._rag_system is None or cls._rag_system.collection_name != collection_name:
                    from infrastructure.rag import RAGSystem
                    cls._rag_system = RAGSystem(
                        collection_name=collection_name,
                        persist_directory=config.rag_persist_directory
                    )
                    logger.info(f"✅ RAGSystem инициализирован для коллекции {collection_name}")
        return cls._rag_system
    
    @classmethod
    def reset(cls) -> None:
        """Сбрасывает все зависимости (для тестирования)."""
        with cls._lock:
            cls._memory_agent = None
            cls._rag_system = None
        with cls._agents_lock:
            cls._agents_cache.clear()
        logger.info("🔄 DependencyContainer сброшен")
    
    @classmethod
    def _get_agent(
        cls,
        agent_type: str,
        agent_class: type,
        cache_key: str,
        **init_kwargs: Any
    ) -> Any:
        """Универсальный метод для получения агента с кэшированием.
        
        Args:
            agent_type: Тип агента (для логирования)
            agent_class: Класс агента для создания
            cache_key: Ключ кэша
            **init_kwargs: Параметры для инициализации агента
            
        Returns:
            Экземпляр агента
        """
        if cache_key not in cls._agents_cache:
            with cls._agents_lock:
                if cache_key not in cls._agents_cache:
                    cls._agents_cache[cache_key] = agent_class(**init_kwargs)
                    logger.debug(f"✅ {agent_type} инициализирован (cache_key: {cache_key})")
        return cls._agents_cache[cache_key]
    
    @classmethod
    def _get_agent_with_params(
        cls,
        agent_type: str,
        agent_module: str,
        agent_class_name: str,
        model: Optional[str] = None,
        temperature: float = 0.25,
        **extra_kwargs: Any
    ) -> Any:
        """Generic метод для получения агента с параметрами model и temperature.
        
        Args:
            agent_type: Тип агента (для логирования)
            agent_module: Модуль агента (например, 'agents.intent')
            agent_class_name: Имя класса агента (например, 'IntentAgent')
            model: Модель для агента
            temperature: Температура генерации
            **extra_kwargs: Дополнительные параметры для инициализации
            
        Returns:
            Экземпляр агента
        """
        cache_key = f"{agent_type.lower()}_{model}_{temperature}"
        if cache_key not in cls._agents_cache:
            with cls._agents_lock:
                if cache_key not in cls._agents_cache:
                    # Динамический импорт
                    module = __import__(agent_module, fromlist=[agent_class_name])
                    agent_class = getattr(module, agent_class_name)
                    cls._agents_cache[cache_key] = agent_class(
                        model=model,
                        temperature=temperature,
                        **extra_kwargs
                    )
                    logger.debug(f"✅ {agent_type} инициализирован (cache_key: {cache_key})")
        return cls._agents_cache[cache_key]
    
    @classmethod
    def get_intent_agent(cls, model: Optional[str] = None, temperature: float = 0.2) -> 'IntentAgent':
        """Возвращает IntentAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента (None = используется из конфига)
            temperature: Температура генерации
            
        Returns:
            Экземпляр IntentAgent
        """
        return cls._get_agent_with_params(
            agent_type="IntentAgent",
            agent_module="agents.intent",
            agent_class_name="IntentAgent",
            model=model,
            temperature=temperature
        )
    
    @classmethod
    def get_planner_agent(
        cls,
        model: Optional[str] = None,
        temperature: float = 0.25,
        memory_agent: Optional['MemoryAgent'] = None
    ) -> 'PlannerAgent':
        """Возвращает PlannerAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента
            temperature: Температура генерации
            memory_agent: MemoryAgent (если None, получается автоматически)
            
        Returns:
            Экземпляр PlannerAgent
        """
        if memory_agent is None:
            memory_agent = cls.get_memory_agent()
        return cls._get_agent_with_params(
            agent_type="PlannerAgent",
            agent_module="agents.planner",
            agent_class_name="PlannerAgent",
            model=model,
            temperature=temperature,
            memory_agent=memory_agent
        )
    
    @classmethod
    def get_researcher_agent(cls, memory_agent: Optional['MemoryAgent'] = None) -> 'ResearcherAgent':
        """Возвращает ResearcherAgent, создавая его при необходимости.
        
        Args:
            memory_agent: MemoryAgent (если None, получается автоматически)
            
        Returns:
            Экземпляр ResearcherAgent
        """
        if memory_agent is None:
            memory_agent = cls.get_memory_agent()
        cache_key = "researcher"
        if cache_key not in cls._agents_cache:
            with cls._agents_lock:
                if cache_key not in cls._agents_cache:
                    from agents.researcher import ResearcherAgent
                    cls._agents_cache[cache_key] = ResearcherAgent(memory_agent=memory_agent)
                    logger.debug(f"✅ ResearcherAgent инициализирован (cache_key: {cache_key})")
        return cls._agents_cache[cache_key]
    
    @classmethod
    def get_test_generator_agent(
        cls,
        model: Optional[str] = None,
        temperature: float = 0.18
    ) -> 'TestGeneratorAgent':
        """Возвращает TestGeneratorAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента
            temperature: Температура генерации
            
        Returns:
            Экземпляр TestGeneratorAgent
        """
        return cls._get_agent_with_params(
            agent_type="TestGeneratorAgent",
            agent_module="agents.test_generator",
            agent_class_name="TestGeneratorAgent",
            model=model,
            temperature=temperature
        )
    
    @classmethod
    def get_coder_agent(
        cls,
        model: Optional[str] = None,
        temperature: float = 0.25
    ) -> 'CoderAgent':
        """Возвращает CoderAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента
            temperature: Температура генерации
            
        Returns:
            Экземпляр CoderAgent
        """
        return cls._get_agent_with_params(
            agent_type="CoderAgent",
            agent_module="agents.coder",
            agent_class_name="CoderAgent",
            model=model,
            temperature=temperature
        )
    
    @classmethod
    def get_debugger_agent(
        cls,
        model: Optional[str] = None,
        temperature: float = 0.2
    ) -> 'DebuggerAgent':
        """Возвращает DebuggerAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента
            temperature: Температура генерации
            
        Returns:
            Экземпляр DebuggerAgent
        """
        return cls._get_agent_with_params(
            agent_type="DebuggerAgent",
            agent_module="agents.debugger",
            agent_class_name="DebuggerAgent",
            model=model,
            temperature=temperature
        )
    
    @classmethod
    def get_reflection_agent(
        cls,
        model: Optional[str] = None,
        temperature: float = 0.25
    ) -> 'ReflectionAgent':
        """Возвращает ReflectionAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента
            temperature: Температура генерации
            
        Returns:
            Экземпляр ReflectionAgent
        """
        return cls._get_agent_with_params(
            agent_type="ReflectionAgent",
            agent_module="agents.reflection",
            agent_class_name="ReflectionAgent",
            model=model,
            temperature=temperature
        )
    
    @classmethod
    def get_critic_agent(cls) -> 'CriticAgent':
        """Возвращает CriticAgent, создавая его при необходимости.
        
        Returns:
            Экземпляр CriticAgent
        """
        from agents.critic import get_critic_agent as create_critic
        cache_key = "critic"
        if cache_key not in cls._agents_cache:
            with cls._agents_lock:
                if cache_key not in cls._agents_cache:
                    cls._agents_cache[cache_key] = create_critic()
                    logger.debug("✅ CriticAgent инициализирован")
        return cls._agents_cache[cache_key]
    
    # === Стриминговые агенты ===
    
    @classmethod
    def _get_streaming_agent(
        cls,
        agent_type: str,
        agent_class: type,
        cache_key: str,
        **init_kwargs: Any
    ) -> Any:
        """Универсальный метод для получения стримингового агента с кэшированием.
        
        Args:
            agent_type: Тип агента (для логирования)
            agent_class: Класс стримингового агента для создания
            cache_key: Ключ кэша
            **init_kwargs: Параметры для инициализации агента
            
        Returns:
            Экземпляр стримингового агента
        """
        if cache_key not in cls._streaming_agents_cache:
            with cls._streaming_agents_lock:
                if cache_key not in cls._streaming_agents_cache:
                    cls._streaming_agents_cache[cache_key] = agent_class(**init_kwargs)
                    logger.debug(f"✅ {agent_type} (streaming) инициализирован (cache_key: {cache_key})")
        return cls._streaming_agents_cache[cache_key]
    
    @classmethod
    def _get_streaming_agent_with_params(
        cls,
        agent_type: str,
        agent_module: str,
        agent_class_name: str,
        model: Optional[str] = None,
        temperature: float = 0.25,
        **extra_kwargs: Any
    ) -> Any:
        """Generic метод для получения стримингового агента с параметрами model и temperature.
        
        Args:
            agent_type: Тип агента (для логирования)
            agent_module: Модуль агента (например, 'agents.streaming_coder')
            agent_class_name: Имя класса агента (например, 'StreamingCoderAgent')
            model: Модель для агента
            temperature: Температура генерации
            **extra_kwargs: Дополнительные параметры для инициализации
            
        Returns:
            Экземпляр стримингового агента
        """
        cache_key = f"streaming_{agent_type.lower()}_{model}_{temperature}"
        if cache_key not in cls._streaming_agents_cache:
            with cls._streaming_agents_lock:
                if cache_key not in cls._streaming_agents_cache:
                    # Динамический импорт
                    module = __import__(agent_module, fromlist=[agent_class_name])
                    agent_class = getattr(module, agent_class_name)
                    cls._streaming_agents_cache[cache_key] = agent_class(
                        model=model,
                        temperature=temperature,
                        **extra_kwargs
                    )
                    logger.debug(f"✅ {agent_type} (streaming) инициализирован (cache_key: {cache_key})")
        return cls._streaming_agents_cache[cache_key]
    
    @classmethod
    def get_streaming_planner_agent(
        cls,
        model: Optional[str] = None,
        temperature: float = 0.25,
        memory_agent: Optional['MemoryAgent'] = None
    ) -> Any:
        """Возвращает StreamingPlannerAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента
            temperature: Температура генерации
            memory_agent: MemoryAgent (если None, получается автоматически)
            
        Returns:
            Экземпляр StreamingPlannerAgent
        """
        if memory_agent is None:
            memory_agent = cls.get_memory_agent()
        return cls._get_streaming_agent_with_params(
            agent_type="PlannerAgent",
            agent_module="agents.streaming_planner",
            agent_class_name="StreamingPlannerAgent",
            model=model,
            temperature=temperature,
            memory_agent=memory_agent
        )
    
    @classmethod
    def get_streaming_test_generator_agent(
        cls,
        model: Optional[str] = None,
        temperature: float = 0.18
    ) -> Any:
        """Возвращает StreamingTestGeneratorAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента
            temperature: Температура генерации
            
        Returns:
            Экземпляр StreamingTestGeneratorAgent
        """
        return cls._get_streaming_agent_with_params(
            agent_type="TestGeneratorAgent",
            agent_module="agents.streaming_test_generator",
            agent_class_name="StreamingTestGeneratorAgent",
            model=model,
            temperature=temperature
        )
    
    @classmethod
    def get_streaming_coder_agent(
        cls,
        model: Optional[str] = None,
        temperature: float = 0.25
    ) -> Any:
        """Возвращает StreamingCoderAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента
            temperature: Температура генерации
            
        Returns:
            Экземпляр StreamingCoderAgent
        """
        return cls._get_streaming_agent_with_params(
            agent_type="CoderAgent",
            agent_module="agents.streaming_coder",
            agent_class_name="StreamingCoderAgent",
            model=model,
            temperature=temperature
        )
    
    @classmethod
    def get_streaming_debugger_agent(
        cls,
        model: Optional[str] = None,
        temperature: float = 0.2
    ) -> Any:
        """Возвращает StreamingDebuggerAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента
            temperature: Температура генерации
            
        Returns:
            Экземпляр StreamingDebuggerAgent
        """
        return cls._get_streaming_agent_with_params(
            agent_type="DebuggerAgent",
            agent_module="agents.streaming_debugger",
            agent_class_name="StreamingDebuggerAgent",
            model=model,
            temperature=temperature
        )
    
    @classmethod
    def get_streaming_reflection_agent(
        cls,
        model: Optional[str] = None,
        temperature: float = 0.25
    ) -> Any:
        """Возвращает StreamingReflectionAgent, создавая его при необходимости.
        
        Args:
            model: Модель для агента
            temperature: Температура генерации
            
        Returns:
            Экземпляр StreamingReflectionAgent
        """
        return cls._get_streaming_agent_with_params(
            agent_type="ReflectionAgent",
            agent_module="agents.streaming_reflection",
            agent_class_name="StreamingReflectionAgent",
            model=model,
            temperature=temperature
        )
    
    @classmethod
    def get_streaming_critic_agent(cls) -> Any:
        """Возвращает StreamingCriticAgent, создавая его при необходимости.
        
        Returns:
            Экземпляр StreamingCriticAgent
        """
        return cls._get_streaming_agent_with_params(
            agent_type="CriticAgent",
            agent_module="agents.streaming_critic",
            agent_class_name="StreamingCriticAgent",
            model=None,
            temperature=0.1
        )
    
    @classmethod
    def shutdown(cls) -> None:
        """Корректно завершает работу всех зависимостей.
        
        Вызывается при graceful shutdown приложения для освобождения ресурсов.
        """
        with cls._lock:
            if cls._rag_system:
                # ChromaDB PersistentClient не требует явного закрытия,
                # но можно добавить cleanup если понадобится
                logger.info("✅ RAGSystem остановлен")
                cls._rag_system = None
            
            if cls._memory_agent:
                # MemoryAgent не имеет явного cleanup, но можно добавить если понадобится
                logger.info("✅ MemoryAgent остановлен")
                cls._memory_agent = None
            
            # Очищаем кэш агентов
            with cls._agents_lock:
                cls._agents_cache.clear()
                logger.info("✅ Кэш агентов очищен")
            
            # Очищаем кэш стриминговых агентов
            with cls._streaming_agents_lock:
                cls._streaming_agents_cache.clear()
                logger.info("✅ Кэш стриминговых агентов очищен")
            
            logger.info("✅ DependencyContainer остановлен")


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


def get_rag_system(collection_name: Optional[str] = None) -> 'RAGSystem':
    """Возвращает глобальный RAGSystem.
    
    Args:
        collection_name: Название коллекции. Если None, используется значение
                        из конфигурации (rag.code_collection).
        
    Returns:
        Экземпляр RAGSystem
    """
    return DependencyContainer.get_rag_system(collection_name)


def reset_dependencies() -> None:
    """Сбрасывает все зависимости (для тестирования)."""
    DependencyContainer.reset()


def shutdown_dependencies() -> None:
    """Корректно завершает работу всех зависимостей.
    
    Вызывается при graceful shutdown приложения.
    """
    DependencyContainer.shutdown()


def get_dependency_container() -> DependencyContainer:
    """Возвращает глобальный контейнер зависимостей.
    
    Returns:
        Экземпляр DependencyContainer
        
    Note:
        lru_cache не нужен, т.к. DependencyContainer уже реализует Singleton.
    """
    return DependencyContainer()


# === Удобные функции для получения агентов ===

def get_intent_agent(model: Optional[str] = None, temperature: float = 0.2) -> 'IntentAgent':
    """Возвращает IntentAgent через DependencyContainer."""
    return DependencyContainer.get_intent_agent(model=model, temperature=temperature)


def get_planner_agent(
    model: Optional[str] = None,
    temperature: float = 0.25,
    memory_agent: Optional['MemoryAgent'] = None
) -> 'PlannerAgent':
    """Возвращает PlannerAgent через DependencyContainer."""
    return DependencyContainer.get_planner_agent(
        model=model,
        temperature=temperature,
        memory_agent=memory_agent
    )


def get_researcher_agent(memory_agent: Optional['MemoryAgent'] = None) -> 'ResearcherAgent':
    """Возвращает ResearcherAgent через DependencyContainer."""
    return DependencyContainer.get_researcher_agent(memory_agent=memory_agent)


def get_test_generator_agent(
    model: Optional[str] = None,
    temperature: float = 0.18
) -> 'TestGeneratorAgent':
    """Возвращает TestGeneratorAgent через DependencyContainer."""
    return DependencyContainer.get_test_generator_agent(model=model, temperature=temperature)


def get_coder_agent(
    model: Optional[str] = None,
    temperature: float = 0.25
) -> 'CoderAgent':
    """Возвращает CoderAgent через DependencyContainer."""
    return DependencyContainer.get_coder_agent(model=model, temperature=temperature)


def get_debugger_agent(
    model: Optional[str] = None,
    temperature: float = 0.2
) -> 'DebuggerAgent':
    """Возвращает DebuggerAgent через DependencyContainer."""
    return DependencyContainer.get_debugger_agent(model=model, temperature=temperature)


def get_reflection_agent(
    model: Optional[str] = None,
    temperature: float = 0.25
) -> 'ReflectionAgent':
    """Возвращает ReflectionAgent через DependencyContainer."""
    return DependencyContainer.get_reflection_agent(model=model, temperature=temperature)


def get_critic_agent() -> 'CriticAgent':
    """Возвращает CriticAgent через DependencyContainer."""
    return DependencyContainer.get_critic_agent()


# === Удобные функции для получения стриминговых агентов ===

def get_streaming_planner_agent(
    model: Optional[str] = None,
    temperature: float = 0.25,
    memory_agent: Optional['MemoryAgent'] = None
) -> Any:
    """Возвращает StreamingPlannerAgent через DependencyContainer."""
    return DependencyContainer.get_streaming_planner_agent(
        model=model,
        temperature=temperature,
        memory_agent=memory_agent
    )


def get_streaming_test_generator_agent(
    model: Optional[str] = None,
    temperature: float = 0.18
) -> Any:
    """Возвращает StreamingTestGeneratorAgent через DependencyContainer."""
    return DependencyContainer.get_streaming_test_generator_agent(
        model=model,
        temperature=temperature
    )


def get_streaming_coder_agent(
    model: Optional[str] = None,
    temperature: float = 0.25
) -> Any:
    """Возвращает StreamingCoderAgent через DependencyContainer."""
    return DependencyContainer.get_streaming_coder_agent(
        model=model,
        temperature=temperature
    )


def get_streaming_debugger_agent(
    model: Optional[str] = None,
    temperature: float = 0.2
) -> Any:
    """Возвращает StreamingDebuggerAgent через DependencyContainer."""
    return DependencyContainer.get_streaming_debugger_agent(
        model=model,
        temperature=temperature
    )


def get_streaming_reflection_agent(
    model: Optional[str] = None,
    temperature: float = 0.25
) -> Any:
    """Возвращает StreamingReflectionAgent через DependencyContainer."""
    return DependencyContainer.get_streaming_reflection_agent(
        model=model,
        temperature=temperature
    )


def get_streaming_critic_agent() -> Any:
    """Возвращает StreamingCriticAgent через DependencyContainer."""
    return DependencyContainer.get_streaming_critic_agent()
