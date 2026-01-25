"""Тесты для ReflectionAgent."""
import pytest
from unittest.mock import Mock, patch
from agents.reflection import ReflectionAgent, ReflectionResult
from tests.test_utils import create_mock_agent_dependencies, create_mock_model_router
from tests.factories import create_reflection_result


class TestReflectionAgent:
    """Тесты для класса ReflectionAgent."""
    
    @pytest.fixture
    def agent(self, mock_agent_dependencies):
        """Создаёт экземпляр ReflectionAgent для тестов."""
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
             patch.multiple('agents.reflection', **mock_agent_dependencies):
            return ReflectionAgent(temperature=0.25)
    
    @pytest.mark.agents

    
    def test_init(self, agent):
        """Тест инициализации агента."""
        with patch('utils.model_checker.check_model_available', return_value=True):
            assert agent is not None
            assert hasattr(agent, 'llm')
    
    @pytest.mark.agents

    
    def test_reflection_result_creation(self):
        """Тест создания ReflectionResult."""
        result = create_reflection_result()
        
        assert result.planning_score == 0.8
        assert result.overall_score == 0.875
        assert result.should_retry is False
