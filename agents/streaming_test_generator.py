"""Стриминговая версия агента генерации тестов.

Обеспечивает real-time стриминг:
- <think> блоков reasoning моделей
- Тестов по мере генерации
- Возможность прерывания
"""
from typing import Optional, AsyncGenerator
from infrastructure.local_llm import create_llm_for_stage
from infrastructure.prompt_enhancer import get_prompt_enhancer
from infrastructure.reasoning_stream import get_reasoning_stream_manager
from infrastructure.reasoning_utils import extract_code_from_reasoning, is_reasoning_response
from agents.base import BaseAgent
from utils.logger import get_logger
from utils.config import get_config
from infrastructure.model_router import get_model_router

logger = get_logger()


class StreamingTestGeneratorAgent(BaseAgent):
    """Агент для генерации pytest тестов с real-time стримингом.
    
    Расширяет функциональность TestGeneratorAgent:
    - Real-time стриминг <think> блоков
    - Real-time стриминг тестов
    - Возможность прерывания генерации
    """

    def __init__(
        self, 
        model: Optional[str] = None, 
        temperature: float = 0.18
    ) -> None:
        """Инициализация агента.
        
        Args:
            model: Модель (если None, выбирается автоматически)
            temperature: Температура (0.15-0.2 для точности)
        """
        # Инициализация базового класса (LLM создаётся автоматически)
        super().__init__(
            model=model,
            temperature=temperature,
            stage="testing"
        )
        self.prompt_enhancer = get_prompt_enhancer()
        self.reasoning_manager = get_reasoning_stream_manager()
        self._interrupted = False
    
    def interrupt(self) -> None:
        """Прерывает текущую генерацию."""
        self._interrupted = True
        self.reasoning_manager.interrupt()
        logger.info("⏹️ Генерация тестов прервана")
    
    def reset(self) -> None:
        """Сбрасывает состояние агента."""
        self._interrupted = False
        self.reasoning_manager.reset()
    
    async def generate_tests_stream(
        self,
        plan: str,
        context: str,
        intent_type: str,
        user_query: str = "",
        min_test_cases: int = 3,
        max_test_cases: int = 5,
        stage: str = "testing"
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Генерирует тесты с real-time стримингом.
        
        Args:
            plan: План реализации
            context: Контекст из RAG
            intent_type: Тип намерения
            user_query: Запрос пользователя
            min_test_cases: Мин. количество тестов
            max_test_cases: Макс. количество тестов
            stage: Этап workflow
            
        Yields:
            tuple[event_type, data]:
                - ("thinking", sse_event) — SSE событие для <think> блока
                - ("test_chunk", chunk) — чанк тестов
                - ("done", final_tests) — финальные тесты
        """
        logger.info(f"🧪 Стриминг тестов для: {intent_type} (план: {len(plan)} симв., контекст: {len(context)} симв.)")
        
        self.reset()
        
        # Не генерируем тесты для приветствий
        if intent_type == "greeting":
            logger.info("ℹ️ Пропущена генерация тестов для приветствия")
            yield ("done", "")
            return
        
        # Строим промпт
        if user_query:
            prompt = self.prompt_enhancer.enhance_for_tests(
                user_query=user_query,
                intent_type=intent_type,
                context=context
            )
        else:
            prompt = self._build_test_generation_prompt(
                plan=plan,
                context=context,
                intent_type=intent_type,
                min_cases=min_test_cases,
                max_cases=max_test_cases
            )
        
        config = get_config()
        tests_buffer = ""
        full_response = ""
        
        try:
            async for event_type, data in self.reasoning_manager.stream_from_llm(
                llm=self.llm,
                prompt=prompt,
                stage=stage,
                num_predict=config.llm_tokens_tests
            ):
                if self._interrupted:
                    logger.info("⏹️ Генерация прервана")
                    break
                
                if event_type == "thinking":
                    yield ("thinking", data)
                elif event_type == "content":
                    tests_buffer += data
                    yield ("test_chunk", data)
                elif event_type == "done":
                    full_response = data
            
            # Очищаем финальные тесты
            if full_response:
                if is_reasoning_response(full_response):
                    tests_only = extract_code_from_reasoning(full_response)
                    cleaned_tests = self._clean_test_code(tests_only)
                else:
                    cleaned_tests = self._clean_test_code(full_response)
            else:
                cleaned_tests = self._clean_test_code(tests_buffer)
            
            if cleaned_tests:
                logger.info(f"✅ Тесты сгенерированы ({len(cleaned_tests)} символов)")
            else:
                logger.warning("⚠️ Не удалось сгенерировать тесты")
            
            yield ("done", cleaned_tests)
            
        except Exception as e:
            logger.error(f"❌ Ошибка стриминга тестов: {e}", error=e)
            yield ("done", "")
    
    # === Синхронный метод для обратной совместимости ===
    
    def generate_tests(
        self,
        plan: str,
        context: str,
        intent_type: str,
        user_query: str = "",
        min_test_cases: int = 3,
        max_test_cases: int = 5
    ) -> str:
        """Синхронная генерация тестов (для обратной совместимости)."""
        from agents.test_generator import TestGeneratorAgent
        
        sync_agent = TestGeneratorAgent(
            model=self.model,
            temperature=self.temperature
        )
        return sync_agent.generate_tests(
            plan, context, intent_type, user_query, min_test_cases, max_test_cases
        )
    
    # === Приватные методы ===
    
    def _build_test_generation_prompt(
        self,
        plan: str,
        context: str,
        intent_type: str,
        min_cases: int,
        max_cases: int
    ) -> str:
        """Строит промпт для генерации тестов."""
        # Используем унифицированную функцию для получения описания intent
        from utils.intent_helpers import get_intent_description
        intent_desc = get_intent_description(intent_type, format="planning") or "выполнение задачи"
        
        context_section = ""
        if context.strip():
            context_section = f"""
Контекст из базы знаний:
{context}
"""
        
        prompt = f"""Ты - эксперт по написанию pytest тестов. Сгенерируй тесты для следующей задачи.

Тип задачи: {intent_desc}

План реализации:
{plan}
{context_section}
КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:
1. АНАЛИЗИРУЙ что функция делает:
   - Если функция использует print() для вывода — используй capsys для захвата stdout
   - Если функция возвращает значение (return) — проверяй возвращаемое значение
   - Если функция изменяет объект — проверяй изменение объекта
   - Если функция записывает в файл — используй tmp_path и проверяй содержимое

2. ПРИМЕРЫ правильного тестирования:

   # Для функции с print() — используй capsys:
   def test_hello_world(capsys):
       hello_world()  # функция вызывает print()
       captured = capsys.readouterr()
       assert "Hello" in captured.out
   
   # Для функции с return — проверяй значение:
   def test_add():
       result = add(2, 3)
       assert result == 5
   
   # Для функции изменяющей список — проверяй изменение:
   def test_append_item():
       items = []
       append_item(items, "x")
       assert "x" in items

3. ТРЕБОВАНИЯ:
   - Напиши {min_cases}-{max_cases} осмысленных тестов
   - Покрывай: основной функционал, граничные случаи, ошибки
   - Понятные имена тестов: test_функция_сценарий
   - НЕ используй parametrize если это усложняет тест
   - Код должен быть готов к запуску без изменений

Верни ТОЛЬКО код тестов на Python. Начни сразу с import pytest.
"""
        return prompt
    
    def _clean_test_code(self, raw_code: str) -> str:
        """Очищает сгенерированный код тестов."""
        if not raw_code:
            return ""
        
        lines = raw_code.split("\n")
        cleaned_lines: list[str] = []
        skip_until_code = False
        in_code_block = False
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    skip_until_code = True
                else:
                    in_code_block = False
                continue
            
            if skip_until_code:
                if stripped.startswith("import") or stripped.startswith("from") or stripped.startswith("def test_"):
                    skip_until_code = False
                    cleaned_lines.append(line)
                continue
            
            if not cleaned_lines and (stripped.startswith("#") or not stripped or stripped.lower().startswith("вот")):
                continue
            
            cleaned_lines.append(line)
        
        cleaned = "\n".join(cleaned_lines).strip()
        
        if "def test_" not in cleaned and "def test" not in cleaned:
            logger.warning("⚠️ В тестах не найдено функций test_*")
            return ""
        
        return cleaned


# === Factory функция ===

def get_streaming_test_generator_agent(
    model: Optional[str] = None,
    temperature: float = 0.18
) -> StreamingTestGeneratorAgent:
    """Создаёт StreamingTestGeneratorAgent."""
    return StreamingTestGeneratorAgent(model=model, temperature=temperature)
