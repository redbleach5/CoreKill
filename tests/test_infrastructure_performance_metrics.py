"""Тесты для infrastructure/performance_metrics.py."""
import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from infrastructure.performance_metrics import (
    PerformanceMetrics,
    StageMetrics,
    SystemBenchmark
)


class TestStageMetrics:
    """Тесты для StageMetrics."""
    
    @pytest.mark.infrastructure

    
    def test_stage_metrics_creation(self):
        """Тест создания StageMetrics."""
        metrics = StageMetrics(stage_name="intent")
        
        assert metrics.stage_name == "intent"
        assert len(metrics.samples) == 0
    
    @pytest.mark.infrastructure

    
    def test_add_sample(self):
        """Тест добавления замеров."""
        metrics = StageMetrics(stage_name="intent")
        
        metrics.add_sample(1.5)
        metrics.add_sample(2.0)
        metrics.add_sample(1.8)
        
        assert len(metrics.samples) == 3
        assert metrics.samples == [1.5, 2.0, 1.8]
    
    @pytest.mark.infrastructure

    
    def test_add_sample_max_limit(self):
        """Тест ограничения максимального количества сэмплов."""
        metrics = StageMetrics(stage_name="intent")
        
        # Добавляем больше MAX_SAMPLES
        for i in range(StageMetrics.MAX_SAMPLES + 10):
            metrics.add_sample(float(i))
        
        # Должно остаться только MAX_SAMPLES последних
        assert len(metrics.samples) == StageMetrics.MAX_SAMPLES
    
    @pytest.mark.infrastructure

    
    def test_avg_property(self):
        """Тест вычисления среднего."""
        metrics = StageMetrics(stage_name="intent")
        
        metrics.add_sample(1.0)
        metrics.add_sample(2.0)
        metrics.add_sample(3.0)
        
        assert metrics.avg == 2.0
    
    @pytest.mark.infrastructure

    
    def test_avg_empty(self):
        """Тест среднего для пустого списка."""
        metrics = StageMetrics(stage_name="intent")
        
        assert metrics.avg == 0.0
    
    @pytest.mark.infrastructure

    
    def test_to_dict(self):
        """Тест сериализации в словарь."""
        metrics = StageMetrics(stage_name="intent")
        metrics.add_sample(1.0)
        metrics.add_sample(2.0)
        
        data = metrics.to_dict()
        
        assert data["stage_name"] == "intent"
        assert data["count"] == 2
        assert "avg" in data
        assert "median" in data
        assert "samples" in data
    
    @pytest.mark.infrastructure

    
    def test_from_dict(self):
        """Тест восстановления из словаря."""
        data = {
            "stage_name": "intent",
            "samples": [1.0, 2.0, 3.0]
        }
        
        metrics = StageMetrics.from_dict(data)
        
        assert metrics.stage_name == "intent"
        assert metrics.samples == [1.0, 2.0, 3.0]


class TestSystemBenchmark:
    """Тесты для SystemBenchmark."""
    
    @pytest.mark.infrastructure

    
    def test_benchmark_creation(self):
        """Тест создания SystemBenchmark."""
        benchmark = SystemBenchmark(
            tokens_per_second=20.0,
            time_to_first_token=0.5,
            model_used="test-model",
            timestamp="2026-01-01T00:00:00",
            performance_multiplier=1.0
        )
        
        assert benchmark.tokens_per_second == 20.0
        assert benchmark.model_used == "test-model"
    
    @pytest.mark.infrastructure

    
    def test_benchmark_to_dict(self):
        """Тест сериализации в словарь."""
        benchmark = SystemBenchmark(
            tokens_per_second=20.0,
            time_to_first_token=0.5,
            model_used="test-model"
        )
        
        data = benchmark.to_dict()
        
        assert data["tokens_per_second"] == 20.0
        assert data["model_used"] == "test-model"
    
    @pytest.mark.infrastructure

    
    def test_benchmark_from_dict(self):
        """Тест восстановления из словаря."""
        data = {
            "tokens_per_second": 20.0,
            "time_to_first_token": 0.5,
            "model_used": "test-model",
            "timestamp": "2026-01-01T00:00:00",
            "performance_multiplier": 1.0
        }
        
        benchmark = SystemBenchmark.from_dict(data)
        
        assert benchmark.tokens_per_second == 20.0
        assert benchmark.model_used == "test-model"


class TestPerformanceMetricsInit:
    """Тесты инициализации PerformanceMetrics."""
    
    @pytest.mark.infrastructure

    
    def test_init_creates_directory(self):
        """Тест создания директории при инициализации."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('infrastructure.performance_metrics.get_config') as mock_config:
                mock_config_instance = Mock()
                mock_config_instance.output_dir = tmpdir
                mock_config.return_value = mock_config_instance
                
                metrics = PerformanceMetrics()
                
                assert Path(tmpdir) / "metrics" in [metrics.persist_path]
    
    @pytest.mark.infrastructure

    
    def test_init_custom_path(self):
        """Тест инициализации с кастомным путём."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('infrastructure.performance_metrics.get_config'):
                metrics = PerformanceMetrics(persist_path=tmpdir)
                
                assert metrics.persist_path == Path(tmpdir)


class TestPerformanceMetricsRecord:
    """Тесты для записи метрик."""
    
    @pytest.mark.infrastructure

    
    def test_record_stage_duration(self):
        """Тест записи длительности этапа."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('infrastructure.performance_metrics.get_config'):
                metrics = PerformanceMetrics(persist_path=tmpdir)
                
                metrics.record_stage_duration("intent", 1.5)
                metrics.record_stage_duration("intent", 2.0)
                
                assert "intent" in metrics.stage_metrics
                assert metrics.stage_metrics["intent"].count == 2
    
    @pytest.mark.infrastructure

    
    def test_record_multiple_stages(self):
        """Тест записи метрик для разных этапов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('infrastructure.performance_metrics.get_config'):
                metrics = PerformanceMetrics(persist_path=tmpdir)
                
                metrics.record_stage_duration("intent", 1.0)
                metrics.record_stage_duration("planning", 2.0)
                metrics.record_stage_duration("coding", 3.0)
                
                assert len(metrics.stage_metrics) == 3
                assert "intent" in metrics.stage_metrics
                assert "planning" in metrics.stage_metrics
                assert "coding" in metrics.stage_metrics


class TestPerformanceMetricsEstimate:
    """Тесты для оценки времени."""
    
    @pytest.mark.infrastructure

    
    def test_get_estimated_duration_with_samples(self):
        """Тест оценки времени на основе сэмплов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('infrastructure.performance_metrics.get_config'):
                metrics = PerformanceMetrics(persist_path=tmpdir)
                
                # Добавляем сэмплы (нужно >= 5 для использования медианы)
                for i in range(6):
                    metrics.record_stage_duration("intent", float(i + 1))
                
                estimate = metrics.get_estimated_duration("intent")
                
                # Должно использовать медиану (близко к 3.5)
                assert 2.0 <= estimate <= 5.0
    
    @pytest.mark.infrastructure

    
    def test_get_estimated_duration_no_samples(self):
        """Тест оценки времени без сэмплов (базовые значения)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('infrastructure.performance_metrics.get_config'):
                metrics = PerformanceMetrics(persist_path=tmpdir)
                
                estimate = metrics.get_estimated_duration("intent")
                
                # Должно использовать базовое значение
                assert estimate == PerformanceMetrics.BASE_STAGE_DURATIONS["intent"]
    
    @pytest.mark.infrastructure

    
    def test_get_estimated_duration_with_benchmark(self):
        """Тест оценки времени с учётом бенчмарка."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('infrastructure.performance_metrics.get_config'):
                metrics = PerformanceMetrics(persist_path=tmpdir)
                
                # Устанавливаем бенчмарк (быстрее базового)
                metrics.benchmark = SystemBenchmark(
                    tokens_per_second=40.0,  # В 2 раза быстрее базового (20.0)
                    performance_multiplier=2.0
                )
                
                estimate = metrics.get_estimated_duration("intent")
                
                # Должно быть скорректировано с учётом производительности
                base_duration = PerformanceMetrics.BASE_STAGE_DURATIONS["intent"]
                assert estimate < base_duration  # Быстрее из-за лучшей производительности


class TestPerformanceMetricsBenchmark:
    """Тесты для бенчмарка."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_run_benchmark(self):
        """Тест запуска бенчмарка."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('infrastructure.performance_metrics.get_config') as mock_config, \
                 patch('infrastructure.local_llm.LocalLLM') as mock_llm_class:
                
                mock_config_instance = Mock()
                mock_config_instance.output_dir = tmpdir
                mock_config_instance.default_model = "test-model"
                mock_config.return_value = mock_config_instance
                
                mock_llm = Mock()
                mock_llm.generate.return_value = "1\n2\n3\n" * 10  # ~100 символов
                mock_llm_class.return_value = mock_llm
                
                metrics = PerformanceMetrics(persist_path=tmpdir)
                
                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = "1\n2\n3\n" * 10
                    
                    benchmark = await metrics.run_benchmark()
                    
                    assert benchmark is not None
                    assert benchmark.model_used == "test-model"
                    assert benchmark.tokens_per_second > 0
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_run_benchmark_custom_model(self):
        """Тест запуска бенчмарка с кастомной моделью."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('infrastructure.performance_metrics.get_config'), \
                 patch('infrastructure.local_llm.LocalLLM') as mock_llm_class:
                
                mock_llm = Mock()
                mock_llm.generate.return_value = "test response"
                mock_llm_class.return_value = mock_llm
                
                metrics = PerformanceMetrics(persist_path=tmpdir)
                
                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = "test response"
                    
                    benchmark = await metrics.run_benchmark(model="custom-model")
                    
                    assert benchmark.model_used == "custom-model"


class TestPerformanceMetricsPersistence:
    """Тесты для сохранения/загрузки метрик."""
    
    @pytest.mark.infrastructure

    
    def test_save_and_load(self):
        """Тест сохранения и загрузки метрик."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('infrastructure.performance_metrics.get_config'):
                # Создаём и сохраняем
                metrics1 = PerformanceMetrics(persist_path=tmpdir)
                metrics1.record_stage_duration("intent", 1.5)
                metrics1._save()
                
                # Загружаем в новом экземпляре
                metrics2 = PerformanceMetrics(persist_path=tmpdir)
                
                assert "intent" in metrics2.stage_metrics
                assert metrics2.stage_metrics["intent"].count == 1
