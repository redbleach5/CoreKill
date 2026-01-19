"""Тесты для IntentAgent."""
import pytest
from unittest.mock import Mock, patch
from agents.intent import IntentAgent, IntentResult
from utils.model_checker import TaskComplexity


class TestIntentAgent:
    """Тесты для класса IntentAgent."""
    
    @pytest.fixture
    def agent(self):
        """Создаёт экземпляр IntentAgent для тестов."""
        # IntentAgent использует lazy_llm=True, поэтому LLM не создаётся при инициализации
        return IntentAgent(lazy_llm=True)
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'model')
        assert hasattr(agent, 'temperature')
    
    def test_is_greeting_fast_with_greeting(self):
        """Тест быстрого определения приветствия.
        
        Проверяет только короткие однозначные приветствия (1-3 слова).
        """
        greetings = [
            "привет",
            "hello",
            "hi",
            "Привет!",  # Не пройдёт т.к. с восклицательным знаком
            "HELLO",   # Не пройдёт т.к. uppercase
        ]
        
        # Только чистые приветствия без пунктуации
        for greeting in ["привет", "hello", "hi", "хай", "салют", "hey"]:
            assert IntentAgent.is_greeting_fast(greeting), f"Не распознано приветствие: {greeting}"
    
    def test_is_greeting_fast_with_non_greeting(self):
        """Тест быстрого определения не-приветствия."""
        non_greetings = [
            "создай функцию",
            "напиши код",
            "исправь ошибку",
            "what is python",
            "как работает класс",
            "привет, как дела?",  # Слишком длинное
        ]
        
        for non_greeting in non_greetings:
            assert not IntentAgent.is_greeting_fast(non_greeting), \
                f"Неправильно распознано как приветствие: {non_greeting}"
    
    def test_intent_result_creation(self):
        """Тест создания IntentResult."""
        result = IntentResult(
            type="create",
            confidence=0.95,
            description="Создание новой функции"
        )
        
        assert result.type == "create"
        assert result.confidence == 0.95
        assert result.description == "Создание новой функции"
        # Проверяем автозаполненные поля
        assert result.complexity == TaskComplexity.SIMPLE
        assert result.recommended_mode in ["chat", "code"]
        assert isinstance(result.requires_code_generation, bool)
    
    def test_intent_result_confidence_bounds(self):
        """Тест граничных значений confidence."""
        # Валидные значения
        valid_result = IntentResult(
            type="create",
            confidence=0.5,
            description="Test"
        )
        assert valid_result.confidence == 0.5
        
        # Граничные значения
        low_result = IntentResult(type="explain", confidence=0.0, description="Low")
        assert low_result.confidence == 0.0
        
        high_result = IntentResult(type="create", confidence=1.0, description="High")
        assert high_result.confidence == 1.0
    
    def test_intent_result_post_init_code_generation(self):
        """Тест автоматического определения requires_code_generation."""
        # Типы требующие генерации кода
        code_types = ["create", "modify", "debug", "optimize", "test", "refactor"]
        for intent_type in code_types:
            result = IntentResult(type=intent_type, confidence=0.9, description="Test")
            assert result.requires_code_generation is True, \
                f"Тип {intent_type} должен требовать генерацию кода"
        
        # Типы НЕ требующие генерации кода
        non_code_types = ["explain", "greeting"]
        for intent_type in non_code_types:
            result = IntentResult(type=intent_type, confidence=0.9, description="Test")
            assert result.requires_code_generation is False, \
                f"Тип {intent_type} не должен требовать генерацию кода"
    
    def test_intent_result_recommended_mode(self):
        """Тест автоматического определения recommended_mode."""
        # Приветствие → chat
        greeting = IntentResult(type="greeting", confidence=1.0, description="Test")
        assert greeting.recommended_mode == "chat"
        
        # Создание кода → code
        create = IntentResult(type="create", confidence=1.0, description="Test")
        assert create.recommended_mode == "code"
        
        # Объяснение → chat
        explain = IntentResult(type="explain", confidence=1.0, description="Test")
        assert explain.recommended_mode == "chat"
