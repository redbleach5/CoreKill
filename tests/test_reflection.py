"""Тесты для ReflectionAgent."""
import pytest
from agents.reflection import ReflectionAgent, ReflectionResult


class TestReflectionAgent:
    """Тесты для класса ReflectionAgent."""
    
    @pytest.fixture
    def agent(self):
        """Создаёт экземпляр ReflectionAgent для тестов."""
        return ReflectionAgent(temperature=0.25)
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'llm')
    
    def test_reflection_result_creation(self):
        """Тест создания ReflectionResult."""
        result = ReflectionResult(
            planning_score=0.8,
            research_score=0.85,
            testing_score=0.9,
            coding_score=0.88,
            overall_score=0.875,
            analysis="Good implementation",
            improvements="Could be faster",
            should_retry=False
        )
        
        assert result.planning_score == 0.8
        assert result.overall_score == 0.875
        assert result.should_retry is False
