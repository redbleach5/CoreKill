"""Абстракция для выбора и роутинга моделей.

Поддерживает:
- Выбор одной модели (текущая реализация)
- Умный выбор по сложности задачи
- Динамическое сканирование доступных моделей
- Роевое использование моделей (будущее расширение)
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from utils.model_checker import (
    check_model_available,
    get_any_available_model,
    get_light_model,
    get_coder_model,
    get_all_available_models,
    get_best_model_for_complexity,
    get_reasoning_model,
    get_all_reasoning_models,
    scan_available_models,
    invalidate_models_cache,
    TaskComplexity,
    ModelInfo
)
from utils.config import get_config
from utils.logger import get_logger

logger = get_logger()


@dataclass
class ModelSelection:
    """Результат выбора модели."""
    model: str
    confidence: float = 1.0
    reason: str = ""  # Почему выбрана эта модель
    metadata: Optional[Dict[str, Any]] = None
    is_reasoning: bool = False  # Является ли модель reasoning (DeepSeek-R1, QwQ)


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
    - Complexity-based selection (умный выбор по сложности)
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
            context: Дополнительный контекст для выбора (complexity, agent, etc.)
            
        Returns:
            ModelSelection с выбранной моделью
        """
        pass
    
    @abstractmethod
    def select_model_for_complexity(
        self,
        complexity: TaskComplexity,
        task_type: str = "coding",
        preferred_model: Optional[str] = None
    ) -> ModelSelection:
        """Выбирает модель на основе сложности задачи.
        
        Args:
            complexity: Сложность задачи (simple, medium, complex)
            task_type: Тип задачи
            preferred_model: Предпочтительная модель (если указана и подходит)
            
        Returns:
            ModelSelection с оптимальной моделью
        """
        pass
    
    @abstractmethod
    def select_model_roster(
        self,
        task_type: str,
        preferred_models: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[ModelRosterSelection]:
        """Выбирает рой моделей для задачи (опционально).
        
        Args:
            task_type: Тип задачи
            preferred_models: Список предпочтительных моделей
            context: Дополнительный контекст
            
        Returns:
            ModelRosterSelection или None если роевое использование отключено
        """
        pass
    
    @abstractmethod
    def refresh_models(self) -> List[ModelInfo]:
        """Принудительно обновляет список доступных моделей.
        
        Returns:
            Список информации о доступных моделях
        """
        pass


class SmartModelRouter(ModelRouter):
    """Умный роутер моделей с выбором по сложности задачи.
    
    Особенности:
    - Динамическое сканирование моделей при старте
    - Выбор модели по сложности задачи
    - Приоритет reasoning моделей (DeepSeek-R1, QwQ) для complex задач
    - Приоритет качества для сложных задач
    - Приоритет скорости для простых задач
    """
    
    # Минимальное качество модели для каждой сложности
    MIN_QUALITY_THRESHOLDS = {
        TaskComplexity.SIMPLE: 0.3,   # Любая модель от 1.5B
        TaskComplexity.MEDIUM: 0.55,  # Минимум 7B или хорошая coder
        TaskComplexity.COMPLEX: 0.7,  # Минимум 7B coder или 13B+
    }
    
    def __init__(self, enable_roster: bool = False, prefer_reasoning: bool = True) -> None:
        """Инициализация умного роутера.
        
        Args:
            enable_roster: Включить поддержку роя моделей (по умолчанию False)
            prefer_reasoning: Предпочитать reasoning модели для complex задач
        """
        self.enable_roster = enable_roster
        self.prefer_reasoning = prefer_reasoning
        self.config = get_config()
        # Сканируем модели при инициализации
        self._models = scan_available_models(force_refresh=True)
        
        # Проверяем наличие reasoning моделей
        reasoning_models = get_all_reasoning_models()
        reasoning_count = len(reasoning_models)
        
        logger.info(
            f"🔍 SmartModelRouter инициализирован: "
            f"{len(self._models)} моделей, "
            f"{reasoning_count} reasoning"
        )
    
    def refresh_models(self) -> List[ModelInfo]:
        """Принудительно обновляет список доступных моделей."""
        invalidate_models_cache()
        self._models = scan_available_models(force_refresh=True)
        logger.info(f"🔄 Модели обновлены, найдено {len(self._models)} моделей")
        return list(self._models.values())
    
    def select_model(
        self,
        task_type: str,
        preferred_model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ModelSelection:
        """Выбирает модель для задачи с учётом контекста.
        
        Если в context передана complexity, использует её для умного выбора.
        """
        context = context or {}
        
        # Если указана предпочтительная модель и она доступна, используем её
        if preferred_model and check_model_available(preferred_model):
            return ModelSelection(
                model=preferred_model, 
                confidence=1.0,
                reason="Указана пользователем"
            )
        
        # Если передана сложность в контексте, используем умный выбор
        complexity = context.get("complexity")
        if complexity and isinstance(complexity, TaskComplexity):
            return self.select_model_for_complexity(
                complexity=complexity,
                task_type=task_type,
                preferred_model=preferred_model
            )
        
        # Для intent и planning используем лёгкие модели (скорость важнее)
        if task_type in ["intent", "planning"]:
            model = get_light_model()
            if model:
                return ModelSelection(
                    model=model, 
                    confidence=0.9,
                    reason="Лёгкая модель для быстрых операций"
                )
        
        # Для генерации кода выбираем модель по сложности
        if task_type == "coding":
            # Для coding — medium сложность (может использовать reasoning)
            return self.select_model_for_complexity(
                complexity=TaskComplexity.MEDIUM,
                task_type=task_type,
                preferred_model=preferred_model
            )
        
        if task_type in ["testing", "reflection", "debug"]:
            # Для testing/reflection/debug — SIMPLE, быстрая модель
            # Reasoning модели слишком медленные для этих задач
            return self.select_model_for_complexity(
                complexity=TaskComplexity.SIMPLE,
                task_type=task_type,
                preferred_model=preferred_model
            )
        
        # Fallback: любая доступная модель
        model = get_any_available_model()
        if model:
            return ModelSelection(
                model=model, 
                confidence=0.7,
                reason="Fallback: любая доступная модель"
            )
        
        # Если ничего не найдено
        available = get_all_available_models()
        if not available:
            raise RuntimeError(
                "Нет доступных моделей Ollama. "
                "Установите хотя бы одну модель через: ollama pull <model_name>"
            )
        
        return ModelSelection(
            model=available[0], 
            confidence=0.3,
            reason="Крайний fallback"
        )
    
    def select_model_for_complexity(
        self,
        complexity: TaskComplexity,
        task_type: str = "coding",
        preferred_model: Optional[str] = None,
        prefer_reasoning: Optional[bool] = None
    ) -> ModelSelection:
        """Выбирает оптимальную модель на основе сложности задачи.
        
        Логика:
        - SIMPLE: быстрая модель (1.5B-4B), скорость важнее качества
        - MEDIUM: баланс (7B coder), хорошее качество и приемлемая скорость
        - COMPLEX: reasoning модель (DeepSeek-R1, QwQ) если доступна, иначе 7B+ coder
        
        Учитывает hardware лимиты из конфига:
        - max_model_vram_gb: максимальный размер модели
        - allow_heavy_models: разрешить 30B+ модели
        - allow_ultra_models: разрешить 100B+ модели
        
        Args:
            complexity: Сложность задачи
            task_type: Тип задачи (coding, testing, debug, etc.)
            preferred_model: Предпочтительная модель (если указана и подходит)
            prefer_reasoning: Предпочитать reasoning модели (по умолчанию self.prefer_reasoning)
        """
        # Обновляем модели для актуальности
        self._models = scan_available_models()
        
        if not self._models:
            raise RuntimeError("Нет доступных моделей Ollama")
        
        # Фильтруем модели по hardware лимитам
        available_models = self._filter_by_hardware_limits(self._models)
        
        if not available_models:
            logger.warning("⚠️ Все модели отфильтрованы по hardware лимитам, используем все доступные")
            available_models = self._models
        
        # Определяем, нужно ли предпочитать reasoning модели
        use_reasoning = prefer_reasoning if prefer_reasoning is not None else self.prefer_reasoning
        
        # Для COMPLEX задач пробуем сначала reasoning модель
        if complexity == TaskComplexity.COMPLEX and use_reasoning:
            reasoning_selection = self._try_select_reasoning_model(available_models)
            if reasoning_selection:
                logger.info(
                    f"🧠 Выбрана reasoning модель {reasoning_selection.model} "
                    f"для complex задачи (рассуждает в <think> блоках)"
                )
                return reasoning_selection
        
        # Если указана предпочтительная модель, проверяем её качество
        if preferred_model and preferred_model in available_models:
            model_info = available_models[preferred_model]
            min_quality = self.MIN_QUALITY_THRESHOLDS[complexity]
            
            if model_info.estimated_quality >= min_quality:
                logger.info(
                    f"✅ Используется предпочтительная модель {preferred_model} "
                    f"(качество {model_info.estimated_quality:.2f} >= {min_quality})"
                )
                return ModelSelection(
                    model=preferred_model,
                    confidence=0.95,
                    reason=f"Предпочтительная модель подходит для {complexity.value} задачи",
                    metadata={"quality": model_info.estimated_quality, "tier": model_info.tier},
                    is_reasoning=model_info.is_reasoning
                )
            else:
                logger.warning(
                    f"⚠️ Модель {preferred_model} (качество {model_info.estimated_quality:.2f}) "
                    f"недостаточна для {complexity.value} задачи (требуется >= {min_quality})"
                )
        
        # Выбираем лучшую модель для сложности с учётом фильтров
        best_model = self._select_best_from_filtered(
            available_models,
            complexity=complexity,
            prefer_coder=(task_type in ["coding", "testing", "debug"])
        )
        
        if best_model:
            best_model_info: ModelInfo | None = available_models.get(best_model)
            quality = best_model_info.estimated_quality if best_model_info else 0.5
            tier = best_model_info.tier if best_model_info else "unknown"
            is_reasoning = best_model_info.is_reasoning if best_model_info else False
            
            logger.info(
                f"🤖 Выбрана модель {best_model} для {complexity.value} задачи "
                f"(качество: {quality:.2f}, tier: {tier}"
                f"{', reasoning' if is_reasoning else ''})"
            )
            
            return ModelSelection(
                model=best_model,
                confidence=0.9,
                reason=f"Оптимальная модель для {complexity.value} задачи",
                metadata={"quality": quality, "complexity": complexity.value, "tier": tier},
                is_reasoning=is_reasoning
            )
        
        # Крайний fallback
        first_model = list(available_models.keys())[0]
        return ModelSelection(
            model=first_model,
            confidence=0.5,
            reason="Fallback: первая доступная модель"
        )
    
    def _try_select_reasoning_model(
        self, 
        available_models: Dict[str, ModelInfo]
    ) -> Optional[ModelSelection]:
        """Пытается выбрать reasoning модель (DeepSeek-R1, QwQ).
        
        Args:
            available_models: Доступные модели после фильтрации
            
        Returns:
            ModelSelection с reasoning моделью или None
        """
        min_quality = self.MIN_QUALITY_THRESHOLDS[TaskComplexity.COMPLEX]
        
        # Ищем reasoning модели среди доступных
        reasoning_models = [
            m for m in available_models.values()
            if m.is_reasoning and m.estimated_quality >= min_quality
        ]
        
        if not reasoning_models:
            return None
        
        # Выбираем лучшую reasoning модель: сначала по качеству, затем по размеру
        # Это гарантирует выбор самой мощной модели при одинаковом качестве
        import re
        def _model_priority(m: ModelInfo) -> tuple[float, float]:
            """Приоритет модели: (качество, размер_параметров_в_миллиардах)."""
            param_match = re.search(r'(\d+\.?\d*)', m.parameter_size)
            param_value = float(param_match.group(1)) if param_match else 0.0
            return (m.estimated_quality, param_value)
        
        best = max(reasoning_models, key=_model_priority)
        
        return ModelSelection(
            model=best.name,
            confidence=0.95,
            reason="Reasoning модель для complex задачи (встроенный CoT)",
            metadata={
                "quality": best.estimated_quality,
                "tier": best.tier,
                "reasoning": True
            },
            is_reasoning=True
        )
    
    def _filter_by_hardware_limits(
        self, 
        models: Dict[str, ModelInfo]
    ) -> Dict[str, ModelInfo]:
        """Фильтрует модели по hardware лимитам из конфига.
        
        Args:
            models: Словарь моделей
            
        Returns:
            Отфильтрованный словарь моделей
        """
        max_vram = self.config.max_model_vram_gb
        allow_heavy = self.config.allow_heavy_models
        allow_ultra = self.config.allow_ultra_models
        
        filtered = {}
        for name, info in models.items():
            # Пропускаем embed модели
            if 'embed' in name.lower():
                continue
            
            # Проверяем VRAM лимит
            if max_vram > 0 and info.estimated_vram_gb > max_vram:
                logger.debug(f"⏭️ Модель {name} пропущена: VRAM {info.estimated_vram_gb}GB > лимит {max_vram}GB")
                continue
            
            # Проверяем tier лимиты
            if info.tier == 'heavy' and not allow_heavy:
                logger.debug(f"⏭️ Модель {name} пропущена: heavy модели отключены")
                continue
            
            if info.tier == 'ultra' and not allow_ultra:
                logger.debug(f"⏭️ Модель {name} пропущена: ultra модели отключены")
                continue
            
            filtered[name] = info
        
        return filtered
    
    def _select_best_from_filtered(
        self,
        models: Dict[str, ModelInfo],
        complexity: TaskComplexity,
        prefer_coder: bool = True
    ) -> Optional[str]:
        """Выбирает лучшую модель из отфильтрованного списка.
        
        Args:
            models: Отфильтрованные модели
            complexity: Сложность задачи
            prefer_coder: Предпочитать coder модели
            
        Returns:
            Название лучшей модели
        """
        if not models:
            return None
        
        candidates = list(models.values())
        min_quality = self.MIN_QUALITY_THRESHOLDS[complexity]
        
        # Фильтруем по минимальному качеству
        suitable = [m for m in candidates if m.estimated_quality >= min_quality]
        
        if not suitable:
            # Берём лучшую из доступных
            suitable = candidates
        
        # Для coder задач предпочитаем coder модели
        if prefer_coder:
            coder_models = [m for m in suitable if m.is_coder]
            if coder_models:
                suitable = coder_models
        
        # Для SIMPLE выбираем минимально подходящую (быстрее)
        # Для MEDIUM/COMPLEX выбираем лучшую
        if complexity == TaskComplexity.SIMPLE:
            best = min(suitable, key=lambda m: m.estimated_quality)
        else:
            best = max(suitable, key=lambda m: m.estimated_quality)
        
        return best.name
    
    def select_model_roster(
        self,
        task_type: str,
        preferred_models: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[ModelRosterSelection]:
        """Выбирает рой моделей (опционально, по умолчанию отключено)."""
        if not self.enable_roster:
            return None
        
        # Будущая реализация роя моделей
        return None


# Legacy alias для обратной совместимости
SimpleModelRouter = SmartModelRouter


# Глобальный экземпляр роутера (можно заменить на другую реализацию)
_default_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Возвращает глобальный экземпляр ModelRouter.
    
    Использует SmartModelRouter с умным выбором по сложности.
    
    Returns:
        ModelRouter экземпляр
    """
    global _default_router
    
    if _default_router is None:
        config = get_config()
        # Проверяем конфиг на наличие настройки роя моделей и reasoning
        enable_roster = getattr(config, 'enable_model_roster', False)
        prefer_reasoning = getattr(config, 'prefer_reasoning_models', True)
        _default_router = SmartModelRouter(
            enable_roster=enable_roster,
            prefer_reasoning=prefer_reasoning
        )
    
    return _default_router


def set_model_router(router: ModelRouter) -> None:
    """Устанавливает глобальный роутер (для тестирования или кастомизации).
    
    Args:
        router: Экземпляр ModelRouter
    """
    global _default_router
    _default_router = router


def reset_model_router() -> None:
    """Сбрасывает глобальный роутер для пересоздания.
    
    Полезно после добавления/удаления моделей Ollama.
    """
    global _default_router
    _default_router = None
    invalidate_models_cache()
