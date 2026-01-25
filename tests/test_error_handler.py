"""Тесты для error_handler.py."""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from backend.error_handler import RetryConfig, async_retry, sync_retry


class TestRetryConfig:
    """Тесты для RetryConfig."""
    
    def test_retry_config_defaults(self):
        """Тест значений по умолчанию."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
    
    def test_retry_config_custom(self):
        """Тест кастомных значений."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=2.0,
            max_delay=60.0,
            exponential_base=3.0,
            jitter=False
        )
        assert config.max_attempts == 5
        assert config.initial_delay == 2.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 3.0
        assert config.jitter is False
    
    def test_get_delay_exponential(self):
        """Тест экспоненциального увеличения задержки."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)
        
        assert config.get_delay(0) == 1.0  # 1.0 * 2^0 = 1.0
        assert config.get_delay(1) == 2.0  # 1.0 * 2^1 = 2.0
        assert config.get_delay(2) == 4.0  # 1.0 * 2^2 = 4.0
    
    def test_get_delay_max_limit(self):
        """Тест ограничения максимальной задержки."""
        config = RetryConfig(initial_delay=10.0, max_delay=20.0, exponential_base=2.0, jitter=False)
        
        assert config.get_delay(0) == 10.0  # 10.0 * 2^0 = 10.0
        assert config.get_delay(1) == 20.0  # 10.0 * 2^1 = 20.0 (ограничено max_delay)
        assert config.get_delay(2) == 20.0  # 10.0 * 2^2 = 40.0, но ограничено 20.0
    
    def test_get_delay_jitter(self):
        """Тест добавления jitter к задержке."""
        config = RetryConfig(initial_delay=10.0, jitter=True)
        
        # Jitter добавляет случайное значение от 0.5 до 1.5
        delay = config.get_delay(0)
        assert 5.0 <= delay <= 15.0  # 10.0 * (0.5 + random) где random в [0, 1]


class TestAsyncRetry:
    """Тесты для async_retry декоратора."""
    
    @pytest.mark.asyncio
    async def test_async_retry_success_first_attempt(self):
        """Тест успешного выполнения с первой попытки."""
        call_count = 0
        
        @async_retry()
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_async_retry_success_after_retries(self):
        """Тест успешного выполнения после нескольких попыток."""
        call_count = 0
        
        @async_retry(RetryConfig(max_attempts=3, initial_delay=0.01))
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_async_retry_all_attempts_failed(self):
        """Тест исчерпания всех попыток."""
        call_count = 0
        
        @async_retry(RetryConfig(max_attempts=3, initial_delay=0.01))
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")
        
        with pytest.raises(ValueError, match="Persistent error"):
            await test_func()
        
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_retry_custom_exceptions(self):
        """Тест retry только для определенных исключений."""
        call_count = 0
        
        @async_retry(RetryConfig(max_attempts=2, initial_delay=0.01, retriable_exceptions=(ValueError,)))
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retriable")
        
        with pytest.raises(TypeError, match="Not retriable"):
            await test_func()
        
        assert call_count == 1  # Не должно быть retry для TypeError (не в retriable_exceptions)
    
    @pytest.mark.asyncio
    async def test_async_retry_delay_timing(self):
        """Тест что задержка действительно происходит."""
        call_times = []
        
        @async_retry(RetryConfig(max_attempts=2, initial_delay=0.1, jitter=False))
        async def test_func():
            call_times.append(time.time())
            raise ValueError("Error")
        
        start_time = time.time()
        with pytest.raises(ValueError):
            await test_func()
        end_time = time.time()
        
        # Должна быть задержка между попытками
        assert len(call_times) == 2
        assert call_times[1] - call_times[0] >= 0.1  # Минимум 0.1 секунды задержки
        assert end_time - start_time >= 0.1


class TestSyncRetry:
    """Тесты для sync_retry декоратора."""
    
    def test_sync_retry_success_first_attempt(self):
        """Тест успешного выполнения с первой попытки."""
        call_count = 0
        
        @sync_retry()
        def test_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = test_func()
        assert result == "success"
        assert call_count == 1
    
    def test_sync_retry_success_after_retries(self):
        """Тест успешного выполнения после нескольких попыток."""
        call_count = 0
        
        @sync_retry(RetryConfig(max_attempts=3, initial_delay=0.01))
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = test_func()
        assert result == "success"
        assert call_count == 2
    
    def test_sync_retry_all_attempts_failed(self):
        """Тест исчерпания всех попыток."""
        call_count = 0
        
        @sync_retry(RetryConfig(max_attempts=3, initial_delay=0.01))
        def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")
        
        with pytest.raises(ValueError, match="Persistent error"):
            test_func()
        
        assert call_count == 3
    
    def test_sync_retry_custom_exceptions(self):
        """Тест retry только для определенных исключений."""
        call_count = 0
        
        @sync_retry(RetryConfig(max_attempts=2, initial_delay=0.01, retriable_exceptions=(ValueError,)))
        def test_func():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retriable")
        
        with pytest.raises(TypeError, match="Not retriable"):
            test_func()
        
        assert call_count == 1  # Не должно быть retry для TypeError (не в retriable_exceptions)
    
    def test_sync_retry_delay_timing(self):
        """Тест что задержка действительно происходит (используется time.sleep)."""
        call_times = []
        
        @sync_retry(RetryConfig(max_attempts=2, initial_delay=0.1, jitter=False))
        def test_func():
            call_times.append(time.time())
            raise ValueError("Error")
        
        start_time = time.time()
        with pytest.raises(ValueError):
            test_func()
        end_time = time.time()
        
        # Должна быть задержка между попытками
        assert len(call_times) == 2
        assert call_times[1] - call_times[0] >= 0.1  # Минимум 0.1 секунды задержки
        assert end_time - start_time >= 0.1
    
    def test_sync_retry_no_asyncio_run(self):
        """Тест что sync_retry не использует asyncio.run (критично для работы в event loop)."""
        # Этот тест проверяет, что sync_retry можно использовать внутри async функции
        # без блокировки event loop
        
        @sync_retry(RetryConfig(max_attempts=2, initial_delay=0.01))
        def sync_function():
            return "success"
        
        async def async_wrapper():
            # Если sync_retry использует asyncio.run, это вызовет RuntimeError
            return sync_function()
        
        # Не должно быть RuntimeError
        result = asyncio.run(async_wrapper())
        assert result == "success"


class TestRetryIntegration:
    """Интеграционные тесты для retry логики."""
    
    @pytest.mark.asyncio
    async def test_async_retry_with_network_simulation(self):
        """Симуляция сетевого запроса с retry."""
        attempts = []
        
        @async_retry(RetryConfig(max_attempts=3, initial_delay=0.01))
        async def network_request():
            attempts.append(time.time())
            if len(attempts) < 3:
                raise ConnectionError("Network error")
            return {"status": "ok", "data": "success"}
        
        result = await network_request()
        assert result["status"] == "ok"
        assert len(attempts) == 3
    
    def test_sync_retry_with_file_operation(self):
        """Симуляция операции с файлом с retry."""
        attempts = []
        
        @sync_retry(RetryConfig(max_attempts=3, initial_delay=0.01))
        def file_operation():
            attempts.append(time.time())
            if len(attempts) < 2:
                raise IOError("File locked")
            return "file_content"
        
        result = file_operation()
        assert result == "file_content"
        assert len(attempts) == 2
