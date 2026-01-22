"""Централизованная конфигурация для workflow.

Предоставляет единый интерфейс для доступа к настройкам workflow,
стриминга, инкрементального кодирования и других параметров.
"""
from typing import Dict, Any
from utils.config import get_config
from utils.model_checker import TaskComplexity


class WorkflowConfig:
    """Централизованный конфигурационный сервис для workflow.
    
    Предоставляет типизированный доступ к настройкам из config.toml,
    избегая разбросанных проверок конфигурации по коду.
    """
    
    _instance: 'WorkflowConfig | None' = None
    
    def __new__(cls) -> 'WorkflowConfig':
        """Singleton паттерн."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = get_config()
        return cls._instance
    
    @property
    def streaming_enabled(self) -> bool:
        """Проверяет включён ли режим стриминга."""
        try:
            streaming_config = self._config._config_data.get("streaming", {})
            return streaming_config.get("use_streaming_agents", False)
        except Exception:
            return False
    
    @property
    def incremental_coding(self) -> Dict[str, Any]:
        """Возвращает конфигурацию инкрементального кодирования."""
        return self._config._config_data.get("incremental_coding", {})
    
    def should_use_incremental(self, complexity: TaskComplexity) -> bool:
        """Проверяет, нужно ли использовать инкрементальное кодирование.
        
        Args:
            complexity: Сложность задачи
            
        Returns:
            True если нужно использовать инкрементальное кодирование
        """
        config = self.incremental_coding
        if not config.get("enabled", False):
            return False
        
        min_complexity_map = {
            "simple": TaskComplexity.SIMPLE,
            "medium": TaskComplexity.MEDIUM,
            "complex": TaskComplexity.COMPLEX
        }
        min_complexity_str = config.get("min_complexity", "complex")
        min_complexity = min_complexity_map.get(
            min_complexity_str,
            TaskComplexity.COMPLEX
        )
        
        # Сравниваем по значению enum
        complexity_values = {
            TaskComplexity.SIMPLE: 1,
            TaskComplexity.MEDIUM: 2,
            TaskComplexity.COMPLEX: 3
        }
        
        return complexity_values.get(complexity, 0) >= complexity_values.get(min_complexity, 3)
    
    def get_stage_timeout(self, stage: str) -> int:
        """Получает таймаут для этапа.
        
        Args:
            stage: Название этапа (planning, coding, etc.)
            
        Returns:
            Таймаут в секундах
        """
        timeouts = self._config._config_data.get("timeouts", {})
        return timeouts.get(stage, timeouts.get("default", 120))
    
    def get_temperature(self, stage: str | None = None) -> float:
        """Получает температуру для этапа.
        
        Args:
            stage: Название этапа (опционально)
            
        Returns:
            Температура (0.0-1.0)
        """
        if stage:
            stage_config = self._config._config_data.get("stages", {}).get(stage, {})
            if "temperature" in stage_config:
                return float(stage_config["temperature"])
        
        return float(self._config._config_data.get("default", {}).get("temperature", 0.25))
    
    def reload(self) -> None:
        """Перезагружает конфигурацию."""
        self._config.reload()


# === Удобная функция для импорта ===

def get_workflow_config() -> WorkflowConfig:
    """Возвращает экземпляр WorkflowConfig.
    
    Returns:
        Singleton экземпляр WorkflowConfig
    """
    return WorkflowConfig()
