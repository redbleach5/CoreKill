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
from typing import Optional, Dict, Any, AsyncGenerator
from infrastructure.local_llm import create_llm_for_stage, StreamChunk
from infrastructure.prompt_enhancer import get_prompt_enhancer
from infrastructure.reasoning_stream import get_reasoning_stream_manager
from infrastructure.reasoning_utils import extract_code_from_reasoning, is_reasoning_response
from utils.logger import get_logger
from utils.config import get_config
from infrastructure.model_router import get_model_router

logger = get_logger()


class StreamingCoderAgent:
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
        if model is None:
            router = get_model_router()
            model_selection = router.select_model(
                task_type="coding",
                preferred_model=None,
                context={"agent": "streaming_coder"}
            )
            model = model_selection.model
        
        self.model = model
        self.temperature = temperature
        self.llm = create_llm_for_stage(
            stage="coding",
            model=model,
            temperature=temperature,
            top_p=0.9
        )
        self.user_query = user_query
        self.prompt_enhancer = get_prompt_enhancer()
        self.reasoning_manager = get_reasoning_stream_manager()
        self._interrupted = False
    
    def interrupt(self) -> None:
        """Прерывает текущую генерацию."""
        self._interrupted = True
        self.reasoning_manager.interrupt()
        logger.info("⏹️ Генерация кода прервана")
    
    def reset(self) -> None:
        """Сбрасывает состояние агента."""
        self._interrupted = False
        self.reasoning_manager.reset()
    
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
            prompt = self._build_code_generation_prompt(
                plan=plan,
                tests=tests,
                context=context,
                intent_type=intent_type
            )
        
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
                    
                elif event_type == "content":
                    # Накапливаем код и отправляем чанк
                    code_buffer += data
                    yield ("code_chunk", data)
                    
                elif event_type == "done":
                    full_response = data
            
            # Очищаем финальный код
            if full_response:
                # Если был reasoning ответ — извлекаем код
                if is_reasoning_response(full_response):
                    code_only = extract_code_from_reasoning(full_response)
                    cleaned_code = self._clean_code(code_only)
                else:
                    cleaned_code = self._clean_code(full_response)
            else:
                cleaned_code = self._clean_code(code_buffer)
            
            if cleaned_code:
                logger.info(f"✅ Код сгенерирован ({len(cleaned_code)} символов)")
            else:
                logger.warning("⚠️ Не удалось сгенерировать валидный код")
            
            yield ("done", cleaned_code)
            
        except Exception as e:
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
        
        prompt = self._build_fix_prompt(
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
            
            # Очищаем код
            if full_response:
                if is_reasoning_response(full_response):
                    code_only = extract_code_from_reasoning(full_response)
                    cleaned_code = self._clean_code(code_only)
                else:
                    cleaned_code = self._clean_code(full_response)
            else:
                cleaned_code = self._clean_code(code_buffer)
            
            if not cleaned_code:
                logger.warning("⚠️ Не удалось исправить код, возвращаю исходный")
                cleaned_code = code
            else:
                logger.info(f"✅ Код исправлен ({len(cleaned_code)} символов)")
            
            yield ("done", cleaned_code)
            
        except Exception as e:
            logger.error(f"❌ Ошибка стриминга исправления: {e}", error=e)
            yield ("done", code)
    
    # === Синхронные методы для обратной совместимости ===
    
    def generate_code(
        self,
        plan: str,
        tests: str,
        context: str,
        intent_type: str,
        user_query: str = ""
    ) -> str:
        """Синхронная генерация кода (для обратной совместимости).
        
        Использует существующий CoderAgent под капотом.
        """
        from agents.coder import CoderAgent
        
        sync_agent = CoderAgent(
            model=self.model,
            temperature=self.temperature,
            user_query=user_query or self.user_query
        )
        return sync_agent.generate_code(plan, tests, context, intent_type, user_query)
    
    def fix_code(
        self,
        code: str,
        instructions: str,
        tests: str,
        validation_results: Dict[str, Any]
    ) -> str:
        """Синхронное исправление кода (для обратной совместимости)."""
        from agents.coder import CoderAgent
        
        sync_agent = CoderAgent(
            model=self.model,
            temperature=self.temperature
        )
        return sync_agent.fix_code(code, instructions, tests, validation_results)
    
    # === Приватные методы (общие с CoderAgent) ===
    
    def _build_code_generation_prompt(
        self,
        plan: str,
        tests: str,
        context: str,
        intent_type: str
    ) -> str:
        """Строит промпт для генерации кода."""
        intent_descriptions = {
            "create": "создать новую функцию/класс/модуль",
            "modify": "изменить существующий код",
            "debug": "исправить ошибки в коде",
            "optimize": "оптимизировать производительность кода",
            "explain": "объяснить код (генерация документации)",
            "test": "написать тесты (но тесты уже есть, нужно реализовать тестируемый код)",
            "refactor": "рефакторинг кода без изменения функциональности"
        }
        
        intent_desc = intent_descriptions.get(intent_type, "выполнить задачу")
        
        context_section = ""
        if context.strip():
            context_section = f"""
Контекст из базы знаний:
{context}
"""
        
        prompt = f"""Ты - эксперт по написанию чистого Python кода. Реализуй код, который пройдёт следующие тесты.

Тип задачи: {intent_desc}

План реализации:
{plan}
{context_section}
Тесты, которые должен пройти код:
{tests}

Требования к коду:
1. Код должен проходить ВСЕ предоставленные тесты
2. Используй type hints для всех функций и методов
3. Добавь docstrings на русском языке для всех публичных функций/классов/методов
4. Следуй PEP8 и лучшим практикам Python
5. Код должен быть читаемым и понятным
6. Обрабатывай ошибки там, где это необходимо
7. Используй понятные имена переменных (snake_case)
8. Импортируй все необходимые модули

Верни ТОЛЬКО код на Python, без объяснений и markdown разметки. Начни сразу с import statements.

Код:
"""
        return prompt
    
    def _build_fix_prompt(
        self,
        code: str,
        instructions: str,
        tests: str,
        validation_results: Dict[str, Any]
    ) -> str:
        """Строит промпт для исправления кода."""
        error_summary = []
        if not validation_results.get("pytest", {}).get("success", True):
            pytest_output = validation_results.get("pytest", {}).get("output", "")
            error_summary.append(f"pytest errors: {pytest_output[:300]}")
        if not validation_results.get("mypy", {}).get("success", True):
            mypy_errors = validation_results.get("mypy", {}).get("errors", "")
            error_summary.append(f"mypy errors: {mypy_errors[:300]}")
        if not validation_results.get("bandit", {}).get("success", True):
            bandit_issues = validation_results.get("bandit", {}).get("issues", "")
            error_summary.append(f"bandit issues: {bandit_issues[:300]}")
        
        errors_context = "\n".join(error_summary) if error_summary else "No specific error details"
        
        prompt = f"""You are an expert Python code fixer. Fix the code according to the specific instructions from Debugger Agent.

Current code (with errors):
```python
{code}
```

Tests:
```python
{tests[:1000]}
```

Validation errors:
{errors_context}

FIX INSTRUCTIONS (from Debugger Agent):
{instructions}

IMPORTANT RULES:
1. Follow the fix instructions EXACTLY
2. Make MINIMAL changes
3. Keep all existing functionality
4. Maintain type hints and docstrings
5. Return ONLY the fixed Python code, no explanations

Fixed code:
"""
        return prompt
    
    def _clean_code(self, raw_code: str) -> str:
        """Очищает сгенерированный код от markdown и лишних элементов."""
        if not raw_code:
            return ""
        
        lines = raw_code.split("\n")
        cleaned_lines: list[str] = []
        skip_until_code = False
        in_code_block = False
        
        # Маркеры начала текстовых объяснений (не Python код)
        explanation_markers = [
            "in the", "the above", "this code", "this function", "this class",
            "note:", "explanation:", "this will", "this is", "above code",
            "вот ", "этот код", "данный код", "выше", "ниже", "здесь мы",
            "в этом", "таким образом", "как видно",
            "### ", "## ", "** ", "tests:", "test cases:",
            "объяснение", "пояснение", "description:", "usage:"
        ]
        
        for line in lines:
            stripped = line.strip()
            
            # Пропускаем markdown блоки
            if stripped.startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    skip_until_code = True
                else:
                    in_code_block = False
                continue
            
            if skip_until_code:
                if (stripped.startswith("import") or 
                    stripped.startswith("from") or 
                    stripped.startswith("def ") or 
                    stripped.startswith("class ") or
                    stripped.startswith("@") or
                    stripped.startswith("#")):
                    skip_until_code = False
                    cleaned_lines.append(line)
                continue
            
            # Пропускаем объяснения в начале
            if not cleaned_lines and (not stripped or stripped.lower().startswith("вот")):
                continue
            
            # Останавливаемся если встретили текстовое объяснение (не код)
            stripped_lower = stripped.lower()
            is_explanation = any(stripped_lower.startswith(marker) for marker in explanation_markers)
            if is_explanation and cleaned_lines:
                # Проверяем что это не часть строки или комментария
                if not stripped.startswith("#") and not stripped.startswith("'") and not stripped.startswith('"'):
                    logger.debug(f"Обрезаем текстовое объяснение: {stripped[:50]}...")
                    break
            
            cleaned_lines.append(line)
        
        cleaned = "\n".join(cleaned_lines).strip()
        
        if "def " not in cleaned and "class " not in cleaned:
            logger.warning("⚠️ В коде не найдено функций или классов")
            return ""
        
        return cleaned


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
