"""Тесты для PlannerAgent."""
import pytest
from unittest.mock import Mock, patch
from agents.planner import PlannerAgent
from tests.test_utils import create_mock_agent_dependencies


class TestPlannerAgent:
    """Тесты для класса PlannerAgent."""
    
    @pytest.fixture
    def agent(self, mock_agent_dependencies):
        """Создаёт экземпляр PlannerAgent для тестов."""
        with patch.multiple('agents.planner', **mock_agent_dependencies):
            return PlannerAgent(temperature=0.25)
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'llm')
    
    def test_init_with_custom_model(self):
        """Тест инициализации с кастомной моделью."""
        with patch('agents.planner.get_model_router') as mock_router:
            mock_router_instance = Mock()
            mock_router_instance.select_model.return_value = Mock(model="custom-model")
            mock_router.return_value = mock_router_instance
            
            with patch('agents.planner.create_llm_for_stage') as mock_llm:
                mock_llm_instance = Mock(model="custom-model", temperature=0.3)
                mock_llm.return_value = mock_llm_instance
                
                agent = PlannerAgent(model="custom-model", temperature=0.3)
                assert agent is not None
                
                # Проверяем что create_llm_for_stage вызван с правильными параметрами
                mock_llm.assert_called_once_with(
                    stage="planning",
                    model="custom-model",
                    temperature=0.3,
                    top_p=0.9
                )
