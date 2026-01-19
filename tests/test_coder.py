"""Тесты для CoderAgent."""
import pytest
from agents.coder import CoderAgent


class TestCoderAgent:
    """Тесты для класса CoderAgent."""
    
    @pytest.fixture
    def agent(self):
        """Создаёт экземпляр CoderAgent для тестов."""
        return CoderAgent(temperature=0.25, user_query="test query")
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'llm')
        assert hasattr(agent, 'prompt_enhancer')
        assert agent.user_query == "test query"
    
    def test_init_with_custom_model(self):
        """Тест инициализации с кастомной моделью."""
        agent = CoderAgent(model="test-model", temperature=0.3)
        assert agent is not None
        assert agent.llm.model == "test-model"
        assert agent.llm.temperature == 0.3
    
    def test_init_default_temperature(self):
        """Тест инициализации с температурой по умолчанию."""
        agent = CoderAgent()
        assert agent.llm.temperature == 0.25
    
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
        """Тест что код не генерируется для помощи."""
        result = agent.generate_code(
            plan="",
            tests="",
            context="",
            intent_type="help",
            user_query="помощь"
        )
        
        # Для help должна вернуться пустая строка
        assert result == ""
    
    def test_generate_code_returns_string(self, agent):
        """Тест что generate_code возвращает строку."""
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
        query = "test user query"
        agent = CoderAgent(user_query=query)
        assert agent.user_query == query
    
    def test_empty_user_query(self):
        """Тест инициализации с пустым user_query."""
        agent = CoderAgent(user_query="")
        assert agent.user_query == ""
