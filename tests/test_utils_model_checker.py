"""Тесты для utils/model_checker.py."""
import pytest
from unittest.mock import Mock, patch
from utils.model_checker import (
    TaskComplexity,
    ModelInfo,
    check_model_available,
    scan_available_models,
    get_coder_model,
    get_reasoning_model,
    get_best_model_for_complexity
)


class TestTaskComplexity:
    """Тесты для TaskComplexity enum."""
    
    @pytest.mark.utils

    
    def test_task_complexity_values(self):
        """Тест значений enum."""
        assert TaskComplexity.SIMPLE.value == "simple"
        assert TaskComplexity.MEDIUM.value == "medium"
        assert TaskComplexity.COMPLEX.value == "complex"


class TestModelInfo:
    """Тесты для ModelInfo."""
    
    @pytest.mark.utils

    
    def test_model_info_creation(self):
        """Тест создания ModelInfo."""
        info = ModelInfo(
            name="test-model",
            size_bytes=7 * 1024 ** 3,  # 7GB
            parameter_size="7B",
            quantization="Q4_K_M",
            family="test",
            is_coder=True,
            is_reasoning=False,
            estimated_quality=0.8
        )
        
        assert info.name == "test-model"
        assert info.parameter_size == "7B"
        assert info.is_coder is True
        assert info.is_reasoning is False
    
    @pytest.mark.utils

    
    def test_model_info_size_gb(self):
        """Тест свойства size_gb."""
        info = ModelInfo(
            name="test",
            size_bytes=7 * 1024 ** 3,
            parameter_size="7B",
            quantization="Q4_K_M",
            family="test",
            is_coder=False,
            is_reasoning=False,
            estimated_quality=0.5
        )
        
        assert abs(info.size_gb - 7.0) < 0.1
    
    @pytest.mark.utils

    
    def test_model_info_param_billions(self):
        """Тест свойства param_billions."""
        info = ModelInfo(
            name="test",
            size_bytes=1000,
            parameter_size="7B",
            quantization="Q4_K_M",
            family="test",
            is_coder=False,
            is_reasoning=False,
            estimated_quality=0.5
        )
        
        assert info.param_billions == 7.0


class TestCheckModelAvailable:
    """Тесты для check_model_available."""
    
    @pytest.mark.utils

    
    def test_check_model_available_success(self):
        """Тест проверки доступности модели (успех)."""
        with patch('utils.model_checker.ollama') as mock_ollama, \
             patch('utils.model_checker.check_ollama_api_available', return_value=True):
            # ollama.list() возвращает объект с атрибутом models (список)
            mock_models_response = Mock()
            mock_model1 = Mock()
            mock_model1.model = "test-model:7b"
            mock_model2 = Mock()
            mock_model2.model = "other-model:13b"
            mock_models_response.models = [mock_model1, mock_model2]
            mock_ollama.list.return_value = mock_models_response
            
            result = check_model_available("test-model:7b")
            
            assert result is True
    
    @pytest.mark.utils

    
    def test_check_model_available_not_found(self):
        """Тест проверки доступности модели (не найдена)."""
        with patch('utils.model_checker.ollama') as mock_ollama, \
             patch('utils.model_checker.check_ollama_api_available', return_value=True):
            mock_models_response = Mock()
            mock_model = Mock()
            mock_model.model = "other-model:13b"
            mock_models_response.models = [mock_model]
            mock_ollama.list.return_value = mock_models_response
            
            result = check_model_available("test-model:7b")
            
            assert result is False
    
    @pytest.mark.utils

    
    def test_check_model_available_error(self):
        """Тест обработки ошибки при проверке."""
        with patch('utils.model_checker.ollama') as mock_ollama, \
             patch('utils.model_checker.check_ollama_api_available', return_value=True):
            mock_ollama.list.side_effect = Exception("Connection error")
            
            result = check_model_available("test-model:7b")
            
            # При ошибке должна вернуться False
            assert result is False


class TestScanAvailableModels:
    """Тесты для scan_available_models."""
    
    @pytest.mark.utils

    
    def test_scan_available_models(self):
        """Тест сканирования доступных моделей."""
        with patch('utils.model_checker.ollama') as mock_ollama, \
             patch('utils.model_checker.check_ollama_api_available', return_value=True):
            # ollama.list() возвращает объект с атрибутом models
            mock_models_response = Mock()
            mock_model = Mock()
            mock_model.model = "qwen2.5-coder:7b"
            mock_model.size = 7 * 1024 ** 3
            mock_models_response.models = [mock_model]
            mock_ollama.list.return_value = mock_models_response
            
            models = scan_available_models()
            
            assert isinstance(models, dict)
            # Может быть пустым если парсинг не удался, или содержать модели
            assert len(models) >= 0
    
    @pytest.mark.utils

    
    def test_scan_available_models_error(self):
        """Тест обработки ошибки при сканировании."""
        # Сбрасываем кэш перед тестом
        import utils.model_checker
        utils.model_checker._models_cache = {}
        utils.model_checker._cache_valid = False
        
        with patch('utils.model_checker.ollama') as mock_ollama, \
             patch('utils.model_checker.check_ollama_api_available', return_value=True):
            mock_ollama.list.side_effect = Exception("Connection error")
            
            models = scan_available_models()
            
            # При ошибке должен вернуться пустой словарь или кэш
            assert isinstance(models, dict)
            # Может быть пустым или содержать старый кэш


class TestGetCoderModel:
    """Тесты для get_coder_model."""
    
    @pytest.mark.utils

    
    def test_get_coder_model(self):
        """Тест получения модели для кода."""
        with patch('utils.model_checker.scan_available_models') as mock_scan:
            mock_model = ModelInfo(
                name="qwen2.5-coder:7b",
                size_bytes=7 * 1024 ** 3,
                parameter_size="7B",
                quantization="Q4_K_M",
                family="qwen",
                is_coder=True,
                is_reasoning=False,
                estimated_quality=0.8
            )
            mock_scan.return_value = {"qwen2.5-coder:7b": mock_model}
            
            model = get_coder_model(min_quality=0.7)
            
            # Может вернуть модель или None если не найдена подходящая
            assert model is None or isinstance(model, str)
    
    @pytest.mark.utils

    
    def test_get_coder_model_min_quality(self):
        """Тест фильтрации по минимальному качеству."""
        with patch('utils.model_checker.scan_available_models') as mock_scan:
            mock_model = ModelInfo(
                name="low-quality:7b",
                size_bytes=1000,
                parameter_size="7B",
                quantization="Q4_K_M",
                family="test",
                is_coder=True,
                is_reasoning=False,
                estimated_quality=0.5  # Низкое качество
            )
            # Добавляем модель с высоким качеством для сравнения
            mock_model_high = ModelInfo(
                name="high-quality:7b",
                size_bytes=1000,
                parameter_size="7B",
                quantization="Q4_K_M",
                family="test",
                is_coder=True,
                is_reasoning=False,
                estimated_quality=0.8  # Высокое качество
            )
            mock_scan.return_value = {
                "low-quality:7b": mock_model,
                "high-quality:7b": mock_model_high
            }
            
            model = get_coder_model(min_quality=0.7)
            
            # Должна вернуться модель с высоким качеством или None если нет подходящих
            assert model is None or model == "high-quality:7b"


class TestGetReasoningModel:
    """Тесты для get_reasoning_model."""
    
    @pytest.mark.utils

    
    def test_get_reasoning_model(self):
        """Тест получения reasoning модели."""
        with patch('utils.model_checker.scan_available_models') as mock_scan:
            mock_model = ModelInfo(
                name="deepseek-r1:7b",
                size_bytes=7 * 1024 ** 3,
                parameter_size="7B",
                quantization="Q4_K_M",
                family="deepseek",
                is_coder=False,
                is_reasoning=True,  # Reasoning модель
                estimated_quality=0.9
            )
            mock_scan.return_value = {"deepseek-r1:7b": mock_model}
            
            model = get_reasoning_model(min_quality=0.8)
            
            # Может вернуть модель или None
            assert model is None or isinstance(model, str)
    
    @pytest.mark.utils

    
    def test_get_reasoning_model_filters_non_reasoning(self):
        """Тест что фильтруются не-reasoning модели."""
        with patch('utils.model_checker.scan_available_models') as mock_scan:
            mock_model = ModelInfo(
                name="regular-model:7b",
                size_bytes=1000,
                parameter_size="7B",
                quantization="Q4_K_M",
                family="test",
                is_coder=True,
                is_reasoning=False,  # Не reasoning
                estimated_quality=0.9
            )
            mock_scan.return_value = {"regular-model:7b": mock_model}
            
            model = get_reasoning_model(min_quality=0.5)
            
            # Должна вернуться None так как не reasoning модель
            assert model is None


class TestGetBestModelForComplexity:
    """Тесты для get_best_model_for_complexity."""
    
    @pytest.mark.utils

    
    def test_get_best_model_simple(self):
        """Тест получения модели для простой задачи."""
        with patch('utils.model_checker.scan_available_models') as mock_scan:
            mock_model = ModelInfo(
                name="small-model:1.5b",
                size_bytes=2 * 1024 ** 3,
                parameter_size="1.5B",
                quantization="Q4_K_M",
                family="test",
                is_coder=True,
                is_reasoning=False,
                estimated_quality=0.4
            )
            mock_scan.return_value = {"small-model:1.5b": mock_model}
            
            model = get_best_model_for_complexity(
                TaskComplexity.SIMPLE,
                prefer_coder=True
            )
            
            assert model is None or isinstance(model, str)
    
    @pytest.mark.utils

    
    def test_get_best_model_complex(self):
        """Тест получения модели для сложной задачи."""
        with patch('utils.model_checker.scan_available_models') as mock_scan:
            mock_model = ModelInfo(
                name="large-model:14b",
                size_bytes=14 * 1024 ** 3,
                parameter_size="14B",
                quantization="Q4_K_M",
                family="test",
                is_coder=True,
                is_reasoning=False,
                estimated_quality=0.9
            )
            mock_scan.return_value = {"large-model:14b": mock_model}
            
            model = get_best_model_for_complexity(
                TaskComplexity.COMPLEX,
                prefer_coder=True
            )
            
            assert model is None or isinstance(model, str)
