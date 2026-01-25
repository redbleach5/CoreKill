"""Тесты для CoderAgent."""
import pytest
from unittest.mock import Mock, patch
from agents.coder import CoderAgent
from tests.test_utils import create_mock_agent_dependencies, create_mock_model_router
from tests.factories import TEST_MODELS


class TestCoderAgent:
    """Тесты для класса CoderAgent."""
    
    @pytest.fixture
    def agent(self, mock_agent_dependencies):
        """Создаёт экземпляр CoderAgent для тестов."""
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
             patch.multiple(
                'agents.coder',
                **mock_agent_dependencies,
                get_prompt_enhancer=Mock(return_value=Mock())
             ):
            return CoderAgent(temperature=0.25, user_query="test query")
    
    @pytest.mark.agents

    
    def test_init(self, agent):
        """Тест инициализации агента."""
        with patch('utils.model_checker.check_model_available', return_value=True):
            assert agent is not None
            assert hasattr(agent, 'llm')
            assert hasattr(agent, 'prompt_enhancer')
            assert agent.user_query == "test query"
    
    @pytest.mark.agents

    
    def test_init_with_custom_model(self, mock_agent_dependencies):
        """Тест инициализации с кастомной моделью."""
        from utils.model_checker import ModelInfo
        custom_model = TEST_MODELS["medium"]
        mock_models = {
            custom_model: ModelInfo(
                name=custom_model,
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
             patch('infrastructure.model_router.get_model_router', return_value=create_mock_model_router(custom_model)), \
             patch('utils.model_checker.check_model_available', return_value=True), \
             patch.multiple(
                'agents.coder',
                **create_mock_agent_dependencies(model=custom_model, temperature=0.3),
                get_prompt_enhancer=Mock(return_value=Mock())
             ):
            agent = CoderAgent(model=custom_model, temperature=0.3)
            
            assert agent is not None
            assert hasattr(agent, 'llm')
    
    @pytest.mark.agents

    
    def test_init_default_temperature(self):
        """Тест инициализации с температурой по умолчанию."""
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
             patch('infrastructure.model_router.get_model_router') as mock_router, \
             patch('agents.base.create_llm_for_stage') as mock_llm, \
             patch('agents.coder.get_prompt_enhancer') as mock_enhancer, \
             patch('utils.model_checker.check_model_available', return_value=True):
            mock_router.return_value = Mock(select_model=Mock(return_value=Mock(model="test-model")))
            mock_llm.return_value = Mock()
            mock_enhancer.return_value = Mock()
            
            agent = CoderAgent()
            
            # Проверяем что вызван с temperature=0.25 (дефолт)
            assert mock_llm.called
            call_kwargs = mock_llm.call_args.kwargs
            assert call_kwargs.get('temperature') == 0.25
    
    @pytest.mark.agents

    
    def test_generate_code_with_greeting_intent(self, agent):
        """Тест что код не генерируется для приветствия."""
        with patch('utils.model_checker.check_model_available', return_value=True):
            result = agent.generate_code(
                plan="",
                tests="",
                context="",
                intent_type="greeting",
                user_query="привет"
            )
            
            # Для greeting должна вернуться пустая строка
            assert result == ""
    
    @pytest.mark.agents

    
    def test_generate_code_with_help_intent(self, agent):
        """Тест генерации для help intent (help проходит через генерацию)."""
        # Мокаем llm.generate чтобы вернуть код
        with patch.object(agent.llm, 'generate', return_value="# help response"), \
             patch('utils.model_checker.check_model_available', return_value=True):
            result = agent.generate_code(
                plan="",
                tests="",
                context="",
                intent_type="help",
                user_query="помощь"
            )
            
            # Для help код генерируется (в отличие от greeting)
            assert isinstance(result, str)
    
    @pytest.mark.agents

    
    def test_generate_code_returns_string(self, agent):
        """Тест что generate_code возвращает строку."""
        # Мокаем llm.generate чтобы вернуть код
        with patch.object(agent.llm, 'generate', return_value="def example(): pass"), \
             patch('utils.model_checker.check_model_available', return_value=True):
            result = agent.generate_code(
                plan="Create a simple function",
                tests="def test_example(): pass",
                context="Python function",
                intent_type="create",
                user_query="create function"
            )
            
            assert isinstance(result, str)
    
    @pytest.mark.agents

    
    def test_user_query_stored(self, mock_agent_dependencies):
        """Тест что user_query сохраняется."""
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
             patch.multiple(
                'agents.coder',
                **mock_agent_dependencies,
                get_prompt_enhancer=Mock(return_value=Mock())
             ):
            query = "test user query"
            agent = CoderAgent(user_query=query)
            assert agent.user_query == query
    
    @pytest.mark.agents

    
    def test_empty_user_query(self, mock_agent_dependencies):
        """Тест инициализации с пустым user_query."""
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
             patch.multiple(
                'agents.coder',
                **mock_agent_dependencies,
                get_prompt_enhancer=Mock(return_value=Mock())
             ):
            agent = CoderAgent(user_query="")
            assert agent.user_query == ""
