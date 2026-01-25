"""Модуль для быстрых асинхронных консультаций с легкими reasoning моделями.

Решает проблему долгих ответов, предоставляя быстрые советы и подсказки
параллельно с основным workflow, не блокируя выполнение задач.

Особенности:
- Использует легкие reasoning модели (phi3:mini, gemma:2b и т.д.)
- Асинхронная работа - не блокирует основной процесс
- Конфигурируемый через config.toml
- Автоматический выбор оптимальной легкой модели
- Кэширование для типовых вопросов
"""
import asyncio
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json

from infrastructure.local_llm import LocalLLM, create_llm_for_stage, LLMTimeoutError
from utils.model_checker import (
    get_light_model,
    get_all_reasoning_models,
    check_model_available,
    TaskComplexity,
    ModelInfo
)
from utils.config import get_config
from utils.logger import get_logger
from infrastructure.cache import get_cache


logger = get_logger()


class AdvisorPriority(str, Enum):
    """Приоритет консультации."""
    LOW = "low"  # Фоновые советы, не критично
    MEDIUM = "medium"  # Полезные подсказки
    HIGH = "high"  # Важные рекомендации


@dataclass
class AdvisorResponse:
    """Ответ от быстрого консультанта."""
    advice: str  # Текст совета
    confidence: float  # Уверенность (0.0-1.0)
    priority: AdvisorPriority  # Приоритет
    model_used: str  # Использованная модель
    response_time_ms: int  # Время ответа в миллисекундах
    metadata: Dict[str, Any] = field(default_factory=dict)  # Дополнительные данные


@dataclass
class AdvisorRequest:
    """Запрос к быстрому консультанту."""
    query: str  # Вопрос или задача
    context: Optional[str] = None  # Дополнительный контекст
    priority: AdvisorPriority = AdvisorPriority.MEDIUM  # Приоритет
    timeout_seconds: Optional[int] = None  # Таймаут (если None, используется из конфига)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Дополнительные данные


class FastAdvisor:
    """Быстрый консультант на основе легких reasoning моделей.
    
    Предоставляет быстрые советы и подсказки параллельно с основным workflow,
    не блокируя выполнение задач независимо от их сложности.
    """
    
    # Системный промпт для быстрых консультаций
    SYSTEM_PROMPT = """Ты — быстрый консультант-помощник по программированию.

Твоя задача — давать КОРОТКИЕ, ЧЁТКИЕ и ПОЛЕЗНЫЕ советы за минимальное время.

## Правила:
- Отвечай максимально кратко (1-3 предложения)
- Фокусируйся на главном
- Не дублируй очевидное
- Если не уверен — скажи об этом честно
- Используй markdown для форматирования

## Формат ответа:
- Краткий совет
- Ключевая рекомендация (если есть)
- Предупреждение (если нужно)

Примеры:
- "Используй async/await для I/O операций. Это улучшит производительность."
- "Проверь импорты — возможно, модуль не установлен."
- "Для этой задачи лучше использовать словарь вместо списка."

Отвечай на русском языке."""

    def __init__(
        self,
        model: Optional[str] = None,
        timeout_seconds: int = 10,
        enable_cache: bool = True,
        cache_ttl: int = 3600
    ):
        """Инициализация быстрого консультанта.
        
        Args:
            model: Модель Ollama (None = автовыбор легкой модели)
            timeout_seconds: Таймаут для консультации (секунды)
            enable_cache: Включить кэширование ответов
            cache_ttl: Время жизни кэша (секунды)
        """
        self.config = get_config()
        self.timeout_seconds = timeout_seconds
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        
        # Выбираем легкую модель
        if model:
            self.model = model if check_model_available(model) else self._select_light_model()
        else:
            self.model = self._select_light_model()
        
        # Создаём LLM с коротким таймаутом для быстрых ответов
        self.llm = LocalLLM(
            model=self.model,
            temperature=0.3,  # Низкая температура для детерминированных ответов
            top_p=0.9,
            timeout=timeout_seconds,
            max_retries=1  # Не повторяем - быстрые ответы важнее надёжности
        )
        
        # Кэш для типовых вопросов
        self._cache = get_cache() if enable_cache else None
        
        logger.info(f"✅ FastAdvisor инициализирован (модель: {self.model}, timeout: {timeout_seconds}с)")
    
    def _select_light_model(self) -> str:
        """Выбирает оптимальную легкую модель для быстрых консультаций.
        
        Приоритет:
        1. Легкие reasoning модели (phi3:mini, gemma:2b)
        2. Обычные легкие модели (tinyllama, phi3:mini)
        3. Fallback на любую доступную
        
        Returns:
            Название модели
        """
        # Пробуем найти легкую reasoning модель
        reasoning_models = get_all_reasoning_models()
        light_reasoning = [
            m for m in reasoning_models
            if m.size_gb and m.size_gb <= 4.0  # До 4GB
        ]
        
        if light_reasoning:
            # Сортируем по размеру (меньше = быстрее)
            light_reasoning.sort(key=lambda m: m.size_gb or 999)
            selected = light_reasoning[0]
            logger.info(f"🤖 Выбрана легкая reasoning модель: {selected.name} ({selected.size_gb}GB)")
            return selected.name
        
        # Fallback на обычную легкую модель
        light_model = get_light_model()
        if light_model:
            logger.info(f"🤖 Выбрана легкая модель: {light_model}")
            return light_model
        
        # Последний fallback - любая доступная
        from utils.model_checker import get_any_available_model
        any_model = get_any_available_model()
        if any_model:
            logger.warning(f"⚠️ Используется fallback модель: {any_model}")
            return any_model
        
        raise RuntimeError("Нет доступных моделей для FastAdvisor")
    
    def _get_cache_key(self, query: str, context: Optional[str] = None) -> str:
        """Генерирует ключ кэша для запроса.
        
        Args:
            query: Вопрос
            context: Дополнительный контекст
            
        Returns:
            Ключ кэша
        """
        combined = f"{query}:{context or ''}"
        normalized = combined.lower().strip()
        return f"advisor:{hashlib.md5(normalized.encode()).hexdigest()}"
    
    async def consult_async(
        self,
        request: AdvisorRequest,
        callback: Optional[Callable[[AdvisorResponse], Awaitable[None]]] = None
    ) -> Optional[AdvisorResponse]:
        """Асинхронная консультация (не блокирует основной процесс).
        
        Если указан callback, ответ будет передан туда асинхронно.
        Основной процесс не ждёт ответа.
        
        Args:
            request: Запрос на консультацию
            callback: Опциональный callback для получения ответа
            
        Returns:
            AdvisorResponse или None (если используется callback)
        """
        start_time = datetime.now()
        
        # Проверяем кэш
        if self.enable_cache and self._cache:
            cache_key = self._get_cache_key(request.query, request.context)
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug(f"💾 FastAdvisor: ответ из кэша")
                response = AdvisorResponse(
                    advice=cached["advice"],
                    confidence=cached.get("confidence", 0.8),
                    priority=AdvisorPriority(cached.get("priority", "medium")),
                    model_used=self.model,
                    response_time_ms=0,  # Кэш мгновенный
                    metadata=cached.get("metadata", {})
                )
                if callback:
                    await callback(response)
                return response
        
        # Формируем промпт
        prompt = self._build_prompt(request)
        
        try:
            # Быстрый запрос к LLM с коротким таймаутом
            timeout = request.timeout_seconds or self.timeout_seconds
            response_text = await asyncio.to_thread(
                self.llm.generate,
                prompt,
                num_predict=256  # Короткие ответы - максимум 256 токенов
            )
            
            # Парсим ответ
            advice = self._parse_response(response_text)
            confidence = self._estimate_confidence(response_text, request.query)
            
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            response = AdvisorResponse(
                advice=advice,
                confidence=confidence,
                priority=request.priority,
                model_used=self.model,
                response_time_ms=elapsed_ms,
                metadata={
                    "query_length": len(request.query),
                    "context_provided": request.context is not None
                }
            )
            
            # Сохраняем в кэш
            if self.enable_cache and self._cache:
                cache_key = self._get_cache_key(request.query, request.context)
                self._cache.set(cache_key, {
                    "advice": advice,
                    "confidence": confidence,
                    "priority": request.priority.value,
                    "metadata": response.metadata
                }, ttl=self.cache_ttl)
            
            logger.info(f"✅ FastAdvisor: консультация за {elapsed_ms}мс")
            
            if callback:
                await callback(response)
            
            return response
            
        except LLMTimeoutError:
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.warning(f"⏱️ FastAdvisor: таймаут после {elapsed_ms}мс")
            
            # Возвращаем fallback ответ
            fallback = AdvisorResponse(
                advice="Консультация заняла слишком много времени. Рекомендую проверить задачу вручную.",
                confidence=0.3,
                priority=request.priority,
                model_used=self.model,
                response_time_ms=elapsed_ms,
                metadata={"timeout": True}
            )
            
            if callback:
                await callback(fallback)
            
            return fallback
            
        except Exception as e:
            logger.error(f"❌ FastAdvisor ошибка: {e}", error=e)
            
            # Возвращаем fallback ответ
            fallback = AdvisorResponse(
                advice=f"Ошибка консультации: {str(e)[:100]}",
                confidence=0.0,
                priority=request.priority,
                model_used=self.model,
                response_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                metadata={"error": str(e)}
            )
            
            if callback:
                await callback(fallback)
            
            return fallback
    
    def consult_sync(
        self,
        request: AdvisorRequest
    ) -> AdvisorResponse:
        """Синхронная консультация (блокирует до получения ответа).
        
        Используется только если нужен немедленный ответ.
        Для неблокирующих консультаций используйте consult_async().
        
        Args:
            request: Запрос на консультацию
            
        Returns:
            AdvisorResponse
        """
        # Запускаем асинхронную версию в event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если loop уже запущен, создаём новый task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(self.consult_async(request))
                    )
                    return future.result(timeout=request.timeout_seconds or self.timeout_seconds)
            else:
                return loop.run_until_complete(self.consult_async(request))
        except RuntimeError:
            # Нет event loop - создаём новый
            return asyncio.run(self.consult_async(request))
    
    def _build_prompt(self, request: AdvisorRequest) -> str:
        """Формирует промпт для консультации.
        
        Args:
            request: Запрос на консультацию
            
        Returns:
            Промпт для LLM
        """
        parts = [request.query]
        
        if request.context:
            parts.append(f"\n\nКонтекст:\n{request.context}")
        
        return "\n".join(parts)
    
    def _parse_response(self, response: str) -> str:
        """Парсит ответ от LLM, извлекая только полезную информацию.
        
        Args:
            response: Ответ от LLM
            
        Returns:
            Очищенный совет
        """
        # Убираем лишние пробелы и переносы
        cleaned = response.strip()
        
        # Убираем markdown код-блоки если они есть (оставляем только текст)
        if "```" in cleaned:
            lines = cleaned.split("\n")
            result = []
            in_code = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_code = not in_code
                    continue
                if not in_code:
                    result.append(line)
            cleaned = "\n".join(result).strip()
        
        # Ограничиваем длину (максимум 500 символов для быстрых советов)
        if len(cleaned) > 500:
            cleaned = cleaned[:497] + "..."
        
        return cleaned
    
    def _estimate_confidence(self, response: str, query: str) -> float:
        """Оценивает уверенность в ответе на основе эвристик.
        
        Args:
            response: Ответ от LLM
            query: Исходный вопрос
            
        Returns:
            Уверенность (0.0-1.0)
        """
        confidence = 0.7  # Базовая уверенность
        
        # Увеличиваем если ответ конкретный и короткий
        if len(response) < 200:
            confidence += 0.1
        
        # Уменьшаем если есть неопределённые фразы
        uncertain_phrases = [
            "возможно", "может быть", "не уверен", "не знаю",
            "maybe", "perhaps", "not sure", "don't know"
        ]
        if any(phrase in response.lower() for phrase in uncertain_phrases):
            confidence -= 0.2
        
        # Увеличиваем если есть конкретные рекомендации
        if any(word in response.lower() for word in ["используй", "рекомендую", "лучше", "use", "recommend"]):
            confidence += 0.1
        
        return max(0.0, min(1.0, confidence))


# === Singleton и Factory ===

_fast_advisor: Optional[FastAdvisor] = None


def get_fast_advisor() -> FastAdvisor:
    """Возвращает глобальный экземпляр FastAdvisor.
    
    Использует конфигурацию из config.toml.
    
    Returns:
        FastAdvisor экземпляр
    """
    global _fast_advisor
    
    if _fast_advisor is None:
        config = get_config()
        
        # Читаем настройки из конфига
        model = config.fast_advisor_model or None  # Пустая строка -> None
        timeout = config.fast_advisor_timeout
        enable_cache = config.fast_advisor_enable_cache
        cache_ttl = config.fast_advisor_cache_ttl
        
        _fast_advisor = FastAdvisor(
            model=model,
            timeout_seconds=timeout,
            enable_cache=enable_cache,
            cache_ttl=cache_ttl
        )
    
    return _fast_advisor


def reset_fast_advisor() -> None:
    """Сбрасывает глобальный экземпляр FastAdvisor."""
    global _fast_advisor
    _fast_advisor = None
