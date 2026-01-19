"""Тесты для PlannerAgent."""
import pytest
from agents.planner import PlannerAgent


class TestPlannerAgent:
    """Тесты для класса PlannerAgent."""
    
    @pytest.fixture
    def agent(self):
        """Создаёт экземпляр PlannerAgent для тестов."""
        return PlannerAgent(temperature=0.25)
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'llm')
        assert hasattr(agent, 'prompt_enhancer')
    
    def test_init_with_custom_model(self):
        """Тест инициализации с кастомной моделью."""
        agent = PlannerAgent(model="test-model", temperature=0.3)
        assert agent is not None
        assert agent.llm.model == "test-model"
        assert agent.llm.temperature == 0.3
