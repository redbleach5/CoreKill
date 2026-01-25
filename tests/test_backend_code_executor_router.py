"""Тесты для роутера выполнения кода."""
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


class TestExecuteCode:
    """Тесты для POST /api/code/execute."""
    
    @patch('backend.routers.code_executor.asyncio.create_subprocess_exec')
    @patch('backend.routers.code_executor.tempfile.NamedTemporaryFile')
    @patch('backend.routers.code_executor.os.unlink')
    @pytest.mark.backend

    def test_execute_code_success(self, mock_unlink, mock_tempfile, mock_subprocess, client):
        """Тест успешного выполнения кода."""
        # Настраиваем моки для context manager
        mock_file = Mock()
        mock_file.name = "/tmp/test_file.py"
        mock_file.write = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)
        mock_tempfile.return_value = mock_file
        
        # Мокаем async subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(
            b"Hello, World!",
            b""
        ))
        mock_subprocess.return_value = mock_process
        
        response = client.post(
            "/api/code/execute",
            json={
                "code": "print('Hello, World!')",
                "language": "python",
                "timeout": 10
            },
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "output" in data
        assert data["success"] == True
        assert "Hello, World!" in data["output"]
    
    @patch('backend.routers.code_executor.asyncio.create_subprocess_exec')
    @patch('backend.routers.code_executor.tempfile.NamedTemporaryFile')
    @patch('backend.routers.code_executor.os.unlink')
    @pytest.mark.backend

    def test_execute_code_with_error(self, mock_unlink, mock_tempfile, mock_subprocess, client):
        """Тест выполнения кода с ошибкой (runtime error, не security error)."""
        # Настраиваем моки для context manager
        mock_file = Mock()
        mock_file.name = "/tmp/test_file.py"
        mock_file.write = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)
        mock_tempfile.return_value = mock_file
        
        # Мокаем async subprocess с ошибкой
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(
            b"",
            b"SyntaxError: invalid syntax"
        ))
        mock_subprocess.return_value = mock_process
        
        response = client.post(
            "/api/code/execute",
            json={
                "code": "def invalid syntax",
                "language": "python",
                "timeout": 10
            },
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert data["success"] == False
        assert "error" in data
    
    @pytest.mark.backend

    
    def test_execute_code_validation_error(self, client):
        """Тест валидации запроса."""
        # Отправляем невалидный запрос (без обязательного поля code)
        response = client.post(
            "/api/code/execute",
            json={
                "language": "python"
            },
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.backend

    
    def test_execute_code_timeout_validation(self, client):
        """Тест валидации таймаута."""
        # Отправляем запрос с невалидным таймаутом
        response = client.post(
            "/api/code/execute",
            json={
                "code": "print('test')",
                "timeout": 100  # Превышает максимум (60)
            },
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 422  # Validation error
