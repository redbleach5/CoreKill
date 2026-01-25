"""Тесты для request tracker middleware."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request
from backend.middleware.request_tracker import RequestTrackerMiddleware


@pytest.fixture
def mock_app():
    """Мок FastAPI приложения."""
    return Mock()


@pytest.fixture
def request_tracker(mock_app):
    """Создает экземпляр RequestTrackerMiddleware."""
    return RequestTrackerMiddleware(mock_app)


class TestDispatch:
    """Тесты обработки запросов."""
    
    @pytest.mark.asyncio
    @patch('backend.middleware.request_tracker.get_shutdown_manager')
    @pytest.mark.backend

    async def test_dispatch_tracks_request(self, mock_get_manager, request_tracker):
        """Тест что dispatch отслеживает запрос."""
        mock_manager = Mock()
        mock_manager.increment_active_requests = AsyncMock()
        mock_manager.decrement_active_requests = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/api/tasks"
        
        mock_response = Mock()
        mock_call_next = AsyncMock(return_value=mock_response)
        
        response = await request_tracker.dispatch(mock_request, mock_call_next)
        
        assert response == mock_response
        mock_manager.increment_active_requests.assert_called_once()
        mock_manager.decrement_active_requests.assert_called_once()
        mock_call_next.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.middleware.request_tracker.get_shutdown_manager')
    @pytest.mark.backend

    async def test_dispatch_skips_health_check(self, mock_get_manager, request_tracker):
        """Тест что health check не отслеживается."""
        mock_manager = Mock()
        mock_manager.increment_active_requests = AsyncMock()
        mock_manager.decrement_active_requests = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/health"
        
        mock_response = Mock()
        mock_call_next = AsyncMock(return_value=mock_response)
        
        response = await request_tracker.dispatch(mock_request, mock_call_next)
        
        assert response == mock_response
        mock_manager.increment_active_requests.assert_not_called()
        mock_manager.decrement_active_requests.assert_not_called()
        mock_call_next.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.middleware.request_tracker.get_shutdown_manager')
    @pytest.mark.backend

    async def test_dispatch_skips_docs(self, mock_get_manager, request_tracker):
        """Тест что docs endpoints не отслеживаются."""
        mock_manager = Mock()
        mock_manager.increment_active_requests = AsyncMock()
        mock_manager.decrement_active_requests = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/docs"
        
        mock_response = Mock()
        mock_call_next = AsyncMock(return_value=mock_response)
        
        response = await request_tracker.dispatch(mock_request, mock_call_next)
        
        assert response == mock_response
        mock_manager.increment_active_requests.assert_not_called()
        mock_manager.decrement_active_requests.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('backend.middleware.request_tracker.get_shutdown_manager')
    @pytest.mark.backend

    async def test_dispatch_decrements_on_error(self, mock_get_manager, request_tracker):
        """Тест что счетчик уменьшается даже при ошибке."""
        mock_manager = Mock()
        mock_manager.increment_active_requests = AsyncMock()
        mock_manager.decrement_active_requests = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/api/tasks"
        
        mock_call_next = AsyncMock(side_effect=Exception("Test error"))
        
        with pytest.raises(Exception):
            await request_tracker.dispatch(mock_request, mock_call_next)
        
        mock_manager.increment_active_requests.assert_called_once()
        mock_manager.decrement_active_requests.assert_called_once()
