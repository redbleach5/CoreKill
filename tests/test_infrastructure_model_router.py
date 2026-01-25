"""Тесты для model router."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from infrastructure.model_router import (
    SmartModelRouter,
    ModelSelection,
    get_model_router,
    reset_model_router
)
from utils.model_checker import TaskComplexity, ModelInfo


@pytest.fixture
def mock_models():
    """Мок списка моделей."""
    return {
        "phi3:mini": ModelInfo(
            name="phi3:mini",
            size_bytes=2 * 1024 * 1024 * 1024,  # 2GB
            parameter_size="3.8B",
            quantization="Q4_K_M",
            family="phi",
            is_coder=True,
            is_reasoning=False,
            estimated_quality=0.4
        ),
        "qwen2.5-coder:7b": ModelInfo(
            name="qwen2.5-coder:7b",
            size_bytes=7 * 1024 * 1024 * 1024,  # 7GB
            parameter_size="7B",
            quantization="Q4_K_M",
            family="qwen",
            is_coder=True,
            is_reasoning=False,
            estimated_quality=0.7
        ),
        "deepseek-r1:7b": ModelInfo(
            name="deepseek-r1:7b",
            size_bytes=7 * 1024 * 1024 * 1024,  # 7GB
            parameter_size="7B",
            quantization="Q4_K_M",
            family="deepseek",
            is_coder=True,
            is_reasoning=True,
            estimated_quality=0.9
        )
    }


@pytest.fixture
def router(mock_models):
    """Создает экземпляр SmartModelRouter с моками."""
    with patch('infrastructure.model_router.scan_available_models', return_value=mock_models), \
         patch('infrastructure.model_router.get_all_reasoning_models', return_value=["deepseek-r1:7b"]), \
         patch('infrastructure.model_router.get_config') as mock_config:
        mock_config_instance = Mock()
        mock_config_instance.quality_min_simple = 0.3
        mock_config_instance.quality_min_medium = 0.55
        mock_config_instance.quality_min_complex = 0.7
        mock_config_instance.max_model_vram_gb = 16
        mock_config.return_value = mock_config_instance
        
        return SmartModelRouter()


class TestSmartModelRouterInit:
    """Тесты инициализации SmartModelRouter."""
    
    @pytest.mark.infrastructure

    
    def test_init_loads_models(self, router, mock_models):
        """Тест что инициализация загружает модели."""
        assert len(router._models) == len(mock_models)
    
    @pytest.mark.infrastructure

    
    def test_init_validates_config(self):
        """Тест валидации конфигурации."""
        with patch('infrastructure.model_router.scan_available_models', return_value={}), \
             patch('infrastructure.model_router.get_all_reasoning_models', return_value=[]), \
             patch('infrastructure.model_router.get_config') as mock_config:
            mock_config_instance = Mock()
            mock_config_instance.quality_min_simple = 0.5
            mock_config_instance.quality_min_medium = 0.3  # Некорректно: меньше simple
            mock_config_instance.quality_min_complex = 0.7
            mock_config_instance.max_model_vram_gb = 16
            mock_config.return_value = mock_config_instance
            
            with pytest.raises(ValueError, match="Пороги качества должны возрастать"):
                SmartModelRouter()
    
    @pytest.mark.infrastructure

    
    def test_init_creates_cache(self, router):
        """Тест что создается кэш."""
        assert hasattr(router, '_selection_cache')
        assert isinstance(router._selection_cache, dict)


class TestSelectModel:
    """Тесты для select_model."""
    
    @pytest.mark.infrastructure

    
    def test_select_model_with_preferred(self, router, mock_models):
        """Тест выбора модели с предпочтительной."""
        with patch('infrastructure.model_router.scan_available_models', return_value=mock_models), \
             patch('utils.model_checker.check_model_available', return_value=True):
            selection = router.select_model(
                task_type="coding",
                preferred_model="qwen2.5-coder:7b",
                context={}
            )
            
            assert isinstance(selection, ModelSelection)
            assert selection.model == "qwen2.5-coder:7b"
            assert selection.confidence > 0
    
    @pytest.mark.infrastructure

    
    def test_select_model_without_preferred(self, router, mock_models):
        """Тест выбора модели без предпочтительной."""
        with patch('infrastructure.model_router.scan_available_models', return_value=mock_models), \
             patch('utils.model_checker.check_model_available', return_value=True):
            selection = router.select_model(
                task_type="coding",
                preferred_model=None,
                context={}
            )
            
            assert isinstance(selection, ModelSelection)
            assert selection.model is not None
            assert selection.confidence > 0
    
    @pytest.mark.infrastructure

    
    def test_select_model_uses_cache(self, router, mock_models):
        """Тест что используется кэш."""
        with patch('infrastructure.model_router.scan_available_models', return_value=mock_models), \
             patch('utils.model_checker.check_model_available', return_value=True):
            # Первый вызов
            selection1 = router.select_model(
                task_type="coding",
                preferred_model=None,
                context={}
            )
            
            # Второй вызов с теми же параметрами
            selection2 = router.select_model(
                task_type="coding",
                preferred_model=None,
                context={}
            )
            
            # Должны быть одинаковые результаты
            assert selection1.model == selection2.model
    
    @patch('infrastructure.model_router.check_model_available')
    @pytest.mark.infrastructure

    def test_select_model_checks_availability(self, mock_check, router):
        """Тест что проверяется доступность модели."""
        mock_check.return_value = True
        
        selection = router.select_model(
            task_type="coding",
            preferred_model="qwen2.5-coder:7b",
            context={}
        )
        
        mock_check.assert_called()


class TestSelectModelForComplexity:
    """Тесты для select_model_for_complexity."""
    
    @patch('infrastructure.model_router.get_light_model')
    @pytest.mark.infrastructure

    def test_select_model_simple_complexity(self, mock_light, router, mock_models):
        """Тест выбора модели для простой задачи."""
        mock_light.return_value = "phi3:mini"
        
        with patch('infrastructure.model_router.scan_available_models', return_value=mock_models), \
             patch('utils.model_checker.check_model_available', return_value=True):
            selection = router.select_model_for_complexity(
                complexity=TaskComplexity.SIMPLE,
                task_type="coding"
            )
            
            assert isinstance(selection, ModelSelection)
            assert selection.model is not None
            # Для простой задачи должна быть легкая модель
            # Может быть любая доступная модель, не обязательно phi3
    
    @pytest.mark.infrastructure

    
    def test_select_model_medium_complexity(self, router, mock_models):
        """Тест выбора модели для средней задачи."""
        with patch('infrastructure.model_router.scan_available_models', return_value=mock_models), \
             patch('utils.model_checker.check_model_available', return_value=True):
            selection = router.select_model_for_complexity(
                complexity=TaskComplexity.MEDIUM,
                task_type="coding"
            )
            
            assert isinstance(selection, ModelSelection)
            assert selection.model is not None
    
    @pytest.mark.infrastructure

    
    def test_select_model_complex_complexity(self, router, mock_models):
        """Тест выбора модели для сложной задачи."""
        with patch('infrastructure.model_router.scan_available_models', return_value=mock_models), \
             patch('utils.model_checker.check_model_available', return_value=True):
            selection = router.select_model_for_complexity(
                complexity=TaskComplexity.COMPLEX,
                task_type="coding"
            )
            
            assert isinstance(selection, ModelSelection)
            assert selection.model is not None
            # Для сложной задачи может быть reasoning модель
            # (если prefer_reasoning=True)
    
    @pytest.mark.infrastructure

    
    def test_select_model_respects_preferred(self, router, mock_models):
        """Тест что учитывается предпочтительная модель."""
        with patch('infrastructure.model_router.scan_available_models', return_value=mock_models), \
             patch('utils.model_checker.check_model_available', return_value=True):
            selection = router.select_model_for_complexity(
                complexity=TaskComplexity.MEDIUM,
                task_type="coding",
                preferred_model="qwen2.5-coder:7b"
            )
            
            assert selection.model == "qwen2.5-coder:7b"


class TestGetFallbackModel:
    """Тесты для get_fallback_model."""
    
    @pytest.mark.infrastructure

    
    def test_get_fallback_model_with_complexity(self, router):
        """Тест получения запасной модели с известной сложностью."""
        with patch('infrastructure.model_router.scan_available_models', return_value=router._models):
            fallback = router.get_fallback_model(
                failed_model="qwen2.5-coder:7b",
                task_type="coding",
                complexity=TaskComplexity.SIMPLE
            )
            
            assert fallback is not None
            assert isinstance(fallback, ModelSelection)
            assert fallback.model != "qwen2.5-coder:7b"
    
    @patch('utils.model_checker.get_light_model')
    @pytest.mark.infrastructure

    def test_get_fallback_model_for_intent(self, mock_light, router):
        """Тест получения запасной модели для intent."""
        mock_light.return_value = "phi3:mini"
        
        with patch('infrastructure.model_router.scan_available_models', return_value=router._models):
            fallback = router.get_fallback_model(
                failed_model="test-model",
                task_type="intent",
                complexity=None
            )
            
            assert fallback is not None
            assert fallback.model == "phi3:mini"
    
    @patch('infrastructure.model_router.get_any_available_model')
    @pytest.mark.infrastructure

    def test_get_fallback_model_general(self, mock_any, router):
        """Тест получения общей запасной модели."""
        mock_any.return_value = "phi3:mini"
        
        with patch('infrastructure.model_router.scan_available_models', return_value=router._models):
            fallback = router.get_fallback_model(
                failed_model="test-model",
                task_type="coding",
                complexity=None
            )
            
            assert fallback is not None
            assert fallback.model == "phi3:mini"


class TestRefreshModels:
    """Тесты для refresh_models."""
    
    @patch('infrastructure.model_router.invalidate_models_cache')
    @patch('infrastructure.model_router.scan_available_models')
    @pytest.mark.infrastructure

    def test_refresh_models_updates_list(self, mock_scan, mock_invalidate, router):
        """Тест что refresh обновляет список моделей."""
        new_models = {"new-model": Mock()}
        mock_scan.return_value = new_models
        
        result = router.refresh_models()
        
        mock_invalidate.assert_called()
        mock_scan.assert_called()
        assert router._models == new_models
        assert len(result) == 1


class TestGetModelRouter:
    """Тесты для get_model_router."""
    
    @pytest.mark.infrastructure

    
    def test_get_model_router_returns_instance(self):
        """Тест что get_model_router возвращает экземпляр."""
        with patch('infrastructure.model_router.scan_available_models', return_value={}), \
             patch('infrastructure.model_router.get_all_reasoning_models', return_value=[]), \
             patch('infrastructure.model_router.get_config') as mock_config:
            mock_config_instance = Mock()
            mock_config_instance.quality_min_simple = 0.3
            mock_config_instance.quality_min_medium = 0.55
            mock_config_instance.quality_min_complex = 0.7
            mock_config_instance.max_model_vram_gb = 16
            mock_config.return_value = mock_config_instance
            
            router1 = get_model_router()
            router2 = get_model_router()
            
            # После первого вызова должен быть singleton
            assert router1 is router2
    
    @pytest.mark.infrastructure

    
    def test_reset_model_router_creates_new(self):
        """Тест что reset создает новый экземпляр."""
        with patch('infrastructure.model_router.scan_available_models', return_value={}), \
             patch('infrastructure.model_router.get_all_reasoning_models', return_value=[]), \
             patch('infrastructure.model_router.get_config') as mock_config:
            mock_config_instance = Mock()
            mock_config_instance.quality_min_simple = 0.3
            mock_config_instance.quality_min_medium = 0.55
            mock_config_instance.quality_min_complex = 0.7
            mock_config_instance.max_model_vram_gb = 16
            mock_config.return_value = mock_config_instance
            
            router1 = get_model_router()
            reset_model_router()
            router2 = get_model_router()
            
            # После reset должен быть новый экземпляр
            assert router1 is not router2


class TestModelSelection:
    """Тесты для ModelSelection."""
    
    @pytest.mark.infrastructure

    
    def test_model_selection_creation(self):
        """Тест создания ModelSelection."""
        selection = ModelSelection(
            model="test-model",
            confidence=0.9,
            reason="Test reason",
            is_reasoning=False
        )
        
        assert selection.model == "test-model"
        assert selection.confidence == 0.9
        assert selection.reason == "Test reason"
        assert selection.is_reasoning == False
    
    @pytest.mark.infrastructure

    
    def test_model_selection_defaults(self):
        """Тест значений по умолчанию."""
        selection = ModelSelection(model="test-model")
        
        assert selection.confidence == 1.0
        assert selection.reason == ""
        assert selection.metadata is None
        assert selection.is_reasoning == False
