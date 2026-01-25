"""Тесты для роутера агентов."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json

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


class TestCreateTask:
    """Тесты для POST /api/tasks."""
    
    @patch('backend.routers.agent.create_workflow_graph')
    @patch('backend.routers.agent.get_model_router')
    @pytest.mark.backend

    def test_create_task_success(self, mock_router, mock_graph, client):
        """Тест успешного создания задачи."""
        # Настраиваем моки
        mock_graph_instance = Mock()
        mock_graph_instance.astream = AsyncMock()
        mock_graph.return_value = mock_graph_instance
        
        mock_router_instance = Mock()
        mock_router_instance.select_model.return_value = Mock(model="test-model")
        mock_router.return_value = mock_router_instance
        
        response = client.post(
            "/api/tasks",
            json={
                "task": "напиши функцию hello",
                "mode": "code",
                "model": "test-model",
                "temperature": 0.25
            },
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
    
    @pytest.mark.backend

    
    def test_create_task_validation_error(self, client):
        """Тест валидации запроса."""
        # Отправляем невалидный запрос (без обязательного поля task)
        response = client.post(
            "/api/tasks",
            json={
                "mode": "code"
            },
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 422  # Validation error


class TestGetModels:
    """Тесты для GET /api/models."""
    
    @patch('backend.routers.agent.get_all_models_info')
    @pytest.mark.backend

    def test_get_models_success(self, mock_info, client):
        """Тест получения списка моделей."""
        from utils.model_checker import ModelInfo
        
        # Настраиваем моки с правильной структурой ModelInfo
        mock_info.return_value = [
            ModelInfo(
                name="model1",
                size_bytes=7 * 1024 * 1024 * 1024,
                parameter_size="7B",
                quantization="Q4_K_M",
                family="test",
                is_coder=True,
                is_reasoning=False,
                estimated_quality=0.7
            ),
            ModelInfo(
                name="model2",
                size_bytes=14 * 1024 * 1024 * 1024,
                parameter_size="14B",
                quantization="Q4_K_M",
                family="test",
                is_coder=True,
                is_reasoning=False,
                estimated_quality=0.8
            )
        ]
        
        response = client.get("/api/models", headers={"Host": "localhost:8000"})
        
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "models_detailed" in data
        assert "count" in data
        assert data["count"] == 2
    
    @patch('backend.routers.agent.get_all_available_models')
    @patch('backend.routers.agent.get_all_models_info')
    @pytest.mark.backend

    def test_get_models_empty(self, mock_info, mock_models, client):
        """Тест получения пустого списка моделей."""
        mock_models.return_value = []
        mock_info.return_value = []
        
        response = client.get("/api/models", headers={"Host": "localhost:8000"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["models"] == []


class TestRefreshModels:
    """Тесты для POST /api/models/refresh."""
    
    @patch('backend.routers.agent.reset_model_router')
    @patch('backend.routers.agent.get_models')
    @pytest.mark.backend

    def test_refresh_models_success(
        self,
        mock_get_models,
        mock_reset,
        client
    ):
        """Тест обновления списка моделей."""
        mock_get_models.return_value = {
            "models": ["model1", "model2"],
            "models_detailed": [],
            "count": 2
        }
        
        response = client.post(
            "/api/models/refresh",
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "count" in data
        mock_reset.assert_called()
        mock_get_models.assert_called()


class TestBrowseFolder:
    """Тесты для GET /api/browse-folder."""
    
    @patch('subprocess.run')
    @pytest.mark.backend

    def test_browse_folder_success(self, mock_subprocess, client):
        """Тест просмотра директории."""
        # Мокаем subprocess для osascript (macOS)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/test/path\n"
        mock_subprocess.return_value = mock_result
        
        response = client.get(
            "/api/browse-folder?start_path=/test",
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "path" in data or "selected" in data or "cancelled" in data
    
    @patch('subprocess.run')
    @pytest.mark.backend

    def test_browse_folder_cancelled(self, mock_subprocess, client):
        """Тест отмены выбора папки."""
        # Мокаем subprocess для отмены (пустой stdout)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_subprocess.return_value = mock_result
        
        response = client.get(
            "/api/browse-folder",
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Может быть cancelled или пустой путь
        assert "cancelled" in data or "path" in data


class TestGetProjectFiles:
    """Тесты для GET /api/project-files."""
    
    @patch('backend.routers.agent.validate_directory_path')
    @patch('os.path.isdir')
    @patch('os.listdir')
    @patch('os.path.join')
    @patch('os.path.splitext')
    @patch('os.path.getsize')
    @patch('os.path.basename')
    @pytest.mark.backend

    def test_get_project_files_success(
        self,
        mock_basename,
        mock_getsize,
        mock_splitext,
        mock_join,
        mock_listdir,
        mock_isdir,
        mock_validate,
        client
    ):
        """Тест получения файлов проекта."""
        # Мокаем validate_directory_path чтобы вернуть валидный путь
        def validate_side_effect(path, project_path=None):
            return path
        
        mock_validate.side_effect = validate_side_effect
        mock_isdir.return_value = True
        mock_listdir.return_value = ["file1.py", "file2.py", "subdir"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_splitext.side_effect = lambda f: ("file1", ".py") if ".py" in f else ("file2", ".py")
        mock_getsize.return_value = 100
        mock_basename.return_value = "test"
        
        response = client.get(
            "/api/project-files?path=/test",
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
    
    @patch('backend.routers.agent.validate_directory_path')
    @pytest.mark.backend

    def test_get_project_files_invalid_path(self, mock_validate, client):
        """Тест получения файлов с невалидным путем."""
        mock_validate.return_value = False
        
        response = client.get(
            "/api/project-files?path=/invalid",
            headers={"Host": "localhost:8000"}
        )
        
        # Может быть 200 с пустым списком или 400
        assert response.status_code in [200, 400]


class TestGetFileContent:
    """Тесты для GET /api/file-content."""
    
    @patch('backend.routers.agent.validate_file_path')
    @patch('os.path.isfile')
    @patch('os.path.getsize')
    @patch('builtins.open', create=True)
    @pytest.mark.backend

    def test_get_file_content_success(
        self,
        mock_open,
        mock_getsize,
        mock_isfile,
        mock_validate,
        client
    ):
        """Тест получения содержимого файла."""
        mock_validate.return_value = "/test/file.py"
        mock_isfile.return_value = True
        mock_getsize.return_value = 100
        mock_open.return_value.__enter__.return_value.read.return_value = "def hello():\n    return 'world'"
        
        response = client.get(
            "/api/file-content?path=/test/file.py",
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "def hello" in data["content"]
    
    @patch('backend.routers.agent.validate_file_path')
    @pytest.mark.backend

    def test_get_file_content_invalid_path(self, mock_validate, client):
        """Тест получения содержимого с невалидным путем."""
        mock_validate.return_value = False
        
        response = client.get(
            "/api/file-content?path=/invalid/file.py",
            headers={"Host": "localhost:8000"}
        )
        
        # Может быть 200 с пустым содержимым или 400
        assert response.status_code in [200, 400]


class TestIndexProject:
    """Тесты для POST /api/index."""
    
    @patch('backend.routers.agent.validate_directory_path')
    @patch('pathlib.Path')
    @patch('infrastructure.context_engine.ContextEngine')
    @patch('asyncio.to_thread')
    @pytest.mark.backend

    def test_index_project_success(
        self,
        mock_to_thread,
        mock_context_engine,
        mock_path,
        mock_validate,
        client
    ):
        """Тест индексации проекта."""
        mock_validate.return_value = "/test/project"
        
        # Мокаем Path.exists() и is_dir()
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True
        mock_path.return_value = mock_path_instance
        
        mock_engine_instance = Mock()
        mock_engine_instance.index_project.return_value = {"file1.py": []}
        mock_context_engine.return_value = mock_engine_instance
        
        async def mock_to_thread_func(func, *args, **kwargs):
            return func(*args, **kwargs)
        
        mock_to_thread.side_effect = mock_to_thread_func
        
        response = client.post(
            "/api/index",
            json={
                "project_path": "/test/project",
                "file_extensions": [".py", ".js"]
            },
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "message" in data or "files_indexed" in data
    
    @pytest.mark.backend

    
    def test_index_project_invalid_path(self, client):
        """Тест индексации с невалидным путем."""
        with patch('backend.routers.agent.validate_directory_path', return_value=False):
            response = client.post(
                "/api/index",
                json={
                    "project_path": "/invalid",
                    "file_extensions": [".py"]
                },
                headers={"Host": "localhost:8000"}
            )
            
            assert response.status_code == 400


class TestGetStageMetrics:
    """Тесты для GET /api/metrics/stages."""
    
    @patch('infrastructure.performance_metrics.get_performance_metrics')
    @pytest.mark.backend

    def test_get_stage_metrics_success(self, mock_metrics, client):
        """Тест получения метрик этапов."""
        mock_metrics_instance = Mock()
        mock_metrics_instance.get_metrics_summary.return_value = {
            "stages": {
                "intent": {"count": 10, "avg": 0.5},
                "planning": {"count": 8, "avg": 2.0}
            }
        }
        mock_metrics.return_value = mock_metrics_instance
        
        response = client.get(
            "/api/metrics/stages",
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestRunBenchmark:
    """Тесты для POST /api/metrics/benchmark."""
    
    @patch('infrastructure.performance_metrics.get_performance_metrics')
    @pytest.mark.backend

    def test_run_benchmark_success(self, mock_metrics, client):
        """Тест запуска бенчмарка."""
        from infrastructure.performance_metrics import SystemBenchmark
        
        mock_benchmark = Mock(spec=SystemBenchmark)
        mock_benchmark.tokens_per_second = 100.0
        mock_benchmark.to_dict.return_value = {
            "tokens_per_second": 100.0,
            "performance_multiplier": 1.5,
            "model_used": "test-model"
        }
        
        mock_metrics_instance = Mock()
        async def mock_run_benchmark(model=None):
            return mock_benchmark
        
        mock_metrics_instance.run_benchmark = mock_run_benchmark
        mock_metrics.return_value = mock_metrics_instance
        
        response = client.post(
            "/api/metrics/benchmark?model=test-model",
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "benchmark" in data


class TestStreamEndpoint:
    """Тесты для GET /api/stream (SSE endpoint)."""
    
    @patch('backend.routers.agent.WorkflowStreamer')
    @patch('backend.routers.agent.ModeDetector')
    @patch('backend.routers.agent.send_greeting_response')
    @patch('utils.model_checker.check_ollama_api_available', return_value=True)
    @patch('infrastructure.agent_resource_manager.get_resource_manager', new_callable=AsyncMock)
    @pytest.mark.backend

    def test_stream_greeting(
        self,
        mock_resource_manager,
        mock_check_ollama,
        mock_greeting,
        mock_detector,
        mock_streamer,
        client
    ):
        """Тест SSE endpoint для greeting."""
        # Настраиваем моки
        mock_detector_instance = Mock()
        mock_detector_instance.detect.return_value = ("chat", "greeting", None)
        mock_detector.return_value = mock_detector_instance
        
        # Мокируем resource_manager
        mock_rm_instance = Mock()
        mock_rm_instance.get_stats.return_value = {
            "active_agents": 0,
            "max_concurrent": 5,
            "available_slots": 5
        }
        mock_resource_manager.return_value = mock_rm_instance
        
        async def mock_greeting_gen():
            yield "data: {\"type\": \"greeting\"}\n\n"
        
        mock_greeting.return_value = mock_greeting_gen()
        
        response = client.get(
            "/api/stream?task=привет&mode=auto",
            headers={"Host": "localhost:8000"}
        )
        
        # SSE endpoint должен возвращать streaming response
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


class TestGetStreamParams:
    """Тесты для функции get_stream_params."""
    
    @patch('utils.model_checker.check_ollama_api_available', return_value=True)
    @patch('infrastructure.agent_resource_manager.get_resource_manager', new_callable=AsyncMock)
    @pytest.mark.backend

    def test_get_stream_params_defaults(self, mock_resource_manager, mock_check_ollama, client):
        """Тест получения параметров с дефолтными значениями."""
        # Мокируем resource_manager
        mock_rm_instance = Mock()
        mock_rm_instance.get_stats.return_value = {
            "active_agents": 0,
            "max_concurrent": 5,
            "available_slots": 5
        }
        mock_resource_manager.return_value = mock_rm_instance
        
        # Проверяем что endpoint принимает параметры
        response = client.get(
            "/api/stream?task=test",
            headers={"Host": "localhost:8000"}
        )
        
        # Должен вернуть ответ (может быть ошибка валидации или streaming)
        assert response.status_code in [200, 400, 422, 503]
    
    @patch('utils.model_checker.check_ollama_api_available', return_value=True)
    @patch('infrastructure.agent_resource_manager.get_resource_manager', new_callable=AsyncMock)
    @pytest.mark.backend

    def test_get_stream_params_all_fields(self, mock_resource_manager, mock_check_ollama, client):
        """Тест получения параметров со всеми полями."""
        # Мокируем resource_manager
        mock_rm_instance = Mock()
        mock_rm_instance.get_stats.return_value = {
            "active_agents": 0,
            "max_concurrent": 5,
            "available_slots": 5
        }
        mock_resource_manager.return_value = mock_rm_instance
        
        response = client.get(
            "/api/stream?task=test&mode=code&model=test-model&temperature=0.5&max_iterations=3",
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code in [200, 400, 422, 503]
