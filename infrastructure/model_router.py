"""Абстракция для выбора и роутинга моделей.

Поддерживает:
- Выбор одной модели (текущая реализация)
- Роевое использование моделей (будущее расширение)
- Разные стратегии выбора моделей
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from utils.model_checker import (
    check_model_available,
    get_any_available_model,
    get_light_model,
    get_all_available_models
)
from utils.config import get_config


@dataclass
class ModelSelection:
    """Результат выбора модели."""
    model: str
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelRosterSelection:
    """Результат выбора роя моделей (для будущего расширения)."""
    models: List[str]
    strategy: str  # "single", "parallel", "cascade", "voting"
    metadata: Optional[Dict[str, Any]] = None


class ModelRouter(ABC):
    """Абстрактный интерфейс для роутинга моделей.
    
    Позволяет реализовать разные стратегии выбора моделей:
    - Single model (текущая реализация)
    - Model roster/ensemble (будущее расширение)
    """
    
    @abstractmethod
    def select_model(
        self,
        task_type: str,
        preferred_model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ModelSelection:
        """Выбирает модель для задачи.
        
        Args:
            task_type: Тип задачи (intent, planning, coding, testing, reflection)
            preferred_model: Предпочтительная модель (если указана)
            context: Дополнительный контекст для выбора
            
        Returns:
            ModelSelection с выбранной моделью
        """
        pass
    
    @abstractmethod
    def select_model_roster(
        self,
        task_type: str,
        preferred_models: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[ModelRosterSelection]:
        """Выбирает рое моделей для задачи (опционально).
        
        Args:
            task_type: Тип задачи
            preferred_models: Список предпочтительных моделей
            context: Дополнительный контекст
            
        Returns:
            ModelRosterSelection или None если роевое использование отключено
        """
        pass


class SimpleModelRouter(ModelRouter):
    """Простая реализация роутера - выбирает одну модель.
    
    Текущая реализация, совместимая с существующим кодом.
    """
    
    def __init__(self, enable_roster: bool = False) -> None:
        """Инициализация простого роутера.
        
        Args:
            enable_roster: Включить поддержку роя моделей (по умолчанию False)
        """
        self.enable_roster = enable_roster
        self.config = get_config()
    
    def select_model(
        self,
        task_type: str,
        preferred_model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ModelSelection:
        """Выбирает одну модель для задачи."""
        # Если указана предпочтительная модель и она доступна, используем её
        if preferred_model and check_model_available(preferred_model):
            return ModelSelection(model=preferred_model, confidence=1.0)
        
        # Выбираем модель в зависимости от типа задачи
        if task_type in ["intent", "planning"]:
            # Для быстрых операций предпочитаем легкие модели
            model = get_light_model()
            if model:
                return ModelSelection(model=model, confidence=0.9)
        
        # Для остальных задач используем модели из конфига
        if task_type in ["coding", "testing", "reflection"]:
            preferred = self.config.default_model
            fallback = self.config.fallback_model
            
            if check_model_available(preferred):
                return ModelSelection(model=preferred, confidence=0.95)
            elif check_model_available(fallback):
                return ModelSelection(model=fallback, confidence=0.85)
        
        # Используем любую доступную модель
        model = get_any_available_model()
        if model:
            return ModelSelection(model=model, confidence=0.7)
        
        # Последний fallback - пробуем модель из конфига, если она доступна
        config_model = preferred_model or self.config.default_model
        if config_model and check_model_available(config_model):
            return ModelSelection(model=config_model, confidence=0.5)
        
        # Если ничего не найдено, выбрасываем исключение - модель обязательна
        available = get_all_available_models()
        if not available:
            raise RuntimeError(
                "Нет доступных моделей Ollama. "
                "Установите хотя бы одну модель через: ollama pull <model_name>"
            )
        
        # Если дошли сюда, что-то пошло не так, но модели есть
        return ModelSelection(model=available[0], confidence=0.3)
    
    def select_model_roster(
        self,
        task_type: str,
        preferred_models: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[ModelRosterSelection]:
        """Выбирает рое моделей (опционально, по умолчанию отключено)."""
        if not self.enable_roster:
            return None
        
        # Будущая реализация роя моделей
        # Пока возвращаем None, чтобы не нарушать текущую архитектуру
        return None


# Глобальный экземпляр роутера (можно заменить на другую реализацию)
_default_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Возвращает глобальный экземпляр ModelRouter.
    
    Returns:
        ModelRouter экземпляр
    """
    global _default_router
    
    if _default_router is None:
        config = get_config()
        # Проверяем конфиг на наличие настройки роя моделей
        enable_roster = getattr(config, 'enable_model_roster', False)
        _default_router = SimpleModelRouter(enable_roster=enable_roster)
    
    return _default_router


def set_model_router(router: ModelRouter) -> None:
    """Устанавливает глобальный роутер (для тестирования или кастомизации).
    
    Args:
        router: Экземпляр ModelRouter
    """
    global _default_router
    _default_router = router
