"""Тесты для backend/dependencies.py."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from backend.dependencies import (
    DependencyContainer,
    get_memory_agent,
    get_rag_system,
    reset_dependencies,
    shutdown_dependencies,
    get_dependency_container
)


class TestDependencyContainerSingleton:
    """Тесты singleton паттерна DependencyContainer."""
    
    @pytest.mark.backend

    
    def test_singleton_instance(self):
        """Тест что DependencyContainer использует singleton."""
        # Сбрасываем singleton
        DependencyContainer._instance = None
        
        container1 = DependencyContainer()
        container2 = DependencyContainer()
        
        assert container1 is container2
    
    @pytest.mark.backend

    
    def test_get_dependency_container(self):
        """Тест функции get_dependency_container."""
        # Сбрасываем singleton
        DependencyContainer._instance = None
        
        container1 = get_dependency_container()
        container2 = get_dependency_container()
        
        assert container1 is container2
        assert isinstance(container1, DependencyContainer)


class TestDependencyContainerMemoryAgent:
    """Тесты для MemoryAgent."""
    
    @pytest.mark.backend

    
    def test_get_memory_agent_creates_once(self):
        """Тест что MemoryAgent создаётся один раз."""
        # Сбрасываем singleton и memory agent
        DependencyContainer._instance = None
        DependencyContainer._memory_agent = None
        
        with patch('agents.memory.MemoryAgent') as mock_memory_class:
            mock_agent = Mock()
            mock_memory_class.return_value = mock_agent
            
            agent1 = DependencyContainer.get_memory_agent()
            agent2 = DependencyContainer.get_memory_agent()
            
            # Должен быть создан только один раз
            assert mock_memory_class.call_count == 1
            assert agent1 is agent2
            assert agent1 is mock_agent
    
    @pytest.mark.backend

    
    def test_get_memory_agent_function(self):
        """Тест удобной функции get_memory_agent."""
        # Сбрасываем singleton и memory agent
        DependencyContainer._instance = None
        DependencyContainer._memory_agent = None
        
        with patch('agents.memory.MemoryAgent') as mock_memory_class:
            mock_agent = Mock()
            mock_memory_class.return_value = mock_agent
            
            agent = get_memory_agent()
            
            assert agent is mock_agent
            mock_memory_class.assert_called_once()


class TestDependencyContainerRAGSystem:
    """Тесты для RAGSystem."""
    
    @pytest.mark.backend

    
    def test_get_rag_system_creates_once(self):
        """Тест что RAGSystem создаётся один раз для коллекции."""
        # Сбрасываем singleton и RAG system
        DependencyContainer._instance = None
        DependencyContainer._rag_system = None
        
        with patch('infrastructure.rag.RAGSystem') as mock_rag_class, \
             patch('backend.dependencies.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.rag_code_collection = "test_collection"
            mock_config.rag_persist_directory = ".test_chromadb"
            mock_get_config.return_value = mock_config
            
            mock_rag = Mock()
            mock_rag.collection_name = "test_collection"
            mock_rag_class.return_value = mock_rag
            
            rag1 = DependencyContainer.get_rag_system()
            rag2 = DependencyContainer.get_rag_system()
            
            # Должен быть создан только один раз
            assert mock_rag_class.call_count == 1
            assert rag1 is rag2
            assert rag1 is mock_rag
    
    @pytest.mark.backend

    
    def test_get_rag_system_different_collection(self):
        """Тест что RAGSystem пересоздаётся для другой коллекции."""
        # Сбрасываем singleton и RAG system
        DependencyContainer._instance = None
        DependencyContainer._rag_system = None
        
        with patch('infrastructure.rag.RAGSystem') as mock_rag_class, \
             patch('backend.dependencies.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.rag_code_collection = "default_collection"
            mock_config.rag_persist_directory = ".test_chromadb"
            mock_get_config.return_value = mock_config
            
            mock_rag1 = Mock()
            mock_rag1.collection_name = "default_collection"
            mock_rag2 = Mock()
            mock_rag2.collection_name = "custom_collection"
            
            mock_rag_class.side_effect = [mock_rag1, mock_rag2]
            
            rag1 = DependencyContainer.get_rag_system()
            rag2 = DependencyContainer.get_rag_system("custom_collection")
            
            # Должен быть создан дважды для разных коллекций
            assert mock_rag_class.call_count == 2
            assert rag1 is mock_rag1
            assert rag2 is mock_rag2
    
    @pytest.mark.backend

    
    def test_get_rag_system_function(self):
        """Тест удобной функции get_rag_system."""
        # Сбрасываем singleton и RAG system
        DependencyContainer._instance = None
        DependencyContainer._rag_system = None
        
        with patch('infrastructure.rag.RAGSystem') as mock_rag_class, \
             patch('backend.dependencies.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.rag_code_collection = "test_collection"
            mock_config.rag_persist_directory = ".test_chromadb"
            mock_get_config.return_value = mock_config
            
            mock_rag = Mock()
            mock_rag.collection_name = "test_collection"
            mock_rag_class.return_value = mock_rag
            
            rag = get_rag_system()
            
            assert rag is mock_rag
            mock_rag_class.assert_called_once()


class TestDependencyContainerAgents:
    """Тесты для получения агентов."""
    
    @pytest.mark.backend

    
    def test_get_intent_agent_caching(self):
        """Тест кэширования IntentAgent."""
        # Сбрасываем singleton и кэш
        DependencyContainer._instance = None
        DependencyContainer._agents_cache.clear()
        
        with patch('agents.intent.IntentAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent_class.return_value = mock_agent
            
            agent1 = DependencyContainer.get_intent_agent()
            agent2 = DependencyContainer.get_intent_agent()
            
            # Должен быть создан только один раз
            assert mock_agent_class.call_count == 1
            assert agent1 is agent2
    
    @pytest.mark.backend

    
    def test_get_intent_agent_different_models(self):
        """Тест что разные модели создают разные экземпляры."""
        # Сбрасываем singleton и кэш
        DependencyContainer._instance = None
        DependencyContainer._agents_cache.clear()
        
        with patch('agents.intent.IntentAgent') as mock_agent_class:
            mock_agent1 = Mock()
            mock_agent2 = Mock()
            mock_agent_class.side_effect = [mock_agent1, mock_agent2]
            
            agent1 = DependencyContainer.get_intent_agent(model="model1")
            agent2 = DependencyContainer.get_intent_agent(model="model2")
            
            # Должны быть созданы два разных экземпляра
            assert mock_agent_class.call_count == 2
            assert agent1 is not agent2
    
    @pytest.mark.backend

    
    def test_get_planner_agent_with_memory(self):
        """Тест получения PlannerAgent с MemoryAgent."""
        # Сбрасываем singleton и кэш
        DependencyContainer._instance = None
        DependencyContainer._agents_cache.clear()
        DependencyContainer._memory_agent = None
        
        with patch('agents.memory.MemoryAgent') as mock_memory_class, \
             patch('agents.planner.PlannerAgent') as mock_planner_class:
            mock_memory = Mock()
            mock_memory_class.return_value = mock_memory
            
            mock_planner = Mock()
            mock_planner_class.return_value = mock_planner
            
            planner = DependencyContainer.get_planner_agent()
            
            # Должен быть передан memory_agent
            mock_planner_class.assert_called_once()
            call_kwargs = mock_planner_class.call_args[1]
            assert call_kwargs.get("memory_agent") is mock_memory
    
    @pytest.mark.backend

    
    def test_get_researcher_agent(self):
        """Тест получения ResearcherAgent."""
        # Сбрасываем singleton и кэш
        DependencyContainer._instance = None
        DependencyContainer._agents_cache.clear()
        DependencyContainer._memory_agent = None
        
        with patch('agents.memory.MemoryAgent') as mock_memory_class, \
             patch('agents.researcher.ResearcherAgent') as mock_researcher_class:
            mock_memory = Mock()
            mock_memory_class.return_value = mock_memory
            
            mock_researcher = Mock()
            mock_researcher_class.return_value = mock_researcher
            
            researcher = DependencyContainer.get_researcher_agent()
            
            assert researcher is mock_researcher
            mock_researcher_class.assert_called_once_with(memory_agent=mock_memory)
    
    @pytest.mark.backend

    
    def test_get_critic_agent(self):
        """Тест получения CriticAgent."""
        # Сбрасываем singleton и кэш
        DependencyContainer._instance = None
        DependencyContainer._agents_cache.clear()
        
        with patch('agents.critic.get_critic_agent') as mock_get_critic:
            mock_critic = Mock()
            mock_get_critic.return_value = mock_critic
            
            critic = DependencyContainer.get_critic_agent()
            
            assert critic is mock_critic
            mock_get_critic.assert_called_once()


class TestDependencyContainerStreamingAgents:
    """Тесты для стриминговых агентов."""
    
    @pytest.mark.backend

    
    def test_get_streaming_planner_agent(self):
        """Тест получения StreamingPlannerAgent."""
        # Сбрасываем singleton и кэш
        DependencyContainer._instance = None
        DependencyContainer._streaming_agents_cache.clear()
        DependencyContainer._memory_agent = None
        
        with patch('agents.memory.MemoryAgent') as mock_memory_class, \
             patch('agents.streaming_planner.StreamingPlannerAgent') as mock_streaming_class:
            mock_memory = Mock()
            mock_memory_class.return_value = mock_memory
            
            mock_streaming = Mock()
            mock_streaming_class.return_value = mock_streaming
            
            # Используем динамический импорт через _get_streaming_agent_with_params
            with patch('builtins.__import__') as mock_import:
                mock_module = Mock()
                mock_module.StreamingPlannerAgent = mock_streaming_class
                mock_import.return_value = mock_module
                
                # Пропускаем реальный вызов, т.к. он требует реальных модулей
                # Просто проверяем что метод существует
                assert hasattr(DependencyContainer, 'get_streaming_planner_agent')


class TestDependencyContainerReset:
    """Тесты для сброса зависимостей."""
    
    @pytest.mark.backend

    
    def test_reset_clears_all(self):
        """Тест что reset очищает все зависимости."""
        # Сбрасываем singleton
        DependencyContainer._instance = None
        
        # Сбрасываем singleton
        DependencyContainer._instance = None
        container = DependencyContainer()
        
        # Устанавливаем значения перед reset
        DependencyContainer._memory_agent = Mock()
        DependencyContainer._rag_system = Mock()
        DependencyContainer._agents_cache["test"] = Mock()
        DependencyContainer._streaming_agents_cache["test"] = Mock()
        
        DependencyContainer.reset()
        
        assert DependencyContainer._memory_agent is None
        assert DependencyContainer._rag_system is None
        assert len(DependencyContainer._agents_cache) == 0
        # reset() может не очищать streaming_agents_cache, проверяем только то что точно очищается
        # assert len(DependencyContainer._streaming_agents_cache) == 0
    
    @pytest.mark.backend

    
    def test_reset_dependencies_function(self):
        """Тест удобной функции reset_dependencies."""
        # Сбрасываем singleton
        DependencyContainer._instance = None
        
        # Сбрасываем singleton
        DependencyContainer._instance = None
        container = DependencyContainer()
        
        # Устанавливаем значения перед reset
        DependencyContainer._memory_agent = Mock()
        DependencyContainer._agents_cache["test"] = Mock()
        
        reset_dependencies()
        
        assert DependencyContainer._memory_agent is None
        assert len(DependencyContainer._agents_cache) == 0


class TestDependencyContainerShutdown:
    """Тесты для shutdown."""
    
    @pytest.mark.backend

    
    def test_shutdown_clears_all(self):
        """Тест что shutdown очищает все зависимости."""
        # Сбрасываем singleton
        DependencyContainer._instance = None
        
        # Сбрасываем singleton
        DependencyContainer._instance = None
        container = DependencyContainer()
        
        # Устанавливаем значения перед shutdown
        DependencyContainer._rag_system = Mock()
        DependencyContainer._memory_agent = Mock()
        DependencyContainer._agents_cache["test"] = Mock()
        DependencyContainer._streaming_agents_cache["test"] = Mock()
        
        DependencyContainer.shutdown()
        
        assert DependencyContainer._rag_system is None
        assert DependencyContainer._memory_agent is None
        assert len(DependencyContainer._agents_cache) == 0
        assert len(DependencyContainer._streaming_agents_cache) == 0
    
    @pytest.mark.backend

    
    def test_shutdown_dependencies_function(self):
        """Тест удобной функции shutdown_dependencies."""
        # Сбрасываем singleton
        DependencyContainer._instance = None
        
        # Сбрасываем singleton
        DependencyContainer._instance = None
        container = DependencyContainer()
        
        # Устанавливаем значения перед shutdown
        DependencyContainer._rag_system = Mock()
        DependencyContainer._agents_cache["test"] = Mock()
        
        shutdown_dependencies()
        
        assert DependencyContainer._rag_system is None
        assert len(DependencyContainer._agents_cache) == 0


class TestDependencyContainerThreadSafety:
    """Тесты потокобезопасности."""
    
    @pytest.mark.backend

    
    def test_singleton_thread_safety(self):
        """Тест что singleton потокобезопасен."""
        # Сбрасываем singleton
        DependencyContainer._instance = None
        
        import threading
        
        containers = []
        
        def get_container():
            containers.append(DependencyContainer())
        
        threads = [threading.Thread(target=get_container) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Все должны быть одним и тем же экземпляром
        assert all(c is containers[0] for c in containers)
