"""Тесты для rate limiter middleware."""
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request
from backend.middleware.rate_limiter import RateLimiterMiddleware


@pytest.fixture
def mock_app():
    """Мок FastAPI приложения."""
    return Mock()


@pytest.fixture
def rate_limiter(mock_app):
    """Создает экземпляр RateLimiterMiddleware."""
    return RateLimiterMiddleware(mock_app, requests_per_minute=10, cleanup_interval=60)


class TestRateLimitCheck:
    """Тесты проверки rate limit."""
    
    @pytest.mark.backend

    
    def test_check_rate_limit_allows_requests(self, rate_limiter):
        """Тест что rate limit разрешает запросы в пределах лимита."""
        current_time = time.time()
        client_ip = "127.0.0.1"
        
        # Делаем 5 запросов (меньше лимита 10)
        for i in range(5):
            assert rate_limiter._check_rate_limit(client_ip, current_time + i) == True
    
    @pytest.mark.backend

    
    def test_check_rate_limit_blocks_excess(self, rate_limiter):
        """Тест что rate limit блокирует запросы сверх лимита."""
        current_time = time.time()
        client_ip = "127.0.0.1"
        
        # Делаем 10 запросов (на лимите)
        for i in range(10):
            assert rate_limiter._check_rate_limit(client_ip, current_time + i) == True
        
        # 11-й запрос должен быть заблокирован
        assert rate_limiter._check_rate_limit(client_ip, current_time + 10) == False
    
    @pytest.mark.backend

    
    def test_check_rate_limit_resets_after_minute(self, rate_limiter):
        """Тест что rate limit сбрасывается после минуты."""
        current_time = time.time()
        client_ip = "127.0.0.1"
        
        # Делаем 10 запросов
        for i in range(10):
            rate_limiter._check_rate_limit(client_ip, current_time + i)
        
        # Запрос через минуту должен быть разрешен
        assert rate_limiter._check_rate_limit(client_ip, current_time + 61) == True
    
    @pytest.mark.backend

    
    def test_check_rate_limit_different_ips(self, rate_limiter):
        """Тест что rate limit работает независимо для разных IP."""
        current_time = time.time()
        ip1 = "127.0.0.1"
        ip2 = "192.168.1.1"
        
        # Делаем 10 запросов от первого IP
        for i in range(10):
            rate_limiter._check_rate_limit(ip1, current_time + i)
        
        # Второй IP должен иметь свой лимит
        assert rate_limiter._check_rate_limit(ip2, current_time) == True


class TestCleanupOldRecords:
    """Тесты очистки старых записей."""
    
    @pytest.mark.backend

    
    def test_cleanup_removes_old_ips(self, rate_limiter):
        """Тест что cleanup удаляет старые IP адреса."""
        current_time = time.time()
        
        # Добавляем запросы для IP
        rate_limiter.request_counts["127.0.0.1"] = [current_time - 400]  # 400 секунд назад
        
        # Выполняем cleanup
        rate_limiter._cleanup_old_records(current_time)
        
        # IP должен быть удален
        assert "127.0.0.1" not in rate_limiter.request_counts
    
    @pytest.mark.backend

    
    def test_cleanup_keeps_recent_ips(self, rate_limiter):
        """Тест что cleanup сохраняет недавние IP адреса."""
        current_time = time.time()
        
        # Добавляем недавние запросы
        rate_limiter.request_counts["127.0.0.1"] = [current_time - 60]  # 1 минута назад
        
        # Выполняем cleanup
        rate_limiter._cleanup_old_records(current_time)
        
        # IP должен остаться
        assert "127.0.0.1" in rate_limiter.request_counts


class TestDispatch:
    """Тесты обработки запросов."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_dispatch_allows_request(self, rate_limiter, mock_app):
        """Тест что dispatch разрешает запрос в пределах лимита."""
        mock_request = Mock(spec=Request)
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        
        mock_response = Mock()
        mock_call_next = AsyncMock(return_value=mock_response)
        
        # Мокаем time.time для контроля времени
        with patch('backend.middleware.rate_limiter.time.time', return_value=time.time()):
            response = await rate_limiter.dispatch(mock_request, mock_call_next)
            
            assert response == mock_response
            mock_call_next.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_dispatch_blocks_excess_requests(self, rate_limiter, mock_app):
        """Тест что dispatch блокирует запросы сверх лимита."""
        from fastapi import HTTPException
        
        mock_request = Mock(spec=Request)
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        
        mock_call_next = AsyncMock()
        
        # Исчерпываем лимит
        current_time = time.time()
        for i in range(10):
            rate_limiter._check_rate_limit("127.0.0.1", current_time + i)
        
        # Мокаем time.time
        with patch('backend.middleware.rate_limiter.time.time', return_value=current_time + 10):
            with pytest.raises(HTTPException) as exc_info:
                await rate_limiter.dispatch(mock_request, mock_call_next)
            
            assert exc_info.value.status_code == 429
            mock_call_next.assert_not_called()
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_dispatch_handles_unknown_client(self, rate_limiter, mock_app):
        """Тест обработки запроса с неизвестным клиентом."""
        mock_request = Mock(spec=Request)
        mock_request.client = None
        
        mock_response = Mock()
        mock_call_next = AsyncMock(return_value=mock_response)
        
        with patch('backend.middleware.rate_limiter.time.time', return_value=time.time()):
            response = await rate_limiter.dispatch(mock_request, mock_call_next)
            
            assert response == mock_response
