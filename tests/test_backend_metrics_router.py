"""Тесты для роутера метрик."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

# Мокаем setup_log_filter до импорта
with patch('backend.middleware.log_filter.setup_log_filter'):
    from backend.api import app


@pytest.fixture
def client():
    """Создает тестовый клиент FastAPI."""
    with patch('backend.api.initialize_ollama_pool', new_callable=AsyncMock), \
         patch('backend.api.get_performance_metrics'), \
         patch('backend.api.EventStore'), \
         patch('backend.api.get_shutdown_manager'), \
         patch('backend.api.setup_log_filter'):
        yield TestClient(app)


class TestGetMetrics:
    """Тесты для GET /api/metrics."""
    
    @patch('backend.routers.metrics.get_performance_metrics')
    @pytest.mark.backend

    def test_get_metrics_success(self, mock_metrics, client):
        """Тест получения метрик."""
        # Настраиваем моки
        from infrastructure.performance_metrics import StageMetrics
        
        mock_stage1 = Mock(spec=StageMetrics)
        mock_stage1.count = 10
        mock_stage1.avg = 0.5
        
        mock_stage2 = Mock(spec=StageMetrics)
        mock_stage2.count = 8
        mock_stage2.avg = 2.0
        
        mock_metrics_instance = Mock()
        mock_metrics_instance.stage_metrics = {
            "intent": mock_stage1,
            "planning": mock_stage2
        }
        mock_metrics_instance.benchmark = Mock(
            model_used="test-model",
            tokens_per_second=100.0,
            performance_multiplier=1.5,
            timestamp="2026-01-23T00:00:00Z"
        )
        mock_metrics.return_value = mock_metrics_instance
        
        response = client.get("/api/metrics", headers={"Host": "localhost:8000"})
        
        assert response.status_code == 200
        data = response.json()
        assert "stages" in data
        assert "generation" in data
        assert "models" in data
    
    @patch('backend.routers.metrics.get_performance_metrics')
    @pytest.mark.backend

    def test_get_metrics_no_benchmark(self, mock_metrics, client):
        """Тест получения метрик без бенчмарка."""
        mock_metrics_instance = Mock()
        mock_metrics_instance.stage_metrics = {}
        mock_metrics_instance.benchmark = None
        mock_metrics.return_value = mock_metrics_instance
        
        response = client.get("/api/metrics", headers={"Host": "localhost:8000"})
        
        assert response.status_code == 200
        data = response.json()
        # Должен вернуть метрики даже без бенчмарка
        assert isinstance(data, dict)
        assert "stages" in data
        assert "models" in data
