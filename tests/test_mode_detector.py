"""Тесты для ModeDetector."""
import pytest
from backend.mode_detector import ModeDetector
from utils.model_checker import TaskComplexity
from unittest.mock import Mock, patch


@pytest.fixture
def detector():
    """Создаёт экземпляр ModeDetector для тестов."""
    return ModeDetector()


class TestModeDetector:
    """Тесты для ModeDetector."""
    
    def test_detect_chat_mode(self, detector):
        """Тест явного режима chat."""
        mode, intent, complexity = detector.detect(
            task="test",
            user_mode="chat"
        )
        
        assert mode == "chat"
    
    def test_detect_code_mode(self, detector):
        """Тест явного режима code."""
        mode, intent, complexity = detector.detect(
            task="test",
            user_mode="code"
        )
        
        assert mode == "code"
    
    @patch('backend.mode_detector.IntentAgent.is_greeting_fast')
    def test_detect_auto_greeting(self, mock_greeting, detector):
        """Тест автоматического определения greeting."""
        mock_greeting.return_value = True
        
        mode, intent, complexity = detector.detect(
            task="привет",
            user_mode="auto"
        )
        
        assert mode == "chat"
        assert intent == "greeting"
        assert complexity == TaskComplexity.SIMPLE
    
    def test_detect_auto_code_keywords(self, detector):
        """Тест автоматического определения code по ключевым словам."""
        mode, intent, complexity = detector.detect(
            task="напиши функцию",
            user_mode="auto"
        )
        
        assert mode == "code"
    
    def test_detect_auto_chat_keywords(self, detector):
        """Тест автоматического определения chat по ключевым словам."""
        mode, intent, complexity = detector.detect(
            task="объясни как работает",
            user_mode="auto"
        )
        
        assert mode == "chat"
        assert intent == "explain"
    
    def test_detect_auto_analyze_keywords(self, detector):
        """Тест автоматического определения analyze по ключевым словам."""
        mode, intent, complexity = detector.detect(
            task="проанализируй проект",
            user_mode="auto"
        )
        
        assert mode == "analyze"
        assert intent == "analyze"
        assert complexity == TaskComplexity.COMPLEX
    
    def test_detect_auto_learning_request(self, detector):
        """Тест определения обучающего запроса."""
        mode, intent, complexity = detector.detect(
            task="научи меня программировать",
            user_mode="auto"
        )
        
        assert mode == "chat"
        assert intent == "explain"
        assert complexity == TaskComplexity.SIMPLE
    
    @patch('backend.mode_detector.IntentAgent.is_greeting_fast', return_value=False)
    def test_detect_auto_llm_fallback(self, mock_is_greeting, detector):
        """Тест fallback на LLM для неопределённых случаев."""
        mock_intent_result = Mock()
        mock_intent_result.recommended_mode = "code"
        mock_intent_result.type = "create"
        
        mock_intent_agent = Mock()
        mock_intent_agent.determine_intent.return_value = mock_intent_result
        mock_intent_agent._estimate_complexity_heuristic.return_value = TaskComplexity.MEDIUM
        
        detector.intent_agent = mock_intent_agent
        
        mode, intent, complexity = detector.detect(
            task="неопределённый запрос",
            user_mode="auto"
        )
        
        assert mode == "code"
        assert intent == "create"
        assert complexity == TaskComplexity.MEDIUM
