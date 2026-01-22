"""Модуль для стриминга рассуждений reasoning моделей в UI.

Позволяет отображать <think> блоки в реальном времени, чтобы пользователь:
- Видел ход рассуждений модели
- Мог прервать выполнение, если модель идёт не туда
- Понимал логику принятия решений

Архитектура:
- ReasoningStreamManager — управляет стримингом рассуждений
- SSE события: thinking_start, thinking_chunk, thinking_end
- Интегрируется с LocalLLM через callback

Пример использования:
    ```python
    from infrastructure.reasoning_stream import ReasoningStreamManager
    
    manager = ReasoningStreamManager()
    
    # В LocalLLM или агенте
    async for event in manager.stream_with_reasoning(llm, prompt, stage="coding"):
        yield event  # SSE события для frontend
    ```

См. также:
- infrastructure/reasoning_utils.py — парсинг <think> блоков
- backend/sse_manager.py — базовые SSE события
- future/ROADMAP_2026.md — план развития reasoning моделей
"""
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional, Callable, Any, TYPE_CHECKING
from datetime import datetime
from enum import Enum
import json
import asyncio

if TYPE_CHECKING:
    from infrastructure.local_llm import LocalLLM

from infrastructure.reasoning_utils import (
    parse_reasoning_response,
    ReasoningResponse,
    is_reasoning_response,
    get_thinking_summary
)
from utils.logger import get_logger

logger = get_logger()


class ThinkingStatus(str, Enum):
    """Статус процесса рассуждения."""
    STARTED = "started"      # Начало <think> блока
    IN_PROGRESS = "in_progress"  # Получен новый чанк
    COMPLETED = "completed"  # </think> получен
    INTERRUPTED = "interrupted"  # Прервано пользователем


@dataclass
class ThinkingChunk:
    """Чанк рассуждения для стриминга.
    
    Attributes:
        content: Текст чанка рассуждения
        status: Статус (started, in_progress, completed)
        stage: Этап workflow (intent, planning, coding, etc.)
        elapsed_ms: Время с начала рассуждения в мс
        total_chars: Общее количество символов рассуждения
    """
    content: str
    status: ThinkingStatus
    stage: str
    elapsed_ms: int = 0
    total_chars: int = 0


@dataclass
class ReasoningStreamConfig:
    """Конфигурация стриминга рассуждений.
    
    Attributes:
        enabled: Включён ли стриминг <think> блоков
        chunk_size: Размер чанка для отправки (символов)
        debounce_ms: Задержка между отправками (мс)
        max_thinking_time_ms: Максимальное время рассуждения (мс)
        show_summary_only: Показывать только краткую сводку
    """
    enabled: bool = True
    chunk_size: int = 100
    debounce_ms: int = 50
    max_thinking_time_ms: int = 120_000  # 2 минуты
    show_summary_only: bool = False


class ReasoningStreamManager:
    """Менеджер для стриминга рассуждений reasoning моделей.
    
    Обеспечивает:
    - Real-time стриминг <think> контента по мере генерации
    - SSE события для frontend (thinking_start, thinking_chunk, thinking_end)
    - Возможность прерывания
    - Таймауты и защиту от бесконечных рассуждений
    
    Два режима работы:
    1. Real-time: stream_from_llm() — стримит по мере генерации LLM
    2. Post-hoc: process_response_with_thinking() — обрабатывает готовый ответ
    
    Example (real-time):
        ```python
        manager = get_reasoning_stream_manager()
        
        async for event in manager.stream_from_llm(
            llm=llm,
            prompt=prompt,
            stage="coding"
        ):
            yield event  # SSE события + финальный результат
        ```
    """
    
    def __init__(self, config: Optional[ReasoningStreamConfig] = None) -> None:
        """Инициализация менеджера.
        
        Args:
            config: Конфигурация стриминга (опционально)
        """
        self.config = config or ReasoningStreamConfig()
        self._interrupted = False
        self._current_stage: Optional[str] = None
    
    def interrupt(self) -> None:
        """Прерывает текущий стриминг рассуждений.
        
        Вызывается когда пользователь нажимает "Стоп" в UI.
        """
        self._interrupted = True
        logger.info("⏹️ Стриминг рассуждений прерван пользователем")
    
    def reset(self) -> None:
        """Сбрасывает состояние менеджера."""
        self._interrupted = False
        self._current_stage = None
    
    async def create_thinking_event(
        self,
        chunk: ThinkingChunk
    ) -> str:
        """Создаёт SSE событие для чанка рассуждения.
        
        Args:
            chunk: Данные чанка
            
        Returns:
            SSE событие в формате text/event-stream
            
        Формат события:
        - thinking_started: { stage, total_chars }
        - thinking_in_progress: { stage, content, elapsed_ms, total_chars }
        - thinking_completed: { stage, content, summary, elapsed_ms, total_chars }
        - thinking_interrupted: { stage, content, elapsed_ms, total_chars }
        """
        event_type = f"thinking_{chunk.status.value}"
        
        data = {
            "stage": chunk.stage,
            "content": chunk.content,
            "status": chunk.status.value,
            "elapsed_ms": chunk.elapsed_ms,
            "total_chars": chunk.total_chars,
            "timestamp": datetime.now().isoformat()
        }
        
        # Добавляем summary для completed статуса
        if chunk.status == ThinkingStatus.COMPLETED and chunk.content:
            data["summary"] = get_thinking_summary(chunk.content, max_length=150)
        
        json_data = json.dumps(data, ensure_ascii=False)
        event_id = str(datetime.now().timestamp())
        
        lines = [
            f"id: {event_id}",
            f"event: {event_type}",
            f"data: {json_data}",
            ""
        ]
        
        return "\n".join(lines) + "\n"
    
    async def stream_thinking_content(
        self,
        thinking: str,
        stage: str,
        start_time: datetime
    ) -> AsyncGenerator[str, None]:
        """Стримит контент <think> блока чанками.
        
        Args:
            thinking: Полный текст рассуждения
            stage: Этап workflow
            start_time: Время начала
            
        Yields:
            SSE события для каждого чанка
        """
        if not thinking or not self.config.enabled:
            return
        
        # Отправляем начало
        yield await self.create_thinking_event(ThinkingChunk(
            content="",
            status=ThinkingStatus.STARTED,
            stage=stage,
            elapsed_ms=0,
            total_chars=len(thinking)
        ))
        
        # Стримим чанками
        chunk_size = self.config.chunk_size
        total_sent = 0
        
        for i in range(0, len(thinking), chunk_size):
            if self._interrupted:
                yield await self.create_thinking_event(ThinkingChunk(
                    content="[прервано пользователем]",
                    status=ThinkingStatus.INTERRUPTED,
                    stage=stage,
                    elapsed_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                    total_chars=total_sent
                ))
                return
            
            chunk_content = thinking[i:i + chunk_size]
            total_sent += len(chunk_content)
            elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
            
            yield await self.create_thinking_event(ThinkingChunk(
                content=chunk_content,
                status=ThinkingStatus.IN_PROGRESS,
                stage=stage,
                elapsed_ms=elapsed,
                total_chars=total_sent
            ))
            
            # Небольшая задержка для плавности UI
            await asyncio.sleep(self.config.debounce_ms / 1000)
        
        # Отправляем завершение
        elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
        yield await self.create_thinking_event(ThinkingChunk(
            content=thinking,
            status=ThinkingStatus.COMPLETED,
            stage=stage,
            elapsed_ms=elapsed,
            total_chars=len(thinking)
        ))
    
    async def process_response_with_thinking(
        self,
        response: str,
        stage: str,
        start_time: Optional[datetime] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает ответ модели, стримит <think> блок если есть.
        
        Args:
            response: Полный ответ модели
            stage: Этап workflow
            start_time: Время начала (для метрик)
            
        Yields:
            SSE события для thinking блока
        """
        if not response:
            return
        
        start_time = start_time or datetime.now()
        
        # Проверяем есть ли <think> блок
        if not is_reasoning_response(response):
            logger.debug(f"📝 Ответ без <think> блока на этапе {stage}")
            return
        
        # Парсим ответ
        parsed = parse_reasoning_response(response)
        
        if parsed.has_thinking and parsed.thinking:
            logger.info(
                f"🧠 Стримим рассуждения для {stage}: "
                f"{parsed.thinking_lines} строк, {len(parsed.thinking)} символов"
            )
            
            # Стримим thinking контент
            async for event in self.stream_thinking_content(
                thinking=parsed.thinking,
                stage=stage,
                start_time=start_time
            ):
                yield event
    
    async def stream_from_llm(
        self,
        llm: 'LocalLLM',
        prompt: str,
        stage: str,
        num_predict: int = 4096,
        **kwargs
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Real-time стриминг от LLM с разделением thinking и content.
        
        Стримит ответ LLM в реальном времени, отправляя SSE события
        для <think> блоков по мере их генерации.
        
        Args:
            llm: Экземпляр LocalLLM
            prompt: Промпт для генерации
            stage: Этап workflow (coding, planning, etc.)
            num_predict: Максимум токенов
            **kwargs: Дополнительные параметры для generate_stream
            
        Yields:
            tuple[event_type, data]:
                - ("thinking", sse_event) — SSE событие для thinking
                - ("content", chunk) — чанк основного контента (код и т.д.)
                - ("done", full_response) — финальный полный ответ
                
        Example:
            ```python
            async for event_type, data in manager.stream_from_llm(llm, prompt, "coding"):
                if event_type == "thinking":
                    yield data  # SSE событие
                elif event_type == "content":
                    yield code_chunk_event(data)
                elif event_type == "done":
                    final_code = extract_code(data)
            ```
        """
        from infrastructure.local_llm import StreamChunk
        
        start_time = datetime.now()
        thinking_buffer = ""
        content_buffer = ""
        thinking_started = False
        thinking_completed = False
        total_thinking_chars = 0
        
        try:
            chunk_count = 0
            thinking_chunk_count = 0
            chunk = None  # Инициализируем для случая когда цикл не выполнится
            async for chunk in llm.generate_stream(prompt, num_predict=num_predict, **kwargs):
                chunk_count += 1
                if self._interrupted:
                    # Отправляем событие прерывания
                    yield ("thinking", await self.create_thinking_event(ThinkingChunk(
                        content="[прервано пользователем]",
                        status=ThinkingStatus.INTERRUPTED,
                        stage=stage,
                        elapsed_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                        total_chars=total_thinking_chars
                    )))
                    return
                
                if chunk.is_thinking:
                    thinking_chunk_count += 1
                    # Внутри <think> блока
                    if not thinking_started:
                        thinking_started = True
                        logger.info(f"🧠 [{stage}] Начало <think> блока (модель: {llm.model})")
                        # Отправляем событие начала
                        event = await self.create_thinking_event(ThinkingChunk(
                            content="",
                            status=ThinkingStatus.STARTED,
                            stage=stage,
                            elapsed_ms=0,
                            total_chars=0
                        ))
                        logger.info(f"📤 [{stage}] Yielding thinking_started (длина SSE: {len(event)})")
                        yield ("thinking", event)
                    
                    thinking_buffer += chunk.content
                    total_thinking_chars += len(chunk.content)
                    
                    # Отправляем чанк thinking
                    elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
                    event = await self.create_thinking_event(ThinkingChunk(
                        content=chunk.content,
                        status=ThinkingStatus.IN_PROGRESS,
                        stage=stage,
                        elapsed_ms=elapsed,
                        total_chars=total_thinking_chars
                    ))
                    if thinking_chunk_count % 10 == 0:  # Логируем каждые 10 чанков
                        logger.info(f"📤 [{stage}] Yielding thinking_in_progress #{thinking_chunk_count} (длина SSE: {len(event)}, контент: {len(chunk.content)} символов)")
                    yield ("thinking", event)
                    
                else:
                    # Вне <think> блока — основной контент
                    
                    # Если был thinking и ещё не завершён — завершаем
                    if thinking_started and not thinking_completed:
                        thinking_completed = True
                        elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
                        logger.info(f"🧠 [{stage}] Завершение <think> блока ({total_thinking_chars} символов, {elapsed}ms)")
                        event = await self.create_thinking_event(ThinkingChunk(
                            content=thinking_buffer,
                            status=ThinkingStatus.COMPLETED,
                            stage=stage,
                            elapsed_ms=elapsed,
                            total_chars=total_thinking_chars
                        ))
                        logger.info(f"📤 [{stage}] Yielding thinking_completed (длина SSE: {len(event)})")
                        yield ("thinking", event)
                    
                    # Отправляем контент
                    if chunk.content:
                        content_buffer += chunk.content
                        yield ("content", chunk.content)
            
            # Финальное логирование
            if thinking_chunk_count > 0:
                logger.info(f"✅ [{stage}] Стриминг завершён: {chunk_count} чанков, {thinking_chunk_count} thinking чанков, {total_thinking_chars} символов thinking")
            else:
                logger.warning(f"⚠️ [{stage}] Нет thinking блоков! Модель {llm.model} не является reasoning моделью или не генерирует <think> блоки")
            
            # Если был thinking блок и он не был завершён, завершаем его
            if thinking_started and not thinking_completed:
                thinking_completed = True
                elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
                logger.warning(f"⚠️ [{stage}] <think> блок не был закрыт корректно, принудительно завершаю ({total_thinking_chars} символов)")
                event = await self.create_thinking_event(ThinkingChunk(
                    content=thinking_buffer,
                    status=ThinkingStatus.COMPLETED,
                    stage=stage,
                    elapsed_ms=elapsed,
                    total_chars=total_thinking_chars
                ))
                yield ("thinking", event)
            
            # Финальное событие с полным ответом
            full_response = thinking_buffer + content_buffer if thinking_buffer else content_buffer
            yield ("done", chunk.full_response if chunk else full_response)
            
        except Exception as e:
            logger.error(f"❌ Ошибка стриминга от LLM: {e}", error=e)
            # Если был thinking блок, отправляем событие прерывания
            if thinking_started and not thinking_completed:
                elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
                try:
                    event = await self.create_thinking_event(ThinkingChunk(
                        content=thinking_buffer or "[ошибка стриминга]",
                        status=ThinkingStatus.INTERRUPTED,
                        stage=stage,
                        elapsed_ms=elapsed,
                        total_chars=total_thinking_chars
                    ))
                    yield ("thinking", event)
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Ошибка при отправке события прерывания: {cleanup_error}")
            yield ("done", content_buffer)
        finally:
            # Очищаем буферы для предотвращения утечек памяти
            thinking_buffer = ""
            content_buffer = ""
            thinking_started = False
            thinking_completed = False


# === Factory и Singleton ===

_reasoning_stream_manager: Optional[ReasoningStreamManager] = None


def get_reasoning_stream_manager(
    config: Optional[ReasoningStreamConfig] = None
) -> ReasoningStreamManager:
    """Возвращает singleton экземпляр ReasoningStreamManager.
    
    Args:
        config: Конфигурация (только при первом вызове)
        
    Returns:
        ReasoningStreamManager instance
    """
    global _reasoning_stream_manager
    
    if _reasoning_stream_manager is None:
        # Загружаем конфиг из config.toml если не передан
        if config is None:
            config = _load_config_from_toml()
        logger.info(f"🧠 Инициализация ReasoningStreamManager: enabled={config.enabled}, chunk_size={config.chunk_size}, debounce_ms={config.debounce_ms}")
        _reasoning_stream_manager = ReasoningStreamManager(config)
    
    return _reasoning_stream_manager


def reset_reasoning_stream_manager() -> None:
    """Сбрасывает singleton (для тестов)."""
    global _reasoning_stream_manager
    if _reasoning_stream_manager:
        _reasoning_stream_manager.reset()
    _reasoning_stream_manager = None


def _load_config_from_toml() -> ReasoningStreamConfig:
    """Загружает конфигурацию из config.toml.
    
    Читает из секций [reasoning] и [streaming].
    
    Returns:
        ReasoningStreamConfig с настройками из конфига
    """
    try:
        from utils.config import get_config
        config = get_config()
        
        # Читаем настройки из [reasoning] и [streaming] секций
        reasoning_config = config._config_data.get("reasoning", {})
        streaming_config = config._config_data.get("streaming", {})
        
        return ReasoningStreamConfig(
            enabled=streaming_config.get("enabled", True) and reasoning_config.get("show_thinking", True),
            chunk_size=streaming_config.get("thinking_chunk_size", 100),
            debounce_ms=streaming_config.get("thinking_debounce_ms", 50),
            max_thinking_time_ms=streaming_config.get("max_thinking_time_ms", 120_000),
            show_summary_only=reasoning_config.get("show_summary_only", False)
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось загрузить config.toml для reasoning: {e}")
        return ReasoningStreamConfig()
