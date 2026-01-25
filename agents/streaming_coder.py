"""Стриминговая версия агента генерации кода.

Обеспечивает real-time стриминг:
- <think> блоков reasoning моделей
- Кода по мере генерации
- Возможность прерывания

Использует LocalLLM.generate_stream() для асинхронного стриминга.
Совместим с существующим CoderAgent через общие промпты и очистку кода.

Пример использования:
    ```python
    from agents.streaming_coder import StreamingCoderAgent
    
    agent = StreamingCoderAgent(model="deepseek-r1:7b")
    
    async for event_type, data in agent.generate_code_stream(plan, tests, context, intent):
        if event_type == "thinking":
            yield data  # SSE событие для UI
        elif event_type == "code_chunk":
            yield code_chunk_event(data)
        elif event_type == "done":
            final_code = data
    ```
"""
from typing import Optional, Dict, Any, AsyncGenerator, TYPE_CHECKING
from infrastructure.local_llm import create_llm_for_stage, StreamChunk
from infrastructure.prompt_enhancer import get_prompt_enhancer
from infrastructure.reasoning_stream import get_reasoning_stream_manager
from infrastructure.coder_prompt_builder import get_coder_prompt_builder
from utils.logger import get_logger
from utils.config import get_config
from utils.intent_helpers import get_intent_description
from agents.base import BaseAgent

if TYPE_CHECKING:
    from infrastructure.coder_prompt_builder import CoderPromptBuilder

logger = get_logger()


class StreamingCoderAgent(BaseAgent):
    """Агент для генерации кода с real-time стримингом.
    
    Расширяет функциональность CoderAgent:
    - Real-time стриминг <think> блоков
    - Real-time стриминг кода
    - Возможность прерывания генерации
    
    Для обратной совместимости сохранён синхронный generate_code().
    """

    def __init__(
        self, 
        model: Optional[str] = None, 
        temperature: float = 0.25,
        user_query: str = ""
    ) -> None:
        """Инициализация агента.
        
        Args:
            model: Модель для генерации (если None, выбирается автоматически)
            temperature: Температура генерации (0.15-0.35)
            user_query: Оригинальный запрос пользователя
        """
        # Инициализация базового класса (LLM создаётся автоматически)
        super().__init__(
            model=model,
            temperature=temperature,
            stage="coding"
        )
        
        self.user_query = user_query
        self.prompt_enhancer = get_prompt_enhancer()
        self.prompt_builder = get_coder_prompt_builder()
        self.reasoning_manager = get_reasoning_stream_manager()
        self._interrupted = False
    
    def interrupt(self) -> None:
        """Прерывает текущую генерацию."""
        self._interrupted = True
        self.reasoning_manager.interrupt()
        logger.info("⏹️ Генерация кода прервана")
    
    async def generate_code_stream(
        self,
        plan: str,
        tests: str,
        context: str,
        intent_type: str,
        user_query: str = "",
        stage: str = "coding"
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Генерирует код с real-time стримингом.
        
        Args:
            plan: План реализации
            tests: Тесты pytest
            context: Контекст из RAG
            intent_type: Тип намерения (create/modify/debug/etc)
            user_query: Запрос пользователя
            stage: Этап workflow (для SSE событий)
            
        Yields:
            tuple[event_type, data]:
                - ("thinking", sse_event) — SSE событие для <think> блока
                - ("code_chunk", chunk) — чанк сгенерированного кода
                - ("done", final_code) — финальный очищенный код
                
        Example:
            async for event_type, data in agent.generate_code_stream(...):
                if event_type == "thinking":
                    yield data  # Отправляем SSE
                elif event_type == "code_chunk":
                    yield create_code_chunk_sse(data)
                elif event_type == "done":
                    save_code(data)
        """
        logger.info(f"💻 Стриминг генерации кода для: {intent_type}")
        
        self.reset()
        
        # Не генерируем код для приветствий
        if intent_type == "greeting":
            logger.info("ℹ️ Пропущена генерация для приветствия")
            yield ("done", "")
            return
        
        # Отправляем thinking о начале анализа
        from datetime import datetime
        from infrastructure.reasoning_stream import ThinkingChunk, ThinkingStatus
        start_time = datetime.now()
        
        yield ("thinking", await self.reasoning_manager.create_thinking_event(
            ThinkingChunk(
                content="Начинаю анализ задачи и подготовку к генерации кода...",
                status=ThinkingStatus.IN_PROGRESS,
                stage=stage,
                elapsed_ms=0,
                total_chars=0
            )
        ))
        
        # Анализируем контекст и отправляем thinking
        if context:
            context_preview = context[:200] + "..." if len(context) > 200 else context
            yield ("thinking", await self.reasoning_manager.create_thinking_event(
                ThinkingChunk(
                    content=f"Анализирую контекст проекта ({len(context)} символов): {context_preview}",
                    status=ThinkingStatus.IN_PROGRESS,
                    stage=stage,
                    elapsed_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                    total_chars=0
                )
            ))
        
        # Строим промпт
        query = user_query or self.user_query
        if query:
            prompt = self.prompt_enhancer.enhance_for_coding(
                user_query=query,
                intent_type=intent_type,
                plan=plan,
                tests=tests,
                context=context
            )
        else:
            # ИСПРАВЛЕНИЕ: Используем prompt_builder вместо удаленного метода
            prompt = self.prompt_builder.build_generation_prompt(
                plan=plan,
                tests=tests,
                context=context,
                intent_type=intent_type,
                user_query=query
            )
        
        # Отправляем thinking о начале генерации
        yield ("thinking", await self.reasoning_manager.create_thinking_event(
            ThinkingChunk(
                content=f"Начинаю генерацию кода для задачи типа '{intent_type}'. План содержит {len(plan.split(chr(10)))} шагов.",
                status=ThinkingStatus.IN_PROGRESS,
                stage=stage,
                elapsed_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                total_chars=0
            )
        ))
        
        config = get_config()
        code_buffer = ""
        full_response = ""
        
        try:
            # Real-time стриминг через reasoning_manager
            async for event_type, data in self.reasoning_manager.stream_from_llm(
                llm=self.llm,
                prompt=prompt,
                stage=stage,
                num_predict=config.llm_tokens_code
            ):
                if self._interrupted:
                    logger.info("⏹️ Генерация прервана пользователем")
                    break
                
                if event_type == "thinking":
                    # Пробрасываем SSE событие для thinking
                    yield ("thinking", data)
                    
                elif event_type == "progress":
                    # ИСПРАВЛЕНИЕ: Пробрасываем progress события для non-reasoning моделей
                    yield ("progress", data)
                    
                elif event_type == "content":
                    # Накапливаем код и отправляем чанк
                    code_buffer += data
                    yield ("code_chunk", data)
                    
                elif event_type == "done":
                    full_response = data
            
            # Очищаем финальный код (используем метод из BaseAgent)
            if full_response:
                cleaned_code = self._clean_code_from_reasoning(full_response)
            else:
                cleaned_code = self._clean_code(code_buffer)
            
            if cleaned_code:
                logger.info(f"✅ Код сгенерирован ({len(cleaned_code)} символов)")
            else:
                logger.warning("⚠️ Не удалось сгенерировать валидный код")
            
            yield ("done", cleaned_code)
            
        except Exception as e:
            from infrastructure.local_llm import LLMModelUnavailableError
            
            if isinstance(e, LLMModelUnavailableError):
                logger.warning(
                    f"⚠️ Модель {e.model} недоступна при генерации кода: {e}. "
                    f"Пробую переключиться на запасную модель..."
                )
                
                # Пробуем переключиться на запасную модель
                if self._switch_to_fallback_model(
                    failed_model=e.model,
                    task_type="coding",
                    complexity=getattr(e, 'complexity', None)
                ):
                    logger.info(f"✅ Переключился на модель {self.model}, повторяю генерацию...")
                    
                    # ВАЖНО: Пересоздаём промпт после переключения модели
                    # (модель могла измениться, промпт должен быть актуальным)
                    query = user_query or self.user_query
                    if query:
                        prompt = self.prompt_enhancer.enhance_for_coding(
                            user_query=query,
                            intent_type=intent_type,
                            plan=plan,
                            tests=tests,
                            context=context
                        )
                    else:
                        # ИСПРАВЛЕНИЕ: Используем prompt_builder вместо удаленного метода
                        prompt = self.prompt_builder.build_generation_prompt(
                            plan=plan,
                            tests=tests,
                            context=context,
                            intent_type=intent_type,
                            user_query=query
                        )
                    
                    # Отправляем thinking о переключении модели
                    yield ("thinking", await self.reasoning_manager.create_thinking_event(
                        ThinkingChunk(
                            content=f"Переключился на модель {self.model}. Продолжаю генерацию кода...",
                            status=ThinkingStatus.IN_PROGRESS,
                            stage=stage,
                            elapsed_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                            total_chars=0
                        )
                    ))
                    
                    # Повторяем попытку с новой моделью
                    try:
                        code_buffer = ""
                        full_response = ""
                        
                        async for event_type, data in self.reasoning_manager.stream_from_llm(
                            llm=self.llm,
                            prompt=prompt,
                            stage=stage,
                            num_predict=config.llm_tokens_code
                        ):
                            if self._interrupted:
                                logger.info("⏹️ Генерация прервана пользователем")
                                break
                            
                            if event_type == "thinking":
                                yield ("thinking", data)
                            elif event_type == "content":
                                code_buffer += data
                                yield ("code_chunk", data)
                            elif event_type == "done":
                                full_response = data
                        
                        # Очищаем финальный код
                        if full_response:
                            cleaned_code = self._clean_code_from_reasoning(full_response)
                        else:
                            cleaned_code = self._clean_code(code_buffer)
                        
                        if cleaned_code:
                            logger.info(f"✅ Код сгенерирован с запасной моделью ({len(cleaned_code)} символов)")
                        else:
                            logger.warning("⚠️ Не удалось сгенерировать валидный код даже с запасной моделью")
                        
                        yield ("done", cleaned_code)
                        return
                        
                    except Exception as retry_error:
                        logger.error(
                            f"❌ Ошибка при повторной попытке с запасной моделью {self.model}: {retry_error}",
                            error=retry_error
                        )
                        yield ("done", "")
                else:
                    logger.error(
                        f"❌ Не удалось переключиться на запасную модель. "
                        f"Код не был сгенерирован."
                    )
                    yield ("done", "")
            else:
                logger.error(f"❌ Ошибка стриминга кода: {e}", error=e)
                yield ("done", "")
    
    async def fix_code_stream(
        self,
        code: str,
        instructions: str,
        tests: str,
        validation_results: Dict[str, Any],
        stage: str = "fixing"
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Исправляет код с real-time стримингом.
        
        Args:
            code: Исходный код с ошибками
            instructions: Инструкции от Debugger
            tests: Тесты
            validation_results: Результаты валидации
            stage: Этап workflow
            
        Yields:
            tuple[event_type, data] — аналогично generate_code_stream
        """
        logger.info("🔧 Стриминг исправления кода...")
        
        self.reset()
        
        if not code.strip() or not instructions.strip():
            logger.warning("⚠️ Пустой код или инструкции")
            yield ("done", code)
            return
        
        # ИСПРАВЛЕНИЕ: Используем prompt_builder вместо удаленного метода
        prompt = self.prompt_builder.build_fix_prompt(
            code=code,
            instructions=instructions,
            tests=tests,
            validation_results=validation_results
        )
        
        config = get_config()
        code_buffer = ""
        full_response = ""
        
        try:
            async for event_type, data in self.reasoning_manager.stream_from_llm(
                llm=self.llm,
                prompt=prompt,
                stage=stage,
                num_predict=config.llm_tokens_code
            ):
                if self._interrupted:
                    break
                
                if event_type == "thinking":
                    yield ("thinking", data)
                elif event_type == "content":
                    code_buffer += data
                    yield ("code_chunk", data)
                elif event_type == "done":
                    full_response = data
            
            # Очищаем код (используем метод из BaseAgent)
            if full_response:
                cleaned_code = self._clean_code_from_reasoning(full_response)
            else:
                cleaned_code = self._clean_code(code_buffer)
            
            if not cleaned_code:
                logger.warning("⚠️ Не удалось исправить код, возвращаю исходный")
                cleaned_code = code
            else:
                logger.info(f"✅ Код исправлен ({len(cleaned_code)} символов)")
            
            yield ("done", cleaned_code)
            
        except Exception as e:
            from infrastructure.local_llm import LLMModelUnavailableError
            
            if isinstance(e, LLMModelUnavailableError):
                logger.warning(
                    f"⚠️ Модель {e.model} недоступна при исправлении кода: {e}. "
                    f"Пробую переключиться на запасную модель..."
                )
                
                # Пробуем переключиться на запасную модель
                if self._switch_to_fallback_model(
                    failed_model=e.model,
                    task_type="fixing",
                    complexity=getattr(e, 'complexity', None)
                ):
                    logger.info(f"✅ Переключился на модель {self.model}, повторяю исправление...")
                    
                    # Повторяем попытку с новой моделью
                    try:
                        code_buffer = ""
                        full_response = ""
                        
                        async for event_type, data in self.reasoning_manager.stream_from_llm(
                            llm=self.llm,
                            prompt=prompt,
                            stage=stage,
                            num_predict=config.llm_tokens_code
                        ):
                            if self._interrupted:
                                break
                            
                            if event_type == "thinking":
                                yield ("thinking", data)
                            elif event_type == "content":
                                code_buffer += data
                                yield ("code_chunk", data)
                            elif event_type == "done":
                                full_response = data
                        
                        # Очищаем код
                        if full_response:
                            cleaned_code = self._clean_code_from_reasoning(full_response)
                        else:
                            cleaned_code = self._clean_code(code_buffer)
                        
                        if not cleaned_code:
                            logger.warning("⚠️ Не удалось исправить код даже с запасной моделью, возвращаю исходный")
                            cleaned_code = code
                        else:
                            logger.info(f"✅ Код исправлен с запасной моделью ({len(cleaned_code)} символов)")
                        
                        yield ("done", cleaned_code)
                        return
                        
                    except Exception as retry_error:
                        logger.error(
                            f"❌ Ошибка при повторной попытке с запасной моделью {self.model}: {retry_error}",
                            error=retry_error
                        )
                        yield ("done", code)
                else:
                    logger.error(
                        f"❌ Не удалось переключиться на запасную модель. "
                        f"Возвращаю исходный код."
                    )
                    yield ("done", code)
            else:
                logger.error(f"❌ Ошибка стриминга исправления: {e}", error=e)
                yield ("done", code)
    
    # === Приватные методы (общие с CoderAgent) ===
    
    # _build_code_generation_prompt и _build_fix_prompt удалены в пользу CoderPromptBuilder


    # === Factory функция ===

def get_streaming_coder_agent(
    model: Optional[str] = None,
    temperature: float = 0.25
) -> StreamingCoderAgent:
    """Создаёт StreamingCoderAgent с настройками из конфига.
    
    Args:
        model: Модель (если None, выбирается автоматически)
        temperature: Температура генерации
        
    Returns:
        Настроенный StreamingCoderAgent
    """
    return StreamingCoderAgent(model=model, temperature=temperature)
