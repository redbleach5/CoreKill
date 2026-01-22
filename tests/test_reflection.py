"""Тесты для ReflectionAgent."""
import pytest
from unittest.mock import Mock, patch
from agents.reflection import ReflectionAgent, ReflectionResult
from tests.test_utils import create_mock_agent_dependencies
from tests.factories import create_reflection_result


class TestReflectionAgent:
    """Тесты для класса ReflectionAgent."""
    
    @pytest.fixture
    def agent(self, mock_agent_dependencies):
        """Создаёт экземпляр ReflectionAgent для тестов."""
        with patch.multiple('agents.reflection', **mock_agent_dependencies):
            return ReflectionAgent(temperature=0.25)
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'llm')
    
    def test_reflection_result_creation(self):
        """Тест создания ReflectionResult."""
        result = create_reflection_result()
        
        assert result.planning_score == 0.8
        assert result.overall_score == 0.875
        assert result.should_retry is False
