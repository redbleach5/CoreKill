"""Тесты для ResearcherAgent."""
import pytest
from agents.researcher import ResearcherAgent


class TestResearcherAgent:
    """Тесты для класса ResearcherAgent."""
    
    @pytest.fixture
    def agent(self):
        """Создаёт экземпляр ResearcherAgent для тестов."""
        return ResearcherAgent(temperature=0.25)
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'llm')
        assert hasattr(agent, 'rag')
