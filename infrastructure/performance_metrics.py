"""Система метрик производительности.

Отслеживает реальное время выполнения этапов workflow
и адаптирует оценки под конкретное железо.

Особенности:
- Бенчмарк LLM при старте для калибровки
- Сбор статистики по каждому этапу
- Адаптивные оценки на основе реальных данных
- Учёт модели и сложности задачи
"""
import time
import json
import asyncio
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List
from datetime import datetime, timezone
from statistics import mean, median, stdev

from utils.logger import get_logger
from utils.config import get_config

logger = get_logger()


@dataclass
class StageMetrics:
    """Метрики для одного этапа workflow."""
    stage_name: str
    samples: List[float] = field(default_factory=list)  # Время выполнения в секундах
    
    # Лимит сэмплов для экономии памяти (скользящее окно)
    MAX_SAMPLES = 100
    
    def add_sample(self, duration: float) -> None:
        """Добавляет замер времени."""
        self.samples.append(duration)
        # Храним только последние MAX_SAMPLES
        if len(self.samples) > self.MAX_SAMPLES:
            self.samples = self.samples[-self.MAX_SAMPLES:]
    
    @property
    def count(self) -> int:
        """Количество замеров."""
        return len(self.samples)
    
    @property
    def avg(self) -> float:
        """Среднее время."""
        return mean(self.samples) if self.samples else 0.0
    
    @property
    def median_time(self) -> float:
        """Медианное время."""
        return median(self.samples) if self.samples else 0.0
    
    @property
    def std_dev(self) -> float:
        """Стандартное отклонение."""
        return stdev(self.samples) if len(self.samples) > 1 else 0.0
    
    @property
    def min_time(self) -> float:
        """Минимальное время."""
        return min(self.samples) if self.samples else 0.0
    
    @property
    def max_time(self) -> float:
        """Максимальное время."""
        return max(self.samples) if self.samples else 0.0
    
    def to_dict(self) -> Dict:
        """Сериализует в словарь."""
        return {
            "stage_name": self.stage_name,
            "count": self.count,
            "avg": round(self.avg, 2),
            "median": round(self.median_time, 2),
            "std_dev": round(self.std_dev, 2),
            "min": round(self.min_time, 2),
            "max": round(self.max_time, 2),
            "samples": self.samples[-20:]  # Сохраняем последние 20 для анализа
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StageMetrics':
        """Восстанавливает из словаря."""
        metrics = cls(stage_name=data["stage_name"])
        metrics.samples = data.get("samples", [])
        return metrics


@dataclass
class SystemBenchmark:
    """Результаты бенчмарка системы."""
    # Время генерации 100 токенов (базовый тест)
    tokens_per_second: float = 0.0
    # Время первого токена (latency)
    time_to_first_token: float = 0.0
    # Модель использованная для бенчмарка
    model_used: str = ""
    # Когда проводился бенчмарк
    timestamp: str = ""
    # Коэффициент производительности относительно базового (1.0 = среднее железо)
    performance_multiplier: float = 1.0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SystemBenchmark':
        return cls(**data)


class PerformanceMetrics:
    """Менеджер метрик производительности.
    
    Функции:
    - Бенчмарк LLM при первом запуске
    - Сбор реальной статистики по этапам
    - Адаптивные оценки времени
    - Персистентность данных
    """
    
    # Базовые оценки времени (для среднего железа, tokens/sec ~20)
    BASE_STAGE_DURATIONS = {
        "intent": 3.0,
        "planning": 8.0,
        "research": 12.0,
        "testing": 15.0,
        "coding": 25.0,
        "validation": 5.0,
        "debug": 10.0,
        "fixing": 15.0,
        "reflection": 5.0,
        "critic": 5.0,
        "chat": 5.0,
        "greeting": 1.0,
        "help": 2.0
    }
    
    # Базовая скорость (токенов в секунду) для калибровки
    BASE_TOKENS_PER_SECOND = 20.0
    
    def __init__(self, persist_path: Optional[str] = None):
        """Инициализирует менеджер метрик.
        
        Args:
            persist_path: Путь для сохранения метрик (None = автоопределение)
        """
        config = get_config()
        # ИСПРАВЛЕНИЕ: Проверяем что persist_path и config.output_dir не являются Mock объектами
        from utils.test_mode import is_test_mode
        
        if persist_path and isinstance(persist_path, str):
            self.persist_path = Path(persist_path)
        else:
            output_dir = getattr(config, 'output_dir', None)
            # Проверяем что output_dir не является Mock объектом
            if output_dir and isinstance(output_dir, str):
                self.persist_path = Path(output_dir) / "metrics"
            else:
                # Fallback на текущую директорию если config.output_dir - Mock или в тестах
                if is_test_mode():
                    # В тестах используем временную директорию
                    import tempfile
                    self.persist_path = Path(tempfile.gettempdir()) / "test_metrics"
                else:
                    self.persist_path = Path.cwd() / "output" / "metrics"
        
        # В тестовом режиме не создаём директорию (может быть проблемой с правами)
        if not is_test_mode():
            self.persist_path.mkdir(parents=True, exist_ok=True)
        
        # Метрики по этапам
        self.stage_metrics: Dict[str, StageMetrics] = {}
        
        # Результаты бенчмарка
        self.benchmark: Optional[SystemBenchmark] = None
        
        # Загружаем сохранённые данные
        self._load()
        
        logger.info(f"✅ PerformanceMetrics инициализирован (путь: {self.persist_path})")
    
    def _load(self) -> None:
        """Загружает метрики с диска."""
        # Загружаем бенчмарк
        benchmark_file = self.persist_path / "benchmark.json"
        if benchmark_file.exists():
            try:
                with open(benchmark_file, "r") as f:
                    data = json.load(f)
                    self.benchmark = SystemBenchmark.from_dict(data)
                    logger.info(f"📊 Загружен бенчмарк: {self.benchmark.tokens_per_second:.1f} tok/s")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки бенчмарка: {e}")
        
        # Загружаем метрики этапов
        metrics_file = self.persist_path / "stage_metrics.json"
        if metrics_file.exists():
            try:
                with open(metrics_file, "r") as f:
                    data = json.load(f)
                    for stage_data in data.get("stages", []):
                        metrics = StageMetrics.from_dict(stage_data)
                        self.stage_metrics[metrics.stage_name] = metrics
                    logger.info(f"📊 Загружено {len(self.stage_metrics)} метрик этапов")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки метрик: {e}")
    
    def _save(self) -> None:
        """Сохраняет метрики на диск."""
        # Сохраняем бенчмарк
        if self.benchmark:
            benchmark_file = self.persist_path / "benchmark.json"
            try:
                with open(benchmark_file, "w") as f:
                    json.dump(self.benchmark.to_dict(), f, indent=2)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка сохранения бенчмарка: {e}")
        
        # Сохраняем метрики этапов
        metrics_file = self.persist_path / "stage_metrics.json"
        try:
            data = {
                "stages": [m.to_dict() for m in self.stage_metrics.values()],
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            with open(metrics_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения метрик: {e}")
    
    async def run_benchmark(self, model: Optional[str] = None) -> SystemBenchmark:
        """Запускает бенчмарк LLM для калибровки.
        
        Args:
            model: Модель для тестирования (None = текущая)
            
        Returns:
            Результаты бенчмарка
        """
        from infrastructure.local_llm import LocalLLM
        
        # Используем модель из конфига если не указана
        if not model:
            config = get_config()
            model = config.default_model
        
        logger.info(f"🔧 Запуск бенчмарка LLM (модель: {model})...")
        
        # Простой промпт для теста
        test_prompt = "Напиши числа от 1 до 20, каждое на новой строке."
        
        try:
            llm = LocalLLM(model=model, temperature=0.1)
            
            # Замеряем время
            start_time = time.time()
            response = await asyncio.to_thread(
                llm.generate,
                test_prompt,
                num_predict=100  # Генерируем ~100 токенов
            )
            total_time = time.time() - start_time
            
            # Оцениваем количество токенов (примерно 1 токен = 4 символа)
            estimated_tokens = len(response) / 4
            tokens_per_second = estimated_tokens / total_time if total_time > 0 else 0
            
            # Вычисляем коэффициент производительности
            performance_multiplier = tokens_per_second / self.BASE_TOKENS_PER_SECOND
            
            self.benchmark = SystemBenchmark(
                tokens_per_second=round(tokens_per_second, 2),
                time_to_first_token=round(total_time / 10, 3),  # Приблизительно
                model_used=model,
                timestamp=datetime.now(timezone.utc).isoformat(),
                performance_multiplier=round(performance_multiplier, 2)
            )
            
            self._save()
            
            logger.info(
                f"✅ Бенчмарк завершён: {tokens_per_second:.1f} tok/s, "
                f"множитель: {performance_multiplier:.2f}x"
            )
            
            return self.benchmark
            
        except Exception as e:
            logger.error(f"❌ Ошибка бенчмарка: {e}", error=e)
            # Fallback на стандартные значения
            self.benchmark = SystemBenchmark(
                tokens_per_second=self.BASE_TOKENS_PER_SECOND,
                model_used=model,
                timestamp=datetime.now(timezone.utc).isoformat(),
                performance_multiplier=1.0
            )
            return self.benchmark
    
    def record_stage_duration(self, stage: str, duration: float) -> None:
        """Записывает время выполнения этапа.
        
        Args:
            stage: Название этапа
            duration: Время в секундах
        """
        if stage not in self.stage_metrics:
            self.stage_metrics[stage] = StageMetrics(stage_name=stage)
        
        self.stage_metrics[stage].add_sample(duration)
        
        # Сохраняем каждые 10 замеров
        if self.stage_metrics[stage].count % 10 == 0:
            self._save()
    
    def get_estimated_duration(self, stage: str) -> float:
        """Возвращает оценку времени для этапа.
        
        Использует реальные данные если есть, иначе базовые * коэффициент.
        
        Args:
            stage: Название этапа
            
        Returns:
            Оценка времени в секундах
        """
        # Если есть достаточно реальных данных (>5 замеров) — используем медиану
        if stage in self.stage_metrics and self.stage_metrics[stage].count >= 5:
            return self.stage_metrics[stage].median_time
        
        # Иначе используем базовое значение с коэффициентом
        base_duration = self.BASE_STAGE_DURATIONS.get(stage, 5.0)
        
        # Применяем коэффициент производительности (быстрее железо = меньше время)
        if self.benchmark and self.benchmark.performance_multiplier > 0:
            return base_duration / self.benchmark.performance_multiplier
        
        return base_duration
    
    def get_all_estimates(self) -> Dict[str, float]:
        """Возвращает оценки для всех этапов.
        
        Returns:
            Словарь {stage: estimated_seconds}
        """
        return {
            stage: self.get_estimated_duration(stage)
            for stage in self.BASE_STAGE_DURATIONS.keys()
        }
    
    def get_metrics_summary(self) -> Dict:
        """Возвращает сводку метрик для API.
        
        Returns:
            Словарь с метриками
        """
        return {
            "benchmark": self.benchmark.to_dict() if self.benchmark else None,
            "stages": {
                name: metrics.to_dict()
                for name, metrics in self.stage_metrics.items()
            },
            "estimates": self.get_all_estimates(),
            "has_calibration": self.benchmark is not None,
            "total_samples": sum(m.count for m in self.stage_metrics.values())
        }


# Singleton
_performance_metrics: Optional[PerformanceMetrics] = None


def get_performance_metrics() -> PerformanceMetrics:
    """Возвращает singleton PerformanceMetrics.
    
    Returns:
        Экземпляр PerformanceMetrics
    """
    global _performance_metrics
    if _performance_metrics is None:
        _performance_metrics = PerformanceMetrics()
    return _performance_metrics


def reset_performance_metrics() -> None:
    """Сбрасывает singleton PerformanceMetrics."""
    global _performance_metrics
    _performance_metrics = None
