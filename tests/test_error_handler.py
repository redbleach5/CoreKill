"""Тесты для обработки ошибок."""
import pytest
from backend.error_handler import RetryConfig


class TestRetryConfig:
    """Тесты для RetryConfig."""
    
    def test_default_config(self):
        """Тест конфигурации по умолчанию."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
    
    def test_custom_config(self):
        """Тест кастомной конфигурации."""
        config = RetryConfig(max_attempts=5, initial_delay=0.5)
        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
    
    def test_get_delay(self):
        """Тест вычисления задержки."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)
        
        delay_0 = config.get_delay(0)
        assert delay_0 == 1.0
        
        delay_1 = config.get_delay(1)
        assert delay_1 == 2.0
    
    def test_max_delay_limit(self):
        """Тест ограничения максимальной задержки."""
        config = RetryConfig(
            initial_delay=1.0,
            max_delay=5.0,
            exponential_base=10.0,
            jitter=False
        )
        
        # Даже с большим exponential_base, задержка не превышает max_delay
        delay = config.get_delay(5)
        assert delay <= 5.0
