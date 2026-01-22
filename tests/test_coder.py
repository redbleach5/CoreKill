"""Тесты для CoderAgent."""
import pytest
from unittest.mock import Mock, patch
from agents.coder import CoderAgent
from tests.test_utils import create_mock_agent_dependencies
from tests.factories import TEST_MODELS


class TestCoderAgent:
    """Тесты для класса CoderAgent."""
    
    @pytest.fixture
    def agent(self, mock_agent_dependencies):
        """Создаёт экземпляр CoderAgent для тестов."""
        with patch.multiple(
            'agents.coder',
            **mock_agent_dependencies,
            get_prompt_enhancer=Mock(return_value=Mock())
        ):
            return CoderAgent(temperature=0.25, user_query="test query")
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'llm')
        assert hasattr(agent, 'prompt_enhancer')
        assert agent.user_query == "test query"
    
    def test_init_with_custom_model(self, mock_agent_dependencies):
        """Тест инициализации с кастомной моделью."""
        custom_model = TEST_MODELS["medium"]
        with patch.multiple(
            'agents.coder',
            **create_mock_agent_dependencies(model=custom_model, temperature=0.3),
            get_prompt_enhancer=Mock(return_value=Mock())
        ):
            agent = CoderAgent(model=custom_model, temperature=0.3)
            
            assert agent is not None
            assert hasattr(agent, 'llm')
                top_p=0.9
            )
    
    def test_init_default_temperature(self):
        """Тест инициализации с температурой по умолчанию."""
        with patch('agents.coder.get_model_router') as mock_router, \
             patch('agents.coder.create_llm_for_stage') as mock_llm, \
             patch('agents.coder.get_prompt_enhancer') as mock_enhancer:
            mock_router.return_value = Mock(select_model=Mock(return_value=Mock(model="test-model")))
            mock_llm.return_value = Mock()
            mock_enhancer.return_value = Mock()
            
            agent = CoderAgent()
            
            # Проверяем что вызван с temperature=0.25 (дефолт)
            call_kwargs = mock_llm.call_args.kwargs
            assert call_kwargs.get('temperature') == 0.25
    
    def test_generate_code_with_greeting_intent(self, agent):
        """Тест что код не генерируется для приветствия."""
        result = agent.generate_code(
            plan="",
            tests="",
            context="",
            intent_type="greeting",
            user_query="привет"
        )
        
        # Для greeting должна вернуться пустая строка
        assert result == ""
    
    def test_generate_code_with_help_intent(self, agent):
        """Тест генерации для help intent (help проходит через генерацию)."""
        # Мокаем llm.generate чтобы вернуть код
        agent.llm.generate.return_value = "# help response"
        
        result = agent.generate_code(
            plan="",
            tests="",
            context="",
            intent_type="help",
            user_query="помощь"
        )
        
        # Для help код генерируется (в отличие от greeting)
        assert isinstance(result, str)
    
    def test_generate_code_returns_string(self, agent):
        """Тест что generate_code возвращает строку."""
        # Мокаем llm.generate чтобы вернуть код
        agent.llm.generate.return_value = "def example(): pass"
        
        result = agent.generate_code(
            plan="Create a simple function",
            tests="def test_example(): pass",
            context="Python function",
            intent_type="create",
            user_query="create function"
        )
        
        assert isinstance(result, str)
    
    def test_user_query_stored(self):
        """Тест что user_query сохраняется."""
        with mock_coder_dependencies():
            query = "test user query"
            agent = CoderAgent(user_query=query)
            assert agent.user_query == query
    
    def test_empty_user_query(self):
        """Тест инициализации с пустым user_query."""
        with mock_coder_dependencies():
            agent = CoderAgent(user_query="")
            assert agent.user_query == ""
