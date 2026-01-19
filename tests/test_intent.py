"""Тесты для IntentAgent."""
import pytest
from agents.intent import IntentAgent, IntentResult


class TestIntentAgent:
    """Тесты для класса IntentAgent."""
    
    @pytest.fixture
    def agent(self):
        """Создаёт экземпляр IntentAgent для тестов."""
        return IntentAgent()
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'llm')
        assert hasattr(agent, 'prompt_enhancer')
    
    def test_is_greeting_fast_with_greeting(self):
        """Тест быстрого определения приветствия."""
        greetings = [
            "привет",
            "hello",
            "hi",
            "привет, как дела?",
            "Привет!",
            "HELLO",
        ]
        
        for greeting in greetings:
            assert IntentAgent.is_greeting_fast(greeting), f"Не распознано приветствие: {greeting}"
    
    def test_is_greeting_fast_with_non_greeting(self):
        """Тест быстрого определения не-приветствия."""
        non_greetings = [
            "создай функцию",
            "напиши код",
            "исправь ошибку",
            "what is python",
            "как работает класс",
        ]
        
        for non_greeting in non_greetings:
            assert not IntentAgent.is_greeting_fast(non_greeting), \
                f"Неправильно распознано как приветствие: {non_greeting}"
    
    def test_is_help_fast_with_help(self):
        """Тест быстрого определения запроса помощи."""
        help_requests = [
            "помощь",
            "help",
            "что ты можешь делать",
            "помоги мне",
            "HELP",
            "помощь пожалуйста",
        ]
        
        for help_req in help_requests:
            assert IntentAgent.is_help_fast(help_req), f"Не распознан запрос помощи: {help_req}"
    
    def test_is_help_fast_with_non_help(self):
        """Тест быстрого определения не-помощи."""
        non_help = [
            "создай функцию",
            "привет",
            "напиши тесты",
            "исправь баг",
        ]
        
        for item in non_help:
            assert not IntentAgent.is_help_fast(item), \
                f"Неправильно распознано как помощь: {item}"
    
    def test_intent_result_creation(self):
        """Тест создания IntentResult."""
        result = IntentResult(
            type="create",
            confidence=0.95,
            description="Создание новой функции",
            reasoning="Пользователь просит создать функцию"
        )
        
        assert result.type == "create"
        assert result.confidence == 0.95
        assert result.description == "Создание новой функции"
        assert result.reasoning == "Пользователь просит создать функцию"
    
    def test_intent_result_confidence_bounds(self):
        """Тест граничных значений confidence."""
        # Валидные значения
        valid_result = IntentResult(
            type="create",
            confidence=0.5,
            description="Test",
            reasoning="Test"
        )
        assert valid_result.confidence == 0.5
        
        # Граничные значения
        min_result = IntentResult(
            type="create",
            confidence=0.0,
            description="Test",
            reasoning="Test"
        )
        assert min_result.confidence == 0.0
        
        max_result = IntentResult(
            type="create",
            confidence=1.0,
            description="Test",
            reasoning="Test"
        )
        assert max_result.confidence == 1.0
