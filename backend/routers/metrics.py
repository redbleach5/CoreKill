"""API роутер для метрик производительности.

Предоставляет данные для MetricsDashboard на фронтенде.

Заметки по метрикам:
- Учёт ошибок требует расширения StageMetrics (errors_count: int)
- Реальный success_rate требует интеграции с workflow_graph.py
- Метрики моделей доступны через SystemBenchmark
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter

from infrastructure.performance_metrics import get_performance_metrics, PerformanceMetrics
from utils.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api", tags=["metrics"])


def _get_model_metrics(metrics: PerformanceMetrics) -> list[dict[str, Any]]:
    """Возвращает метрики по моделям из бенчмарка.
    
    Args:
        metrics: Экземпляр PerformanceMetrics
        
    Returns:
        Список словарей с метриками моделей
    """
    if not metrics.benchmark:
        return []
    
    return [{
        "model": metrics.benchmark.model_used,
        "tokens_per_second": metrics.benchmark.tokens_per_second,
        "performance_multiplier": metrics.benchmark.performance_multiplier,
        "last_benchmark": metrics.benchmark.timestamp
    }]


@router.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """Возвращает метрики производительности для дашборда.
    
    Returns:
        Словарь с метриками генерации, этапов и моделей
    """
    metrics = get_performance_metrics()
    
    # Собираем данные по этапам
    stage_data = []
    for stage_name, stage_metrics in metrics.stage_metrics.items():
        stage_data.append({
            "stage": stage_name,
            "avg_time_ms": int(stage_metrics.avg * 1000),
            "calls": stage_metrics.count,
            "errors": 0  # Учёт ошибок требует расширения StageMetrics
        })
    
    # Сортируем по времени (самые долгие первые)
    stage_data.sort(key=lambda x: float(x["avg_time_ms"]), reverse=True)  # type: ignore[arg-type]
    
    # Общие метрики генерации
    total_generations = sum(s.count for s in metrics.stage_metrics.values()) // max(len(metrics.stage_metrics), 1)
    # Расчёт successful/failed требует integration с workflow_graph для реального tracking
    successful = total_generations  # Предполагаем что успешные (ошибки отслеживаются отдельно в логах)
    failed = 0
    
    # Среднее время полного цикла
    total_avg_time = sum(s.avg for s in metrics.stage_metrics.values())
    
    return {
        "generation": {
            "total_generations": total_generations,
            "successful": successful,
            "failed": failed,
            "avg_time_ms": int(total_avg_time * 1000),
            "avg_iterations": 1.0,  # Базовое значение (tracking через workflow_graph)
            "success_rate": 1.0 if total_generations == 0 else successful / total_generations
        },
        "stages": stage_data[:10],  # Топ 10 этапов
        "models": _get_model_metrics(metrics),  # Метрики по моделям из бенчмарка
        "last_updated": datetime.now().isoformat()
    }


@router.get("/metrics/stages")
async def get_stage_metrics() -> dict[str, Any]:
    """Возвращает детальные метрики по этапам."""
    metrics = get_performance_metrics()
    
    return {
        "stages": {
            name: stage.to_dict()
            for name, stage in metrics.stage_metrics.items()
        },
        "last_updated": datetime.now().isoformat()
    }


@router.get("/metrics/benchmark")
async def get_benchmark() -> dict[str, Any]:
    """Возвращает результаты бенчмарка системы."""
    metrics = get_performance_metrics()
    benchmark = metrics.benchmark
    
    if not benchmark:
        return {
            "benchmark": None,
            "multiplier": 1.0
        }
    
    return {
        "benchmark": {
            "tokens_per_second": benchmark.tokens_per_second,
            "time_to_first_token": benchmark.time_to_first_token,
            "model_used": benchmark.model_used,
            "timestamp": benchmark.timestamp,
            "performance_multiplier": benchmark.performance_multiplier
        },
        "multiplier": getattr(metrics, 'time_multiplier', 1.0)
    }
