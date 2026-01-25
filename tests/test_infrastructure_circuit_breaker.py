"""Тесты для circuit breaker."""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    get_circuit_breaker
)


@pytest.fixture
def circuit_breaker():
    """Создает экземпляр CircuitBreaker."""
    return CircuitBreaker(
        name="test_breaker",
        failure_threshold=3,
        recovery_timeout=60.0,
        success_threshold=2
    )


class TestCircuitBreakerInit:
    """Тесты инициализации CircuitBreaker."""
    
    @pytest.mark.infrastructure

    
    def test_init_sets_defaults(self, circuit_breaker):
        """Тест что инициализация устанавливает значения по умолчанию."""
        assert circuit_breaker.name == "test_breaker"
        assert circuit_breaker.failure_threshold == 3
        assert circuit_breaker.recovery_timeout == 60.0
        assert circuit_breaker.success_threshold == 2
        assert circuit_breaker.stats.state == CircuitState.CLOSED
    
    @pytest.mark.infrastructure

    
    def test_init_creates_stats(self, circuit_breaker):
        """Тест что создается статистика."""
        assert hasattr(circuit_breaker, 'stats')
        assert circuit_breaker.stats.failures == 0
        assert circuit_breaker.stats.successes == 0
        assert circuit_breaker.stats.state == CircuitState.CLOSED


class TestCircuitState:
    """Тесты для состояния circuit breaker."""
    
    @pytest.mark.infrastructure

    
    def test_state_closed_by_default(self, circuit_breaker):
        """Тест что состояние закрыто по умолчанию."""
        assert circuit_breaker.stats.state == CircuitState.CLOSED


class TestCall:
    """Тесты для call метода."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_call_success_closed_state(self, circuit_breaker):
        """Тест успешного вызова в закрытом состоянии."""
        async def success_func():
            return "success"
        
        result = await circuit_breaker.call(success_func)
        
        assert result == "success"
        assert circuit_breaker.stats.successes == 1
        assert circuit_breaker.stats.failures == 0
        assert circuit_breaker.stats.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_call_failure_increments_count(self, circuit_breaker):
        """Тест что ошибка увеличивает счетчик."""
        async def failing_func():
            raise Exception("Test error")
        
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.stats.failures == 1
        assert circuit_breaker.stats.successes == 0
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_call_opens_after_threshold(self, circuit_breaker):
        """Тест что circuit breaker открывается после порога ошибок."""
        async def failing_func():
            raise Exception("Test error")
        
        # Делаем 3 ошибки (порог)
        for _ in range(3):
            try:
                await circuit_breaker.call(failing_func)
            except Exception:
                pass
        
        # Следующий вызов должен выбросить CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.stats.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_call_half_open_state(self, circuit_breaker):
        """Тест работы в half-open состоянии."""
        from datetime import datetime, timedelta
        # Открываем circuit breaker
        circuit_breaker.stats.failures = 3
        circuit_breaker.stats.state = CircuitState.OPEN
        circuit_breaker.stats.opened_at = datetime.now() - timedelta(seconds=61)  # Прошло больше recovery_timeout
        
        async def success_func():
            return "success"
        
        # В half-open состоянии должен пропустить вызов
        result = await circuit_breaker.call(success_func)
        
        assert result == "success"
        # После успешного вызова должен закрыться (если success_threshold достигнут)
        # Но для одного успешного вызова может остаться в HALF_OPEN
        assert circuit_breaker.stats.state in [CircuitState.CLOSED, CircuitState.HALF_OPEN]
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_call_half_open_failure(self, circuit_breaker):
        """Тест что ошибка в half-open возвращает в OPEN."""
        from datetime import datetime, timedelta
        # Открываем circuit breaker
        circuit_breaker.stats.failures = 3
        circuit_breaker.stats.state = CircuitState.OPEN
        circuit_breaker.stats.opened_at = datetime.now() - timedelta(seconds=61)
        
        async def failing_func():
            raise Exception("Test error")
        
        # В half-open состоянии ошибка должна вернуть в OPEN
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.stats.state == CircuitState.OPEN


class TestGetStats:
    """Тесты для get_stats."""
    
    @pytest.mark.infrastructure

    
    def test_get_stats_returns_dict(self, circuit_breaker):
        """Тест что get_stats возвращает словарь."""
        stats = circuit_breaker.get_stats()
        
        assert isinstance(stats, dict)
        assert "failures" in stats
        assert "successes" in stats
        assert "state" in stats


class TestGetCircuitBreaker:
    """Тесты для get_circuit_breaker."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_circuit_breaker_returns_instance(self):
        """Тест что get_circuit_breaker возвращает экземпляр."""
        breaker = await get_circuit_breaker("test_agent")
        
        assert isinstance(breaker, CircuitBreaker)
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_circuit_breaker_singleton_per_key(self):
        """Тест что разные ключи дают разные экземпляры."""
        breaker1 = await get_circuit_breaker("agent1")
        breaker2 = await get_circuit_breaker("agent2")
        
        assert breaker1 is not breaker2
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_get_circuit_breaker_same_key_same_instance(self):
        """Тест что одинаковый ключ дает тот же экземпляр."""
        breaker1 = await get_circuit_breaker("test_agent")
        breaker2 = await get_circuit_breaker("test_agent")
        
        assert breaker1 is breaker2
