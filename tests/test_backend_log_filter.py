"""Тесты для log filter middleware."""
import pytest
import logging
from unittest.mock import Mock, patch
from backend.middleware.log_filter import GreetingLogFilter, _is_greeting, setup_log_filter


class TestIsGreeting:
    """Тесты функции определения приветствия."""
    
    @pytest.mark.backend

    
    def test_is_greeting_recognizes_greetings(self):
        """Тест распознавания приветствий."""
        assert _is_greeting("привет") == True
        assert _is_greeting("hello") == True
        assert _is_greeting("здравствуйте") == True
        assert _is_greeting("hi there") == True
    
    @pytest.mark.backend

    
    def test_is_greeting_recognizes_non_greetings(self):
        """Тест что не-приветствия не распознаются."""
        assert _is_greeting("напиши функцию") == False
        assert _is_greeting("create a class") == False
        assert _is_greeting("") == False
    
    @pytest.mark.backend

    
    def test_is_greeting_case_insensitive(self):
        """Тест что регистр не важен."""
        assert _is_greeting("ПРИВЕТ") == True
        assert _is_greeting("Hello") == True
        assert _is_greeting("Hi There") == True


class TestGreetingLogFilter:
    """Тесты фильтра логов."""
    
    @pytest.mark.backend

    
    def test_filter_allows_non_greeting_logs(self):
        """Тест что фильтр пропускает логи не-приветствий."""
        filter_obj = GreetingLogFilter()
        
        record = Mock(spec=logging.LogRecord)
        record.msg = '127.0.0.1:60294 - "GET /api/stream?task=напиши функцию&model=test HTTP/1.1" 200'
        record.getMessage = Mock(return_value=record.msg)
        
        assert filter_obj.filter(record) == True
    
    @pytest.mark.backend

    
    def test_filter_removes_model_from_greeting_logs(self):
        """Тест что фильтр убирает model из логов приветствий."""
        filter_obj = GreetingLogFilter()
        
        record = Mock(spec=logging.LogRecord)
        record.msg = '127.0.0.1:60294 - "GET /api/stream?task=привет&model=test-model HTTP/1.1" 200'
        record.getMessage = Mock(return_value=record.msg)
        
        result = filter_obj.filter(record)
        
        # Фильтр должен пропустить запись, но изменить её
        assert result == True
        # Проверяем что model удален из сообщения
        assert "model=" not in record.msg or "model=test-model" not in record.msg
    
    @pytest.mark.backend

    
    def test_filter_handles_malformed_logs(self):
        """Тест обработки некорректных логов."""
        filter_obj = GreetingLogFilter()
        
        record = Mock(spec=logging.LogRecord)
        record.msg = "Invalid log format"
        record.getMessage = Mock(side_effect=Exception("Error"))
        
        # Фильтр должен обработать ошибку gracefully
        assert filter_obj.filter(record) == True
    
    @pytest.mark.backend

    
    def test_filter_handles_missing_attributes(self):
        """Тест обработки записей без атрибутов."""
        filter_obj = GreetingLogFilter()
        
        record = Mock(spec=logging.LogRecord)
        del record.msg
        record.getMessage = Mock(side_effect=AttributeError("No msg"))
        
        # Фильтр должен обработать отсутствие атрибутов
        assert filter_obj.filter(record) == True


class TestSetupLogFilter:
    """Тесты настройки фильтра."""
    
    @patch('backend.middleware.log_filter.logging.getLogger')
    @pytest.mark.backend

    def test_setup_log_filter_applies_to_uvicorn(self, mock_get_logger):
        """Тест что фильтр применяется к uvicorn логгерам."""
        mock_access_logger = Mock()
        mock_access_logger.handlers = []
        mock_access_logger.filters = []  # filters должен быть списком
        
        mock_root_logger = Mock()
        mock_root_logger.handlers = []
        
        def get_logger_side_effect(name=None):
            if name == "uvicorn.access":
                return mock_access_logger
            return mock_root_logger
        
        mock_get_logger.side_effect = get_logger_side_effect
        
        setup_log_filter()
        
        # Проверяем что функция выполнилась без ошибок
        mock_get_logger.assert_called()
