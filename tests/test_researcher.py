"""Тесты для ResearcherAgent."""
import pytest
from unittest.mock import Mock, patch
from agents.researcher import ResearcherAgent


class TestResearcherAgent:
    """Тесты для класса ResearcherAgent."""
    
    @pytest.fixture
    def agent(self):
        """Создаёт экземпляр ResearcherAgent для тестов."""
        with patch('agents.researcher.RAGSystem') as mock_rag:
            with patch('agents.researcher.ContextEngine') as mock_ce:
                mock_rag.return_value = Mock()
                mock_ce.return_value = Mock()
                return ResearcherAgent()
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'rag')
        assert hasattr(agent, 'context_engine')
    
    def test_init_with_custom_components(self):
        """Тест инициализации с кастомными компонентами."""
        mock_rag = Mock()
        mock_memory = Mock()
        mock_context = Mock()
        
        agent = ResearcherAgent(
            rag_system=mock_rag,
            memory_agent=mock_memory,
            context_engine=mock_context
        )
        
        assert agent.rag == mock_rag
        assert agent.memory == mock_memory
        assert agent.context_engine == mock_context
