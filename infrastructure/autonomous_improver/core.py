"""Модуль автономного улучшения проекта.

Версия: v2-universal (Этап 2 завершён)
Статус: Универсальная реализация с поддержкой Python + Frontend

Работает в фоне в свободное время, анализирует кодовую базу и предлагает
аргументированные улучшения при высокой уверенности.

Поддерживает:
- Python (.py) - через PythonAdapter
- Frontend (JS/TS/TSX/HTML/MD/JSON) - через FrontendAdapter
- Mixed проекты - через MultiAdapter

Особенности:
- Работает только в свободное время (не блокирует основной процесс)
- Использует легкие модели для экономии ресурсов
- Накапливает уверенность в предложениях (effective_confidence)
- НЕ применяет изменения автоматически - только предлагает пользователю
- Умная логика принятия решений на основе анализа кода
- Веб-поиск через Tavily при отсутствии прогресса или низкой уверенности
- Логирование в отдельный файл logs/autonomous_improver.log

Публичный API (зафиксирован):
- start() - запуск фонового анализа
- stop() - остановка анализа
- get_suggestions(min_confidence) - получение предложений
- get_metrics() - получение метрик работы модуля
"""
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import time

# Импорты остаются теми же - модуль всё ещё в infrastructure/
from infrastructure.local_llm import LocalLLM, LLMTimeoutError
from infrastructure.ast_analyzer import ASTAnalyzer, FileAnalysis
from infrastructure.web_search import web_search, tavily_search
from utils.model_checker import get_light_model, check_model_available, TaskComplexity
from utils.config import get_config
from infrastructure.cache import get_cache
import logging


# Настраиваем отдельный логгер для Autonomous Improver
# Логи пишутся в logs/autonomous_improver.log (в корне проекта)
# Скрипт находится в infrastructure/autonomous_improver/core.py
# Нужно подняться на 2 уровня вверх до корня проекта
_log_file = Path(__file__).parent.parent.parent / "logs" / "autonomous_improver.log"
_log_file.parent.mkdir(parents=True, exist_ok=True)

# Создаём отдельный логгер с файловым хендлером
logger = logging.getLogger("autonomous_improver")
logger.setLevel(logging.INFO)
logger.handlers.clear()  # Убираем существующие хендлеры

# Файловый хендлер
file_handler = logging.FileHandler(_log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Консольный хендлер
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    'ℹ️ [%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

logger.propagate = False  # Не передаём события в корневой логгер


class ImprovementType(str, Enum):
    """Тип улучшения (универсальный для всех языков)."""
    # Общие типы
    CODE_QUALITY = "code_quality"  # Улучшение качества кода (читаемость, поддерживаемость)
    PERFORMANCE = "performance"  # Оптимизация производительности
    SECURITY = "security"  # Улучшение безопасности
    DOCUMENTATION = "documentation"  # Добавление документации
    REFACTORING = "refactoring"  # Рефакторинг
    ARCHITECTURE = "architecture"  # Архитектурные улучшения
    
    # Фронтенд-специфичные типы
    ACCESSIBILITY = "accessibility"  # Доступность (a11y)
    UX = "ux"  # User experience
    TYPES = "types"  # TypeScript типизация
    COMPONENT_DESIGN = "component_design"  # Структура компонентов


@dataclass
class ImprovementSuggestion:
    """Предложение по улучшению проекта."""
    type: ImprovementType
    file_path: str
    description: str  # Описание проблемы/улучшения
    suggestion: str  # Конкретное предложение
    confidence: float  # Уверенность (0.0-1.0)
    priority: int  # Приоритет (1-10, 10 = критично)
    reasoning: str  # Обоснование улучшения
    estimated_impact: str  # Оценка влияния ("low", "medium", "high")
    code_example: Optional[str] = None  # Пример кода (если применимо)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectAnalysis:
    """Результат анализа проекта."""
    analyzed_files: int  # Количество файлов проанализировано в этом цикле
    total_files: int  # Всего файлов в проекте
    suggestions: List[ImprovementSuggestion]
    metrics: Dict[str, Any]
    timestamp: datetime


class AutonomousImprover:
    """Автономный анализатор и улучшатель кода (v1-python-specific).
    
    Зафиксированная базовая реализация для Python-проектов.
    
    Публичный API:
    - start() -> None - запуск фонового анализа
    - stop() -> None - остановка анализа
    - get_suggestions(min_confidence) -> List[ImprovementSuggestion] - получение предложений
    - get_metrics() -> Dict[str, Any] - получение метрик
    
    См. API_REFERENCE.md для детальной документации.
    """
    """Автономный улучшатель проекта.
    
    Работает в фоне, анализирует кодовую базу и накапливает уверенность
    в предложениях. Предлагает улучшения только при 100% уверенности.
    """
    
    # Системный промпт для анализа улучшений (DEPRECATED - используйте PromptBuilder)
    # Оставлен для обратной совместимости, но не используется напрямую
    ANALYSIS_PROMPT = """Ты — опытный senior разработчик, анализирующий код проекта.

Твоя задача — найти возможности для улучшения кода и оценить их уверенность.

## Правила анализа:
1. Будь КРИТИЧНЫМ — предлагай только реальные улучшения
2. Оценивай уверенность ЧЕСТНО (0.0-1.0)
3. Предлагай улучшения только если уверенность >= 0.9
4. Фокусируйся на:
   - Качестве кода (читаемость, поддерживаемость)
   - Производительности (оптимизация, избегай N+1 запросов, неэффективных алгоритмов)
   - Безопасности (SQL-инъекции, XSS, инъекции кода, небезопасные операции)
   - Документации (отсутствующие docstrings/комментарии, неясные имена)
   - Архитектуре (нарушения SOLID, DRY, магические числа, длинные функции)
   - Соответствии стандартам проекта (PEP 8 для Python, ESLint/TypeScript для фронтенда)
   - Доступности (accessibility, a11y) для UI/UX кода

## Важные критерии:
- Безопасность: проверяй на SQL-инъекции, XSS, инъекции кода, небезопасные eval/exec
- Производительность: избегай N+1 запросов, неэффективных алгоритмов, лишних циклов
- Читаемость: сложные конструкции, магические числа, длинные функции (>50 строк)
- Соответствие PEP 8: именование, отступы, длина строк
- DRY: дублирование кода, повторяющиеся паттерны
- SOLID: нарушения принципов (большие классы, множественная ответственность)

## Формат кода примера:
Если предлагаешь исправление, покажи ДО и ПОСЛЕ:
```python
# Было (проблема):
# ...проблемный код...

# Стало (решение):
# ...улучшенный код...
```

## Формат ответа (JSON):
{
  "suggestions": [
    {
      "type": "code_quality|performance|security|documentation|refactoring|architecture",
      "file_path": "путь/к/файлу.py",
      "description": "Краткое описание проблемы",
      "suggestion": "Конкретное предложение по улучшению",
      "confidence": 0.95,
      "priority": 8,
      "reasoning": "Обоснование почему это улучшение",
      "estimated_impact": "low|medium|high",
      "code_example": "Пример улучшенного кода (опционально)"
    }
  ]
}

Отвечай ТОЛЬКО валидным JSON, без дополнительного текста."""

    def __init__(
        self,
        project_path: Optional[str] = None,
        model: Optional[str] = None,
        min_confidence: float = 1.0,  # Только 100% уверенность
        max_files_per_cycle: int = 10,  # Максимум файлов за цикл
        cycle_interval_seconds: int = 300,  # Интервал между циклами (5 минут)
        profile: Optional["ProjectProfile"] = None,  # Профиль проекта (опционально)
        adapter: Optional["LanguageAdapter"] = None  # Адаптер языка (опционально, автовыбор)
    ):
        """Инициализация автономного улучшателя.
        
        Args:
            project_path: Путь к проекту (None = текущая директория)
            model: Модель для анализа (None = автовыбор легкой)
            min_confidence: Минимальная уверенность для предложения (по умолчанию 1.0 = 100%)
            max_files_per_cycle: Максимум файлов для анализа за цикл
            cycle_interval_seconds: Интервал между циклами анализа
        """
        self.config = get_config()
        # ИСПРАВЛЕНИЕ: Проверяем что project_path не является Mock объектом из тестов
        # Это предотвращает ошибки когда тесты передают Mock объекты в production код
        from utils.test_mode import is_test_mode
        
        if project_path:
            # Проверяем что это реальная строка, а не Mock
            if not isinstance(project_path, str):
                # Если это не строка, проверяем не Mock ли это
                type_str = str(type(project_path))
                if 'unittest.mock' in type_str or 'Mock' in type_str or 'MagicMock' in type_str:
                    # Это Mock объект из теста - используем текущую директорию
                    project_path = None
                elif hasattr(project_path, '__fspath__'):
                    # Это Path объект - конвертируем в строку
                    project_path = str(project_path)
                else:
                    # Неизвестный тип - используем текущую директорию
                    project_path = None
        
        # Создаём Path объект только если project_path - валидная строка
        if project_path and isinstance(project_path, str):
            try:
                self.project_path = Path(project_path)
            except (TypeError, ValueError):
                # Если не удалось создать Path, используем текущую директорию
                self.project_path = Path.cwd()
        else:
            self.project_path = Path.cwd()
        
        # В тестовом режиме не запускаем фоновые задачи
        self._test_mode = is_test_mode()
        self.max_files_per_cycle = max_files_per_cycle
        self.cycle_interval = cycle_interval_seconds
        
        # Профиль проекта (для убирания хардкода) - создаём ДО использования
        if profile is None:
            from .project_profile import ProjectProfile
            # Автоматически определяем профиль
            self.profile = ProjectProfile.detect_from_project(str(self.project_path))
        else:
            self.profile = profile
        
        logger.debug(f"📋 Профиль проекта: {self.profile.language}, {self.profile.domain}, {self.profile.framework}")
        
        # Используем min_confidence из профиля, если не передан явно
        if min_confidence == 1.0:  # Значение по умолчанию
            self.min_confidence = self.profile.confidence_policy.min_confidence
        else:
            self.min_confidence = min_confidence
        
        # Language Adapter (для поддержки разных языков)
        if adapter is None:
            # Автовыбор адаптера на основе профиля
            from .adapters import PythonAdapter, FrontendAdapter, MultiAdapter
            
            if self.profile.language == "python":
                self.adapter = PythonAdapter()
            elif self.profile.language in ["typescript", "javascript"]:
                self.adapter = FrontendAdapter()
            elif self.profile.language == "mixed":
                # Для mixed используем MultiAdapter с обоими адаптерами
                self.adapter = MultiAdapter([
                    PythonAdapter(),
                    FrontendAdapter()
                ])
            else:
                self.adapter = PythonAdapter()  # Fallback
        else:
            self.adapter = adapter
        
        logger.debug(f"🔌 Language Adapter: {self.adapter.language}")
        
        # Список доступных моделей для fallback
        self._available_models: List[str] = []
        self._current_model_index: int = 0
        
        # Инициализируем список доступных моделей
        self._refresh_available_models()
        
        # Используем SmartModelRouter для адаптивного выбора моделей
        from infrastructure.model_router import get_model_router
        self.model_router = get_model_router()
        
        # Выбираем начальную модель (для fallback)
        if model and check_model_available(model):
            if model in self._available_models:
                self._current_model_index = self._available_models.index(model)
            else:
                self._available_models.insert(0, model)
                self._current_model_index = 0
        else:
            # Автовыбор легкой модели
            light_model = self._select_light_model()
            if light_model in self._available_models:
                self._current_model_index = self._available_models.index(light_model)
            else:
                self._current_model_index = 0
        
        self.model = self._available_models[self._current_model_index]
        
        # Создаём базовый LLM (будет пересоздаваться для каждого файла с оптимальной моделью)
        self.llm = LocalLLM(
            model=self.model,
            temperature=0.2,  # Низкая температура для детерминированного анализа
            top_p=0.9,
            timeout=60,  # 60 секунд на анализ (увеличено для больших файлов)
            max_retries=1
        )
        
        logger.info(f"✅ Доступно моделей: {len(self._available_models)} ({', '.join(self._available_models[:3])}{'...' if len(self._available_models) > 3 else ''})")
        
        # AST анализатор для структурного анализа (используется PythonAdapter)
        # Для обратной совместимости оставляем, но предпочтительно использовать adapter
        self.ast_analyzer = ASTAnalyzer()
        
        # Кэш для отслеживания уже проанализированных файлов
        self._cache = get_cache()
        self._analyzed_files: Set[str] = set()
        self._suggestions: List[ImprovementSuggestion] = []
        
        # Кэш результатов анализа (хеш файла -> результаты)
        self._analysis_cache: Dict[str, List[ImprovementSuggestion]] = {}
        
        # Хеши предложений для валидации дубликатов
        self._suggestion_hashes: Set[str] = set()
        
        # Статусы файлов для умного повторного анализа
        # file_path -> (last_analysis_time, has_suggestions, max_confidence_found)
        self._file_statuses: Dict[str, tuple[float, bool, float]] = {}
        
        # Confidence Accumulator для накопления уверенности между циклами
        from .confidence_accumulator import ConfidenceAccumulator
        self._confidence_accumulator = ConfidenceAccumulator(
            min_observations=self.profile.confidence_policy.min_observations,
            stability_window_hours=self.profile.confidence_policy.stability_window_hours,
            max_history_size=10000  # Ограничение для предотвращения memory leaks
        )
        
        # Rate Limiter для веб-поиска
        from .rate_limiter import RateLimiter
        self._web_search_rate_limiter = RateLimiter(
            max_requests=10,  # Максимум 10 запросов
            window_seconds=60  # В минуту
        )
        
        # Настройки параллелизма
        self._max_parallel_files = getattr(self.config, 'autonomous_improver_max_parallel', 3)
        
        # Максимальное количество хранимых предложений (для предотвращения утечки памяти)
        self._max_stored_suggestions = 200
        
        # Флаг работы
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # Счётчики для определения необходимости веб-поиска
        self._cycles_without_progress: int = 0  # Циклы без новых предложений
        self._files_without_high_confidence: int = 0  # Файлы без высокоуверенных предложений
        
        # Настройки веб-поиска
        self._enable_web_search = self.config.web_search_timeout > 0 if hasattr(self.config, 'web_search_timeout') else True
        self._web_search_threshold_cycles = 2  # Использовать поиск после 2 циклов без прогресса
        self._web_search_threshold_files = 5  # Использовать поиск после 5 файлов без высокоуверенных предложений
        
        logger.info(f"✅ AutonomousImprover инициализирован (модель: {self.model}, проект: {self.project_path}, веб-поиск: {'включён' if self._enable_web_search else 'выключен'})")
    
    def _refresh_available_models(self) -> None:
        """Обновляет список доступных моделей."""
        from utils.model_checker import get_all_available_models, invalidate_models_cache
        
        try:
            # Список моделей зависит от OLLAMA_HOST. На всякий случай пересканируем.
            invalidate_models_cache()
            all_models = get_all_available_models()
            if all_models:
                self._available_models = all_models
                logger.info(f"📋 Найдено {len(all_models)} доступных моделей")
            else:
                # Если не удалось получить список, используем fallback
                from utils.model_checker import get_any_available_model
                any_model = get_any_available_model()
                if any_model:
                    self._available_models = [any_model]
                    logger.warning(f"⚠️ Использована fallback модель: {any_model}")
                else:
                    raise RuntimeError("Нет доступных моделей Ollama")
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка моделей: {e}")
            # Последняя попытка - используем любую доступную
            from utils.model_checker import get_any_available_model
            any_model = get_any_available_model()
            if any_model:
                self._available_models = [any_model]
            else:
                raise RuntimeError("Нет доступных моделей для AutonomousImprover")
    
    def _select_light_model(self) -> str:
        """Выбирает легкую модель для анализа."""
        light_model = get_light_model()
        if light_model and light_model in self._available_models:
            return light_model
        
        # Fallback на первую доступную
        if self._available_models:
            return self._available_models[0]
        
        raise RuntimeError("Нет доступных моделей для AutonomousImprover")
    
    def _switch_to_next_model(self) -> bool:
        """Переключается на следующую доступную модель.
        
        Returns:
            True если переключение успешно, False если больше нет моделей
        """
        if len(self._available_models) <= 1:
            return False
        
        self._current_model_index = (self._current_model_index + 1) % len(self._available_models)
        self.model = self._available_models[self._current_model_index]
        
        # Пересоздаём LLM с новой моделью
        self.llm = LocalLLM(
            model=self.model,
            temperature=0.2,
            top_p=0.9,
            timeout=60,  # 60 секунд на анализ
            max_retries=1
        )
        
        logger.warning(f"🔄 Переключение на модель: {self.model}")
        return True
    
    def start(self) -> None:
        """Запускает фоновую задачу анализа."""
        if self._running:
            logger.warning("⚠️ AutonomousImprover уже запущен")
            return
        
        # Упрощённая логика запуска - всегда предполагаем внешний event loop
        # Если loop не запущен, create_task вызовет RuntimeError, что корректно
        self._running = True
        try:
            self._task = asyncio.create_task(self._background_loop())
            logger.info("🚀 AutonomousImprover запущен в фоне")
        except RuntimeError as e:
            logger.error(f"❌ Нет активного event loop для запуска задачи: {e}")
            logger.error("   Убедитесь, что модуль запускается в контексте async приложения")
            self._running = False
            raise
    
    def stop(self) -> None:
        """Останавливает фоновую задачу."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
        
        logger.info("🛑 AutonomousImprover остановлен")
    
    async def _background_loop(self) -> None:
        """Основной цикл фонового анализа."""
        logger.info("🔄 AutonomousImprover: начало фонового цикла")
        
        while self._running:
            try:
                # Ждём интервал перед следующим циклом
                await asyncio.sleep(self.cycle_interval)
                
                # Проверяем, не занята ли система (можно добавить проверку нагрузки)
                if not self._should_analyze():
                    logger.debug("⏸️ AutonomousImprover: система занята, пропускаю цикл")
                    continue
                
                # Анализируем проект
                logger.info(f"🔄 [ЦИКЛ #{self._cycles_without_progress + 1}] Начало цикла анализа (интервал: {self.cycle_interval}с)")
                analysis = await self.analyze_project_async()
                
                # Сохраняем предложения с высокой уверенностью
                high_confidence_suggestions = [
                    s for s in analysis.suggestions
                    if s.confidence >= self.min_confidence
                ]
                
                # Улучшенная логика прогресса: учитываем любые предложения с confidence >= 0.8
                # как "слабый прогресс", а не только >= min_confidence
                high_confidence_suggestions = [
                    s for s in analysis.suggestions
                    if s.confidence >= self.min_confidence
                ]
                
                weak_progress_suggestions = [
                    s for s in analysis.suggestions
                    if 0.8 <= s.confidence < self.min_confidence
                ]
                
                if high_confidence_suggestions:
                    # Валидируем и добавляем предложения
                    validated_suggestions = [
                        s for s in high_confidence_suggestions
                        if self._validate_suggestion(s)
                    ]
                    
                    invalid_count = len(high_confidence_suggestions) - len(validated_suggestions)
                    if invalid_count > 0:
                        logger.warning(f"⚠️ [ЦИКЛ] Отфильтровано {invalid_count} невалидных предложений")
                    
                    if validated_suggestions:
                        logger.info(f"✅ [ЦИКЛ] Найдено {len(validated_suggestions)} валидных предложений с уверенностью >= {self.min_confidence}")
                        logger.info(f"📊 [ЦИКЛ] Всего предложений в системе: {len(self._suggestions)} → {len(self._suggestions) + len(validated_suggestions)}")
                        self._add_suggestions(validated_suggestions)
                        self._cycles_without_progress = 0  # Сбрасываем счётчик
                        self._files_without_high_confidence = 0
                        logger.info(f"🔄 [ЦИКЛ] Счётчики прогресса сброшены (циклы: 0, файлы: 0)")
                elif weak_progress_suggestions:
                    # Есть слабый прогресс - не увеличиваем счётчики, но и не сбрасываем полностью
                    logger.info(f"⚠️ [ЦИКЛ] Слабый прогресс: найдено {len(weak_progress_suggestions)} предложений с уверенностью 0.8-{self.min_confidence} (недостаточно для добавления)")
                    # Не увеличиваем счётчики, но и не сбрасываем - это промежуточное состояние
                else:
                    logger.warning(f"⚠️ [ЦИКЛ] Предложений не найдено (проанализировано файлов: {analysis.analyzed_files})")
                    self._cycles_without_progress += 1
                    self._files_without_high_confidence += analysis.analyzed_files
                    logger.info(f"📉 [ЦИКЛ] Прогресс: циклов без результата={self._cycles_without_progress}, файлов без результата={self._files_without_high_confidence}")
                    
                    # Если нет прогресса, включаем веб-поиск для следующего цикла
                    if self._enable_web_search and (
                        self._cycles_without_progress >= self._web_search_threshold_cycles or
                        self._files_without_high_confidence >= self._web_search_threshold_files
                    ):
                        logger.info(f"🔍 [ЦИКЛ] Активация веб-поиска: нет прогресса ({self._cycles_without_progress} циклов ≥ {self._web_search_threshold_cycles} или {self._files_without_high_confidence} файлов ≥ {self._web_search_threshold_files})")
                
            except asyncio.CancelledError:
                logger.info("🛑 AutonomousImprover: цикл отменён")
                break
            except Exception as e:
                logger.error(f"❌ AutonomousImprover ошибка в цикле: {e}", exc_info=True)
            finally:
                # Периодическая очистка старой истории (каждые 10 циклов)
                if self._cycles_without_progress % 10 == 0:
                    self._confidence_accumulator.clear_old_history(max_age_days=30)
                # Обновляем список моделей на случай, если появились новые
                try:
                    self._refresh_available_models()
                except Exception as refresh_error:
                    logger.warning(f"⚠️ Не удалось обновить список моделей: {refresh_error}")
                
                # Ждём минуту перед повтором, но проверяем флаг _running
                try:
                    await asyncio.sleep(60)
                except asyncio.CancelledError:
                    break
    
    def _should_analyze(self) -> bool:
        """Проверяет, стоит ли анализировать сейчас.
        
        Можно добавить проверку:
        - Загрузки CPU
        - Активных задач
        - Доступности LLM
        """
        # Пока всегда возвращаем True
        # В будущем можно добавить проверку нагрузки системы
        return True
    
    async def analyze_project_async(self) -> ProjectAnalysis:
        """Асинхронно анализирует проект.
        
        Returns:
            ProjectAnalysis с результатами
        """
        start_time = time.time()
        logger.info(f"📊 [ЦИКЛ] Начало анализа проекта: {self.project_path}")
        
        # Используем адаптер для поиска файлов (поддержка разных языков)
        all_files = self.adapter.discover_files(self.project_path)
        logger.info(f"📁 [ЦИКЛ] Найдено файлов в проекте: {len(all_files)}")
        
        # Фильтруем через профиль
        files_to_analyze = [
            f for f in all_files
            if self.profile.should_analyze_file(str(f))
        ]
        
        total_files = len(files_to_analyze)
        logger.info(f"✅ [ЦИКЛ] Файлов подходит для анализа (после фильтрации): {total_files}")
        
        # Выбираем файлы для анализа с умной логикой повторного анализа
        # Стратегия:
        # 1. Новые файлы (не анализировались)
        # 2. Файлы с предложениями - повторно через 7 дней
        # 3. Файлы без предложений - повторно через 24 часа (возможно код улучшился)
        # 4. Исключаем тестовые файлы и скрипты
        
        current_time = time.time()
        REANALYZE_WITH_SUGGESTIONS_HOURS = 7 * 24  # 7 дней
        REANALYZE_WITHOUT_SUGGESTIONS_HOURS = 24   # 24 часа
        
        candidate_files = []
        
        for f in files_to_analyze:
            file_str = str(f)
            
            # Если файл не анализировался - добавляем
            if file_str not in self._file_statuses:
                candidate_files.append(f)
            else:
                # Проверяем статус файла для умного повторного анализа
                last_analysis_time, had_suggestions, max_confidence = self._file_statuses[file_str]
                hours_since_analysis = (current_time - last_analysis_time) / 3600
                
                # Повторно анализируем если:
                # - Файл с предложениями и прошло > 7 дней
                # - Файл без предложений и прошло > 24 часа
                # - Или файл изменился (кэш по хешу это проверит)
                should_reanalyze = False
                if had_suggestions and hours_since_analysis >= REANALYZE_WITH_SUGGESTIONS_HOURS:
                    should_reanalyze = True
                    logger.debug(f"🔄 {f.name}: повторный анализ (были предложения, прошло {hours_since_analysis:.1f}ч)")
                elif not had_suggestions and hours_since_analysis >= REANALYZE_WITHOUT_SUGGESTIONS_HOURS:
                    should_reanalyze = True
                    logger.debug(f"🔄 {f.name}: повторный анализ (не было предложений, прошло {hours_since_analysis:.1f}ч)")
                
                if should_reanalyze:
                    candidate_files.append(f)
        
        # Если после фильтрации не осталось файлов, берём любые (включая уже проанализированные)
        # Это позволяет повторно анализировать файлы, которые могли измениться
        # Кэш по хешу файла автоматически пропустит неизменённые файлы
        if not candidate_files:
            candidate_files = [
                f for f in files_to_analyze
                if "test_" not in f.name.lower() and "scripts" not in str(f)
            ]
            
            # Если после фильтрации по времени не осталось файлов,
            # берём файлы, которые можно проанализировать повторно (старые статусы)
            if not candidate_files:
                # Ищем файлы, которые можно проанализировать повторно
                for f in files_to_analyze:
                    file_str = str(f)
                    if not self.profile.should_analyze_file(file_str):
                        continue
                    
                    if file_str in self._file_statuses:
                        last_analysis_time, _, _ = self._file_statuses[file_str]
                        hours_since = (current_time - last_analysis_time) / 3600
                        # Берём файлы, которые анализировались более 12 часов назад
                        if hours_since >= 12:
                            candidate_files.append(f)
                    elif file_str not in self._file_statuses:
                        candidate_files.append(f)
        
        # Приоритизируем файлы по потенциалу улучшений
        prioritized_files = self._prioritize_files(candidate_files)
        files_to_analyze = prioritized_files[:self.max_files_per_cycle]
        
        logger.info(f"🎯 [ЦИКЛ] Кандидатов для анализа: {len(candidate_files)}")
        logger.info(f"📋 [ЦИКЛ] Файлов выбрано для анализа (лимит {self.max_files_per_cycle}): {len(files_to_analyze)}")
        if files_to_analyze:
            logger.info(f"📝 [ЦИКЛ] Файлы для анализа: {', '.join(f.name for f in files_to_analyze[:5])}{'...' if len(files_to_analyze) > 5 else ''}")
        
        if not files_to_analyze:
            logger.info("ℹ️ [ЦИКЛ] Все файлы уже проанализированы, пропускаю цикл")
            return ProjectAnalysis(
                analyzed_files=0,
                total_files=total_files,
                suggestions=[],
                metrics={},
                timestamp=datetime.now()
            )
        
        suggestions: List[ImprovementSuggestion] = []
        
        # Адаптируемся к доступным ресурсам
        resource_config = self._adapt_to_resources()
        max_parallel = resource_config["max_parallel"]
        use_multiple_models = resource_config["use_multiple_models"]
        
        logger.info(f"⚙️ [ЦИКЛ] Конфигурация ресурсов: параллелизм={max_parallel}, множественные модели={'да' if use_multiple_models else 'нет'}, доступно моделей={resource_config['available_models']}")
        
        # Параллельный анализ файлов с ограничением параллелизма
        files_batches = [
            files_to_analyze[i:i + max_parallel]
            for i in range(0, len(files_to_analyze), max_parallel)
        ]
        
        logger.info(f"🔄 [ЦИКЛ] Батчей для анализа: {len(files_batches)} (по {max_parallel} файлов)")
        
        for batch_idx, batch in enumerate(files_batches, 1):
            logger.info(f"📦 [БАТЧ {batch_idx}/{len(files_batches)}] Анализ {len(batch)} файлов: {', '.join(f.name for f in batch)}")
            
            # Создаём задачи для параллельного анализа с адаптивным выбором моделей
            if use_multiple_models:
                tasks = [self._analyze_file_with_optimal_model_async(f) for f in batch]
                logger.debug(f"🤖 [БАТЧ {batch_idx}] Используется адаптивный выбор моделей")
            else:
                tasks = [self._analyze_file_with_cache_async(f) for f in batch]
                logger.debug(f"🤖 [БАТЧ {batch_idx}] Используется базовая модель: {self.model}")
            
            # Выполняем параллельно с обработкой ошибок
            batch_start = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            batch_time = time.time() - batch_start
            logger.info(f"⏱️ [БАТЧ {batch_idx}] Завершён за {batch_time:.1f}с")
            
            # Обрабатываем результаты
            for file_path, result in zip(batch, results):
                try:
                    if isinstance(result, Exception):
                        logger.error(f"❌ [ФАЙЛ] {file_path.name}: ошибка анализа - {result}")
                        continue
                    
                    file_suggestions = result
                    file_str = str(file_path)
                    current_time = time.time()
                    
                    if file_suggestions:
                        suggestions.extend(file_suggestions)
                        max_confidence = max(s.confidence for s in file_suggestions) if file_suggestions else 0.0
                        avg_confidence = sum(s.confidence for s in file_suggestions) / len(file_suggestions) if file_suggestions else 0.0
                        
                        # Сохраняем статус: время анализа, есть предложения, максимальная уверенность
                        self._file_statuses[file_str] = (current_time, True, max_confidence)
                        self._analyzed_files.add(file_str)
                        
                        # Детальное логирование предложений
                        high_conf = [s for s in file_suggestions if s.confidence >= self.min_confidence]
                        logger.info(f"✅ [ФАЙЛ] {file_path.name}: найдено {len(file_suggestions)} предложений (высокая уверенность: {len(high_conf)}, средняя: {avg_confidence:.2f}, макс: {max_confidence:.2f})")
                        
                        # Логируем топ-3 предложения
                        top_suggestions = sorted(file_suggestions, key=lambda s: s.confidence, reverse=True)[:3]
                        for i, s in enumerate(top_suggestions, 1):
                            logger.info(f"   💡 [{i}] {s.type.value}: {s.description[:80]}... (уверенность: {s.confidence:.2f}, приоритет: {s.priority})")
                    else:
                        # Файл без предложений - сохраняем статус для умного повторного анализа
                        # Повторно анализируем только через 24 часа или если файл изменился
                        self._file_statuses[file_str] = (current_time, False, 0.0)
                        # Не добавляем в _analyzed_files сразу - даём шанс на повторный анализ
                        logger.info(f"ℹ️ [ФАЙЛ] {file_path.name}: предложений не найдено (файл в порядке или требует большего контекста)")
                except Exception as e:
                    logger.error(f"❌ [ФАЙЛ] {file_path.name}: ошибка обработки результатов - {e}", exc_info=True)
        
        # Собираем метрики
        analysis_time = time.time() - start_time
        high_conf_suggestions = [s for s in suggestions if s.confidence >= self.min_confidence]
        metrics = {
            "total_files": total_files,
            "analyzed_files": len(self._analyzed_files),
            "suggestions_count": len(suggestions),
            "high_confidence_count": len(high_conf_suggestions),
            "analysis_time_seconds": analysis_time,
            "errors_count": 0  # Инициализируем для совместимости
        }
        
        logger.info("=" * 80)
        logger.info(f"📊 [ЦИКЛ] ИТОГИ АНАЛИЗА:")
        logger.info(f"   ⏱️ Время: {analysis_time:.1f}с")
        logger.info(f"   📁 Файлов проанализировано: {len(files_to_analyze)}/{total_files}")
        logger.info(f"   💡 Всего предложений: {len(suggestions)}")
        logger.info(f"   ✅ С высокой уверенностью (≥{self.min_confidence}): {len(high_conf_suggestions)}")
        if suggestions:
            avg_conf = sum(s.confidence for s in suggestions) / len(suggestions)
            logger.info(f"   📈 Средняя уверенность: {avg_conf:.2f}")
        logger.info("=" * 80)
        
        return ProjectAnalysis(
            analyzed_files=len(files_to_analyze),
            total_files=total_files,
            suggestions=suggestions,
            metrics=metrics,
            timestamp=datetime.now()
        )
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Вычисляет хеш содержимого файла для кэширования.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            MD5 хеш содержимого файла
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            # Используем SHA256 для более надёжного хеширования
            return hashlib.sha256(content.encode()).hexdigest()
        except Exception as e:
            logger.debug(f"⚠️ Ошибка чтения файла {file_path} для хеширования: {e}")
            # Если не удалось прочитать, используем время модификации
            try:
                mtime = file_path.stat().st_mtime
                return hashlib.sha256(str(mtime).encode()).hexdigest()
            except Exception as e2:
                logger.debug(f"⚠️ Ошибка получения mtime для {file_path}: {e2}")
                return ""
    
    def _prioritize_files(self, files: List[Path]) -> List[Path]:
        """Приоритизирует файлы по потенциалу улучшений.
        
        Критерии приоритизации:
        - Высокая сложность функций (max_complexity > 10)
        - Много функций (> 20)
        - Большой размер (> 500 строк)
        - Отсутствие docstrings
        
        Args:
            files: Список файлов для приоритизации
            
        Returns:
            Отсортированный список файлов (высокий приоритет первым)
        """
        scored_files = []
        
        for file_path in files:
            try:
                # Быстрый структурный анализ через адаптер
                structure = self.adapter.analyze_structure(file_path)
                if not structure:
                    scored_files.append((0, file_path))
                    continue
                
                # Вычисляем score на основе метрик
                score = 0.0
                
                # Высокая сложность - высокий приоритет (используем правила из профиля)
                max_complexity = self.profile.quality_rules.max_function_complexity
                if structure.metrics.max_function_complexity > max_complexity:
                    score += structure.metrics.max_function_complexity * 2
                
                # Много функций - больше возможностей для улучшений
                if len(structure.functions) > 20:
                    score += len(structure.functions) * 0.5
                elif len(structure.functions) > 10:
                    score += len(structure.functions) * 0.3
                
                # Большой размер файла
                if structure.metrics.lines_of_code > 500:
                    score += 10
                elif structure.metrics.lines_of_code > 200:
                    score += 5
                
                # Отсутствие docstrings - возможность улучшения
                functions_without_docs = sum(
                    1 for f in structure.functions if not f.docstring
                )
                if functions_without_docs > 0:
                    score += functions_without_docs * 0.5
                
                # Классы без docstrings
                classes_without_docs = sum(
                    1 for c in structure.classes if not c.docstring
                )
                if classes_without_docs > 0:
                    score += classes_without_docs * 1.0
                
                # Много импортов - может быть сложная зависимость
                if len(structure.imports) > 15:
                    score += 3
                
                scored_files.append((score, file_path))
                
            except Exception as e:
                # При ошибке анализа ставим низкий приоритет
                logger.debug(f"⚠️ Ошибка приоритизации {file_path}: {e}")
                scored_files.append((0, file_path))
        
        # Сортируем по score (высокий первым)
        scored_files.sort(key=lambda x: x[0], reverse=True)
        
        # Логируем топ-5 приоритетных файлов
        if scored_files:
            top_files = scored_files[:5]
            logger.info(f"🎯 Топ приоритетных файлов: {', '.join(f.name for _, f in top_files)}")
        
        return [f for _, f in scored_files]
    
    def _adapt_to_resources(self) -> Dict[str, Any]:
        """Адаптирует стратегию к доступным ресурсам."""
        available_models = len(self._available_models)
        
        # Если много моделей - используем больше параллелизма
        if available_models >= 8:
            max_parallel = min(8, self.max_files_per_cycle)
            use_multiple_models = True
            strategy = "высокая (8+ моделей)"
        elif available_models >= 4:
            max_parallel = min(4, self.max_files_per_cycle)
            use_multiple_models = True
            strategy = "средняя (4-7 моделей)"
        else:
            max_parallel = min(2, self.max_files_per_cycle)
            use_multiple_models = False
            strategy = "низкая (<4 моделей)"
        
        logger.debug(f"⚙️ Адаптация ресурсов: {strategy}, параллелизм={max_parallel}, множественные модели={'да' if use_multiple_models else 'нет'}")
        
        return {
            "max_parallel": max_parallel,
            "use_multiple_models": use_multiple_models,
            "available_models": available_models
        }
    
    def _determine_file_complexity(self, file_path: Path, structure) -> "TaskComplexity":
        """Определяет сложность файла для выбора модели."""
        from utils.model_checker import TaskComplexity
        
        if not structure:
            return TaskComplexity.SIMPLE
        
        # Критерии сложности
        lines = getattr(structure.metrics, 'lines_of_code', 0) if hasattr(structure, 'metrics') else 0
        max_complexity = getattr(structure.metrics, 'max_function_complexity', 0) if hasattr(structure, 'metrics') else 0
        num_functions = len(getattr(structure, 'functions', []))
        num_classes = len(getattr(structure, 'classes', []))
        num_imports = len(getattr(structure, 'imports', []))
        
        # Очень сложный файл
        if lines > 1000 or max_complexity > 15 or (num_functions > 30 and num_classes > 10):
            return TaskComplexity.COMPLEX
        
        # Средний файл
        if lines > 500 or max_complexity > 10 or num_functions > 20 or num_imports > 15:
            return TaskComplexity.MEDIUM
        
        # Простой файл
        return TaskComplexity.SIMPLE
    
    async def _analyze_file_with_optimal_model_async(self, file_path: Path) -> List[ImprovementSuggestion]:
        """Анализирует файл с оптимальной моделью на основе сложности."""
        # Проверяем кэш
        file_hash = self._get_file_hash(file_path)
        if file_hash:
            cache_key = f"improver_analysis:{str(file_path)}:{file_hash}"
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"💾 Использован кэш для {file_path}")
                return cached_result
        
        # Быстрый структурный анализ для определения сложности
        logger.debug(f"🔍 [ФАЙЛ] {file_path.name}: структурный анализ...")
        structure = self.adapter.analyze_structure(file_path)
        complexity = self._determine_file_complexity(file_path, structure)
        
        # Логируем метрики файла
        if structure and hasattr(structure, 'metrics'):
            lines = getattr(structure.metrics, 'lines_of_code', 0)
            functions = len(getattr(structure, 'functions', []))
            classes = len(getattr(structure, 'classes', []))
            max_complexity = getattr(structure.metrics, 'max_function_complexity', 0)
            logger.info(f"📏 [ФАЙЛ] {file_path.name}: {lines} строк, {functions} функций, {classes} классов, макс. сложность={max_complexity}")
        
        # Выбираем оптимальную модель через SmartModelRouter
        try:
            selection = self.model_router.select_model_for_complexity(
                complexity=complexity,
                task_type="code_analysis"
            )
            optimal_model = selection.model
            logger.info(f"🤖 [ФАЙЛ] {file_path.name}: сложность={complexity.value} → модель={optimal_model} (причина: {selection.reason if hasattr(selection, 'reason') else 'оптимальный выбор'})")
        except Exception as e:
            logger.warning(f"⚠️ [ФАЙЛ] {file_path.name}: ошибка выбора модели ({e}), используем базовую: {self.model}")
            optimal_model = self.model
        
        # Создаём LLM с оптимальной моделью
        optimal_llm = LocalLLM(
            model=optimal_model,
            temperature=0.2,
            top_p=0.9,
            timeout=60,
            max_retries=1
        )
        
        # Анализируем файл с оптимальной моделью
        logger.info(f"🚀 [ФАЙЛ] {file_path.name}: запуск анализа с моделью {optimal_model}...")
        analysis_start = time.time()
        suggestions = await self._analyze_file_with_llm_async(file_path, optimal_llm, structure)
        analysis_time = time.time() - analysis_start
        
        logger.info(f"⏱️ [ФАЙЛ] {file_path.name}: анализ завершён за {analysis_time:.1f}с, найдено {len(suggestions)} предложений")
        
        # Сохраняем в кэш
        if file_hash:
            cache_key = f"improver_analysis:{str(file_path)}:{file_hash}"
            self._cache.set(cache_key, suggestions, ttl=86400)  # 24 часа
            logger.debug(f"💾 [ФАЙЛ] {file_path.name}: результаты сохранены в кэш")
        
        return suggestions
    
    async def _analyze_file_with_cache_async(self, file_path: Path) -> List[ImprovementSuggestion]:
        """Анализирует файл с использованием кэша.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Список предложений по улучшению
        """
        # Проверяем кэш
        file_hash = self._get_file_hash(file_path)
        if file_hash:
            cache_key = f"improver_analysis:{str(file_path)}:{file_hash}"
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"💾 Использован кэш для {file_path}")
                return cached_result
        
        # Быстрый структурный анализ для определения сложности
        logger.debug(f"🔍 [ФАЙЛ] {file_path.name}: структурный анализ...")
        structure = self.adapter.analyze_structure(file_path)
        
        # Анализируем файл с базовым LLM
        suggestions = await self._analyze_file_with_llm_async(file_path, self.llm, structure)
        
        # Сохраняем в кэш
        if file_hash:
            cache_key = f"improver_analysis:{str(file_path)}:{file_hash}"
            self._cache.set(cache_key, suggestions, ttl=86400)  # 24 часа
        
        return suggestions
    
    async def _analyze_file_with_llm_async(
        self, 
        file_path: Path, 
        llm: "LocalLLM", 
        structure: Any
    ) -> List[ImprovementSuggestion]:
        """Анализирует файл с указанным LLM.
        
        Args:
            file_path: Путь к файлу
            llm: LLM для анализа
            structure: Структура файла (уже проанализирована)
            
        Returns:
            Список предложений по улучшению
        """
        try:
            code = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось прочитать {file_path}: {e}", exc_info=True)
            return []
        
        # Структура уже передана, используем её
        # Продолжаем с остальной логикой анализа
        
        # Формируем контекст для LLM через адаптер
        context = self.adapter.build_context(file_path, structure)
        
        # Определяем, нужен ли веб-поиск
        use_web_search = (
            self._enable_web_search and
            (self._cycles_without_progress >= self._web_search_threshold_cycles or
             self._files_without_high_confidence >= self._web_search_threshold_files)
        )
        
        # Выполняем веб-поиск если нужно
        web_search_results = []
        if use_web_search:
            try:
                # Формируем запрос для поиска через адаптер
                search_query = self.adapter.build_search_query(file_path, structure)
                
                # Проверяем, стоит ли выполнять поиск
                if not self._should_search_web(search_query):
                    web_search_results = []
                else:
                    # Проверяем rate limit
                    await self._web_search_rate_limiter.wait_if_needed()
                    
                    if not self._web_search_rate_limiter.can_make_request():
                        logger.debug("⏳ Веб-поиск: rate limit, пропускаю")
                        web_search_results = []
                    else:
                        logger.info(f"🔍 Веб-поиск: {search_query}")
                        
                        # Записываем запрос
                        self._web_search_rate_limiter.record_request()
                        
                        # Используем Tavily (приоритет) или fallback
                        web_search_results = await asyncio.to_thread(
                            tavily_search,
                            search_query,
                            max_results=5,
                            timeout=10
                        )
                        
                        # Если Tavily не сработал, пробуем общий web_search
                        if not web_search_results:
                            web_search_results = await asyncio.to_thread(
                                web_search,
                                search_query,
                                max_results=5,
                                timeout=10
                            )
                    
                    # Кэшируем результат поиска
                    if web_search_results:
                        # Используем SHA256 для более надёжного хеширования
                        query_hash = hashlib.sha256(search_query.encode()).hexdigest()
                        cache_key = f"web_search_result:{query_hash}"
                        self._cache.set(cache_key, web_search_results, ttl=3600)  # 1 час
                        logger.info(f"✅ Найдено {len(web_search_results)} результатов веб-поиска")
                    else:
                        logger.warning("⚠️ Веб-поиск не вернул результатов")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка веб-поиска: {e}", exc_info=True)
                web_search_results = []
        
        # Формируем промпт с веб-результатами если есть
        web_context = ""
        if web_search_results:
            web_context = "\n\n## Лучшие практики из интернета:\n\n"
            for i, result in enumerate(web_search_results[:3], 1):
                web_context += f"{i}. **{result.get('title', 'Результат')}**\n"
                web_context += f"   {result.get('snippet', '')[:300]}\n"
                if result.get('url'):
                    web_context += f"   Источник: {result.get('url')}\n"
                web_context += "\n"
        
        # Умная выборка кода через адаптер
        code_sample = self.adapter.extract_code_sample(file_path, structure, max_chars=5000)
        
        # Используем универсальный PromptBuilder
        from .prompt_builder import PromptBuilder
        prompt = PromptBuilder.build(
            adapter=self.adapter,
            profile=self.profile,
            context=context,
            code_sample=code_sample,
            web_context=web_context,
            file_path=file_path
        )
        
        # Логируем размер промпта для диагностики
        prompt_size = len(prompt)
        logger.debug(f"📏 Размер промпта для {file_path.name}: {prompt_size} символов")
        
        max_retries = len(self._available_models)  # Пробуем все доступные модели
        last_error = None
        initial_model = self.model
        
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    llm.generate,
                    prompt,
                    num_predict=1024  # Ограничиваем длину ответа
                )
                
                # Проверяем, что ответ не пустой
                if not response or not response.strip():
                    logger.warning(f"⚠️ Пустой ответ от LLM для {file_path} (модель: {llm.model})")
                    # Обрабатываем как ошибку и пробуем другую модель
                    raise ValueError("Пустой ответ от LLM")
                
                # Логируем первые 200 символов ответа для диагностики (только при ошибках парсинга)
                response_preview = response[:200] if len(response) > 200 else response
                logger.debug(f"📝 Ответ LLM для {file_path.name}: {response_preview}...")
                
                # Парсим JSON ответ
                suggestions = self._parse_suggestions(response, str(file_path))
                
                # Если парсинг не вернул предложений, но ответ не пустой - это проблема
                if not suggestions and response.strip():
                    logger.warning(f"⚠️ Не удалось извлечь предложения из ответа LLM для {file_path} (модель: {llm.model}, длина ответа: {len(response)} символов)")
                    # Логируем полный ответ для диагностики (ограниченный размер)
                    logger.debug(f"📄 Полный ответ LLM (первые 500 символов): {response[:500]}")
                    # Обрабатываем как ошибку парсинга и пробуем другую модель
                    raise ValueError(f"Не удалось распарсить ответ LLM (длина: {len(response)} символов)")
                
                # Используем ConfidenceAccumulator для накопления уверенности
                enhanced_suggestions = []
                for s in suggestions:
                    # Базовый confidence от LLM
                    base_confidence = s.confidence
                    
                    # Проверяем структурное подтверждение (AST для Python, структура для фронтенда)
                    structure_confirmed = False
                    if structure:
                        # Для Python используем AST метрики
                        if hasattr(structure, 'metrics') and hasattr(structure.metrics, 'max_function_complexity'):
                            # Это Python AST
                            if structure.metrics.max_function_complexity > 10 and "complexity" in s.description.lower():
                                structure_confirmed = True
                            if not any(f.docstring for f in structure.functions) and "documentation" in s.type.value:
                                structure_confirmed = True
                        # Для фронтенда используем структуру
                        elif hasattr(structure, 'accessibility_issues') and structure.accessibility_issues:
                            if "accessibility" in s.description.lower() or "a11y" in s.description.lower():
                                structure_confirmed = True
                        elif hasattr(structure, 'has_types') and not structure.has_types:
                            if "type" in s.description.lower() or "typescript" in s.description.lower():
                                structure_confirmed = True
                    
                    # Проверяем веб-подтверждение (если использовался веб-поиск)
                    web_confirmed = bool(web_search_results)
                    
                    # Обновляем аккумулятор и получаем effective_confidence
                    effective_confidence = self._confidence_accumulator.update(
                        file_path=str(file_path),
                        description=s.description,
                        suggestion=s.suggestion,
                        base_confidence=base_confidence,
                        file_content=code,
                        ast_confirmed=structure_confirmed,
                        web_confirmed=web_confirmed
                    )
                    
                    # Создаём улучшенное предложение с effective_confidence
                    enhanced_suggestion = ImprovementSuggestion(
                        type=s.type,
                        file_path=s.file_path,
                        description=s.description,
                        suggestion=s.suggestion,
                        confidence=effective_confidence,  # Используем effective вместо base
                        priority=s.priority,
                        reasoning=f"{s.reasoning} [effective: {effective_confidence:.2f}, base: {base_confidence:.2f}]",
                        estimated_impact=s.estimated_impact,
                        code_example=s.code_example,
                        metadata={
                            **s.metadata,
                            "base_confidence": base_confidence,
                            "effective_confidence": effective_confidence,
                            "structure_confirmed": structure_confirmed,
                            "web_confirmed": web_confirmed
                        }
                    )
                    enhanced_suggestions.append(enhanced_suggestion)
                
                # Фильтруем по минимальной уверенности (теперь с effective_confidence)
                filtered = [
                    s for s in enhanced_suggestions
                    if s.confidence >= self.min_confidence
                ]
                
                if attempt > 0:
                    logger.info(f"✅ Успешный анализ {file_path} с моделью {self.model} (попытка {attempt + 1})")
                
                return filtered
                
            except LLMTimeoutError as e:
                last_error = e
                logger.warning(f"⚠️ Таймаут LLM для {file_path} (модель: {self.model}, попытка {attempt + 1}/{max_retries})")
                
                # Пробуем переключиться на следующую модель
                if attempt < max_retries - 1:
                    if self._switch_to_next_model():
                        logger.info(f"🔄 Повторная попытка с моделью {self.model} после таймаута")
                        continue
                    else:
                        break  # Больше нет моделей для переключения
                        
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                # Определяем тип ошибки для лучшего логирования
                if "Пустой ответ" in error_msg or "empty" in error_msg.lower():
                    logger.warning(f"⚠️ Пустой ответ от LLM для {file_path} (модель: {self.model}, попытка {attempt + 1}/{max_retries})")
                elif "timeout" in error_msg.lower() or "таймаут" in error_msg.lower():
                    logger.warning(f"⚠️ Таймаут LLM для {file_path} (модель: {self.model}, попытка {attempt + 1}/{max_retries})")
                elif "Не удалось распарсить" in error_msg:
                    logger.warning(f"⚠️ Ошибка парсинга ответа LLM для {file_path} (модель: {self.model}, попытка {attempt + 1}/{max_retries})")
                else:
                    logger.warning(f"⚠️ Ошибка анализа {file_path} с моделью {self.model}: {e}")
                
                # Пробуем переключиться на следующую модель
                if attempt < max_retries - 1:
                    if self._switch_to_next_model():
                        logger.info(f"🔄 Повторная попытка с моделью {self.model}")
                        continue
                    else:
                        break  # Больше нет моделей для переключения
                else:
                    # Последняя попытка - обновляем список моделей и пробуем ещё раз
                    try:
                        self._refresh_available_models()
                        if self._available_models and self._available_models[0] != self.model:
                            self._current_model_index = 0
                            self.model = self._available_models[0]
                            self.llm = LocalLLM(
                                model=self.model,
                                temperature=0.2,
                                top_p=0.9,
                                timeout=60,  # 60 секунд на анализ
                                max_retries=1
                            )
                            logger.info(f"🔄 Обновлён список моделей, пробую {self.model}")
                            continue
                    except Exception as refresh_error:
                        logger.error(f"❌ Ошибка обновления списка моделей: {refresh_error}")
        
        # Все попытки исчерпаны
        logger.error(f"❌ Не удалось проанализировать {file_path} ни с одной моделью. Последняя ошибка: {last_error}")
        
        # Возвращаемся к исходной модели для следующего файла
        if self.model != initial_model:
            try:
                if initial_model in self._available_models:
                    self._current_model_index = self._available_models.index(initial_model)
                    self.model = initial_model
                    self.llm = LocalLLM(
                        model=self.model,
                        temperature=0.2,
                        top_p=0.9,
                        timeout=60,  # 60 секунд на анализ
                        max_retries=1
                    )
            except Exception as e:
                logger.debug(f"⚠️ Ошибка возврата к исходной модели {initial_model}: {e}")
                # Игнорируем ошибки при возврате
        
        return []
    
    def _build_analysis_context(
        self,
        code: str,
        ast_analysis: Optional[FileAnalysis],
        file_path: Path
    ) -> str:
        """Формирует контекст для анализа."""
        context_parts = [
            f"Файл: {file_path}",
            f"Размер: {len(code)} символов, {len(code.splitlines())} строк"
        ]
        
        if ast_analysis:
            context_parts.extend([
                f"Функций: {len(ast_analysis.functions)}",
                f"Классов: {len(ast_analysis.classes)}",
                f"Импортов: {len(ast_analysis.imports)}",
                f"Сложность: средняя {ast_analysis.metrics.avg_function_complexity:.1f}, макс {ast_analysis.metrics.max_function_complexity}"
            ])
        
        return "\n".join(context_parts)
    
    def _get_or_analyze_ast(self, file_path: Path) -> Optional[FileAnalysis]:
        """Получает AST анализ из кэша или выполняет новый.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            FileAnalysis или None
        """
        cache_key = f"ast_analysis:{str(file_path)}"
        
        # Проверяем кэш
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        # Выполняем анализ
        analysis = self.ast_analyzer.analyze_file(file_path)
        
        # Сохраняем в кэш (1 час)
        if analysis:
            self._cache.set(cache_key, analysis, ttl=3600)
        
        return analysis
    
    def _extract_code_sample(
        self,
        code: str,
        ast_analysis: Optional[FileAnalysis],
        max_chars: int = 5000
    ) -> str:
        """Извлекает важные участки кода для анализа.
        
        Args:
            code: Полный код файла
            ast_analysis: AST анализ файла
            max_chars: Максимальная длина выборки
            
        Returns:
            Выборка кода для анализа
        """
        if len(code) <= max_chars:
            return code
        
        lines = code.splitlines()
        if len(lines) <= 100:
            # Небольшой файл - берём весь
            return code[:max_chars]
        
        # Для больших файлов берём начало, конец и сложные функции
        important_lines = []
        
        # Начало файла (импорты, константы, классы)
        important_lines.extend(lines[:30])
        
        # Сложные функции из AST анализа
        if ast_analysis:
            for func in ast_analysis.functions:
                if func.complexity > 10:  # Высокая сложность
                    func_lines = lines[func.lineno - 1:func.end_lineno]
                    important_lines.extend(func_lines)
        
        # Конец файла (основная логика)
        important_lines.extend(lines[-30:])
        
        # Объединяем и ограничиваем размер
        sample = "\n".join(important_lines)
        if len(sample) > max_chars:
            sample = sample[:max_chars] + "\n# ... (код обрезан для анализа) ..."
        
        return sample
    
    def _validate_suggestion(self, suggestion: ImprovementSuggestion) -> bool:
        """Проверяет предложение на валидность и уникальность.
        
        Args:
            suggestion: Предложение для валидации
            
        Returns:
            True если предложение валидно и уникально
        """
        # Проверка на минимальную длину описания
        if len(suggestion.description) < 20:
            return False
        
        # Проверка на наличие конкретного предложения
        if len(suggestion.suggestion) < 30:
            return False
        
        # Проверка на дубликаты
        # Используем SHA256 для более надёжного хеширования
        suggestion_hash = hashlib.sha256(
            f"{suggestion.file_path}:{suggestion.description}:{suggestion.type.value}".encode()
        ).hexdigest()
        
        if suggestion_hash in self._suggestion_hashes:
            return False
        
        self._suggestion_hashes.add(suggestion_hash)
        return True
    
    def _add_suggestions(self, suggestions: List[ImprovementSuggestion]) -> None:
        """Добавляет предложения с ограничением по количеству (rotation).
        
        Args:
            suggestions: Список предложений для добавления
        """
        self._suggestions.extend(suggestions)
        
        # Ограничиваем количество хранимых предложений
        if len(self._suggestions) > self._max_stored_suggestions:
            # Сортируем по приоритету и уверенности, оставляем лучшие
            self._suggestions.sort(key=lambda x: (x.priority, x.confidence), reverse=True)
            self._suggestions = self._suggestions[:self._max_stored_suggestions]
            
            # Обновляем хеши для оставшихся предложений
            self._suggestion_hashes.clear()
            for s in self._suggestions:
                # Используем SHA256 для более надёжного хеширования
                suggestion_hash = hashlib.sha256(
                    f"{s.file_path}:{s.description}:{s.type.value}".encode()
                ).hexdigest()
                self._suggestion_hashes.add(suggestion_hash)
    
    def _should_search_web(self, query: str) -> bool:
        """Определяет, стоит ли выполнять веб-поиск для данного запроса.
        
        Args:
            query: Поисковый запрос
            
        Returns:
            True если стоит выполнять поиск
        """
        # Исключить слишком общие запросы
        generic_terms = {"python", "code", "best", "practice", "quality", "improve"}
        query_terms = set(query.lower().split())
        
        if len(query_terms - generic_terms) < 2:
            logger.debug(f"🔍 Пропущен веб-поиск: слишком общий запрос '{query}'")
            return False
        
        # Проверяем кэш похожих запросов
        # Используем SHA256 для более надёжного хеширования
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        cache_key = f"web_search_result:{query_hash}"
        
        if self._cache.get(cache_key) is not None:
            logger.debug(f"🔍 Пропущен веб-поиск: результат уже в кэше для '{query}'")
            return False
        
        return True
    
    def _build_search_query(
        self,
        code: str,
        ast_analysis: Optional[FileAnalysis],
        file_path: Path
    ) -> str:
        """Формирует поисковый запрос для веб-поиска лучших практик.
        
        Args:
            code: Код файла
            ast_analysis: AST анализ файла
            file_path: Путь к файлу
            
        Returns:
            Поисковый запрос
        """
        # Определяем тип файла и основные паттерны
        query_parts = []
        
        # Добавляем контекст из имени файла
        file_name = file_path.stem.lower()
        if "agent" in file_name:
            query_parts.append("python agent best practices")
        elif "api" in file_name or "router" in file_name:
            query_parts.append("python fastapi best practices")
        elif "model" in file_name:
            query_parts.append("python data models best practices")
        elif "test" in file_name:
            query_parts.append("python testing best practices")
        else:
            query_parts.append("python code quality best practices")
        
        # Добавляем информацию из AST анализа
        if ast_analysis:
            if len(ast_analysis.functions) > 10:
                query_parts.append("refactoring large functions")
            max_complexity = self.profile.quality_rules.max_function_complexity
            if ast_analysis.metrics.max_function_complexity > max_complexity:
                query_parts.append("reducing code complexity")
            if len(ast_analysis.classes) > 5:
                query_parts.append("python class design patterns")
        
        # Формируем финальный запрос
        query = " ".join(query_parts[:3])  # Максимум 3 части
        return query
    
    def _parse_suggestions(self, response: str, file_path: str) -> List[ImprovementSuggestion]:
        """Парсит предложения из ответа LLM с улучшенной обработкой ошибок."""
        from infrastructure.autonomous_improver.utils.json_parser import (
            parse_llm_json_response,
            extract_suggestions_with_fallback
        )
        
        suggestions = []
        
        try:
            # Шаг 1: Пробуем нормальный парсинг через улучшенный парсер
            parsed = parse_llm_json_response(response)
            
            if parsed and 'suggestions' in parsed:
                data = parsed
            else:
                # Шаг 2: Fallback на regex парсинг если нормальный не сработал
                logger.debug("⚠️ Нормальный JSON парсинг не удался, используем fallback")
                fallback_suggestions = extract_suggestions_with_fallback(response)
                if fallback_suggestions:
                    # Создаём структуру как ожидается
                    data = {"suggestions": fallback_suggestions}
                else:
                    logger.warning(f"⚠️ Не удалось извлечь предложения из ответа LLM для {file_path}")
                    return suggestions
            
            for item in data.get("suggestions", []):
                try:
                    # Обрабатываем тип (может быть множественным через |)
                    type_str = item.get("type", "code_quality")
                    if "|" in type_str:
                        # Берём первый тип из списка
                        type_str = type_str.split("|")[0].strip()
                        logger.debug(f"🔀 Множественный тип '{item.get('type')}' → '{type_str}'")
                    
                    # Пробуем найти соответствующий тип
                    try:
                        improvement_type = ImprovementType(type_str)
                    except ValueError:
                        # Если тип не найден, пробуем найти похожий (fuzzy matching)
                        type_lower = type_str.lower()
                        if "security" in type_lower:
                            improvement_type = ImprovementType.SECURITY
                        elif "performance" in type_lower:
                            improvement_type = ImprovementType.PERFORMANCE
                        elif "documentation" in type_lower or "docstring" in type_lower:
                            improvement_type = ImprovementType.DOCUMENTATION
                        elif "refactor" in type_lower:
                            improvement_type = ImprovementType.REFACTORING
                        elif "architecture" in type_lower:
                            improvement_type = ImprovementType.ARCHITECTURE
                        elif "accessibility" in type_lower or "a11y" in type_lower:
                            improvement_type = ImprovementType.ACCESSIBILITY
                        elif "ux" in type_lower or "user experience" in type_lower:
                            improvement_type = ImprovementType.UX
                        elif "type" in type_lower and ("typescript" in type_lower or "typing" in type_lower):
                            improvement_type = ImprovementType.TYPES
                        elif "component" in type_lower:
                            improvement_type = ImprovementType.COMPONENT_DESIGN
                        else:
                            improvement_type = ImprovementType.CODE_QUALITY
                        logger.debug(f"🔀 Неизвестный тип '{type_str}' → '{improvement_type.value}'")
                    
                    suggestion = ImprovementSuggestion(
                        type=improvement_type,
                        file_path=item.get("file_path", file_path),
                        description=item.get("description", ""),
                        suggestion=item.get("suggestion", ""),
                        confidence=float(item.get("confidence", 0.0)),
                        priority=int(item.get("priority", 5)),
                        reasoning=item.get("reasoning", ""),
                        estimated_impact=item.get("estimated_impact", "medium"),
                        code_example=item.get("code_example"),
                        metadata=item.get("metadata", {})
                    )
                    
                    # Валидация через адаптер
                    if self.adapter.validate_suggestion(suggestion):
                        suggestions.append(suggestion)
                    else:
                        logger.debug(f"⚠️ Предложение не прошло валидацию: {suggestion.description[:50]}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка парсинга предложения: {e}")
                    continue
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Ошибка парсинга JSON: {e}")
            # Пробуем fallback парсинг при JSONDecodeError
            try:
                from infrastructure.autonomous_improver.utils.json_parser import (
                    extract_suggestions_with_fallback
                )
                fallback_suggestions = extract_suggestions_with_fallback(response)
                if fallback_suggestions:
                    logger.info(f"✅ Fallback парсинг успешно извлёк {len(fallback_suggestions)} предложений")
                    # Обрабатываем fallback предложения
                    data = {"suggestions": fallback_suggestions}
                    # Продолжаем обработку как обычно (код выше уже обработает data)
            except Exception as fallback_error:
                logger.debug(f"⚠️ Fallback парсинг тоже не удался: {fallback_error}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка парсинга предложений: {e}")
        
        # Накопление статистики ошибок парсинга (для мониторинга)
        if not suggestions:
            # Увеличиваем счётчик ошибок парсинга (если есть такой механизм)
            # Это можно использовать для мониторинга качества LLM ответов
            pass
        
        return suggestions
    
    def get_suggestions(self, min_confidence: Optional[float] = None) -> List[ImprovementSuggestion]:
        """Возвращает накопленные предложения.
        
        Args:
            min_confidence: Минимальная уверенность (None = использовать self.min_confidence)
            
        Returns:
            Список предложений
        """
        threshold = min_confidence if min_confidence is not None else self.min_confidence
        return [s for s in self._suggestions if s.confidence >= threshold]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Возвращает метрики эффективности работы модуля.
        
        Returns:
            Словарь с метриками
        """
        if not self._suggestions:
            avg_confidence = 0.0
        else:
            avg_confidence = sum(s.confidence for s in self._suggestions) / len(self._suggestions)
        
        # Распределение по типам
        type_distribution = {}
        for suggestion_type in ImprovementType:
            count = len([s for s in self._suggestions if s.type == suggestion_type])
            if count > 0:
                type_distribution[suggestion_type.value] = count
        
        # Распределение по приоритетам
        priority_distribution = {}
        for priority in range(1, 11):
            count = len([s for s in self._suggestions if s.priority == priority])
            if count > 0:
                priority_distribution[priority] = count
        
        return {
            "total_files_analyzed": len(self._analyzed_files),
            "total_suggestions": len(self._suggestions),
            "high_confidence_suggestions": len([s for s in self._suggestions if s.confidence >= self.min_confidence]),
            "average_confidence": round(avg_confidence, 3),
            "cycles_without_progress": self._cycles_without_progress,
            "files_without_high_confidence": self._files_without_high_confidence,
            "suggestion_types": type_distribution,
            "priority_distribution": priority_distribution,
            "current_model": self.model,
            "available_models_count": len(self._available_models),
            "files_with_status": len(self._file_statuses),
            "confidence_accumulator_stats": self._confidence_accumulator.get_stats(),
            "web_search_rate_limiter_stats": self._web_search_rate_limiter.get_stats(),
        }
    
    def clear_suggestions(self) -> None:
        """Очищает накопленные предложения."""
        self._suggestions.clear()
        self._suggestion_hashes.clear()
        logger.info("🗑️ AutonomousImprover: предложения очищены")


# === Singleton и Factory ===

_autonomous_improver: Optional[AutonomousImprover] = None


def get_autonomous_improver() -> AutonomousImprover:
    """Возвращает глобальный экземпляр AutonomousImprover.
    
    Returns:
        AutonomousImprover экземпляр
    """
    global _autonomous_improver
    
    if _autonomous_improver is None:
            config = get_config()
            
            project_path = getattr(config, 'autonomous_improver_project_path', None)
            model = getattr(config, 'autonomous_improver_model', None)
            min_confidence = getattr(config, 'autonomous_improver_min_confidence', 1.0)
            max_files = getattr(config, 'autonomous_improver_max_files_per_cycle', 10)
            cycle_interval = getattr(config, 'autonomous_improver_cycle_interval', 300)
            
            # Профиль и адаптер определяются автоматически в __init__
            _autonomous_improver = AutonomousImprover(
                project_path=project_path,
                model=model,
                min_confidence=min_confidence,
                max_files_per_cycle=max_files,
                cycle_interval_seconds=cycle_interval,
                profile=None,  # Автоматическое определение
                adapter=None  # Автоматический выбор на основе профиля
            )
    
    return _autonomous_improver


def reset_autonomous_improver() -> None:
    """Сбрасывает глобальный экземпляр."""
    global _autonomous_improver
    if _autonomous_improver:
        _autonomous_improver.stop()
    _autonomous_improver = None
