"""Тесты для PlannerAgent."""
import pytest
from unittest.mock import Mock, patch
from agents.planner import PlannerAgent
from tests.test_utils import create_mock_agent_dependencies, create_mock_model_router


class TestPlannerAgent:
    """Тесты для класса PlannerAgent."""
    
    @pytest.fixture
    def agent(self, mock_agent_dependencies):
        """Создаёт экземпляр PlannerAgent для тестов."""
        from utils.model_checker import ModelInfo
        mock_models = {
            "test-model": ModelInfo(
                name="test-model",
                size_bytes=7 * 1024 * 1024 * 1024,
                parameter_size="7B",
                quantization="Q4_K_M",
                family="test",
                is_coder=True,
                is_reasoning=False,
                estimated_quality=0.7
            )
        }
        with patch('infrastructure.model_router.scan_available_models', return_value=mock_models), \
             patch('infrastructure.model_router.get_all_reasoning_models', return_value=[]), \
             patch('infrastructure.model_router.get_model_router', return_value=create_mock_model_router()), \
             patch('utils.model_checker.check_model_available', return_value=True), \
             patch.multiple('agents.planner', **mock_agent_dependencies):
            return PlannerAgent(temperature=0.25)
    
    @pytest.mark.agents

    
    def test_init(self, agent):
        """Тест инициализации агента."""
        with patch('utils.model_checker.check_model_available', return_value=True):
            assert agent is not None
            assert hasattr(agent, 'llm')
    
    @pytest.mark.agents

    
    def test_init_with_custom_model(self):
        """Тест инициализации с кастомной моделью."""
        from utils.model_checker import ModelInfo
        mock_models = {
            "custom-model": ModelInfo(
                name="custom-model",
                size_bytes=7 * 1024 * 1024 * 1024,
                parameter_size="7B",
                quantization="Q4_K_M",
                family="test",
                is_coder=True,
                is_reasoning=False,
                estimated_quality=0.7
            )
        }
        with patch('infrastructure.model_router.scan_available_models', return_value=mock_models), \
             patch('infrastructure.model_router.get_all_reasoning_models', return_value=[]), \
             patch('infrastructure.model_router.get_model_router') as mock_router, \
             patch('utils.model_checker.check_model_available', return_value=True):
            mock_router_instance = Mock()
            mock_router_instance.select_model.return_value = Mock(model="custom-model")
            mock_router.return_value = mock_router_instance
            
            with patch('agents.base.create_llm_for_stage') as mock_llm:
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
