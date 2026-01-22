"""Агент для генерации pytest тестов до написания кода (TDD)."""
from typing import Optional
from infrastructure.local_llm import create_llm_for_stage
from infrastructure.prompt_enhancer import get_prompt_enhancer
from utils.logger import get_logger
from utils.model_checker import (
    get_available_model,
    get_any_available_model,
    check_model_available
)
from utils.config import get_config
from infrastructure.model_router import get_model_router


logger = get_logger()


class TestGeneratorAgent:
    """Агент для генерации pytest тестов на основе плана, контекста и намерения.
    
    Следует TDD-подходу: тесты генерируются ДО кода.
    Использует PromptEnhancer для динамического улучшения промптов.
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.18) -> None:
        """Инициализация агента генерации тестов.
        
        Args:
            model: Модель для генерации тестов (если None, выбирается из config)
            temperature: Температура генерации (0.15-0.2 по правилам, низкая для точности)
        """
        # Инициализация базового класса (LLM создаётся автоматически)
        super().__init__(
            model=model,
            temperature=temperature,
            stage="testing"
        )
        self.prompt_enhancer = get_prompt_enhancer()

    def generate_tests(
        self,
        plan: str,
        context: str,
        intent_type: str,
        user_query: str = "",
        min_test_cases: int = 3,
        max_test_cases: int = 5
    ) -> str:
        """Генерирует pytest тесты на основе плана, контекста и намерения.
        
        Args:
            plan: План реализации задачи
            context: Собранный контекст из RAG/веб-поиска
            intent_type: Тип намерения (create/modify/debug/etc)
            user_query: Оригинальный запрос пользователя (для улучшения промпта)
            min_test_cases: Минимальное количество тестовых кейсов
            max_test_cases: Максимальное количество тестовых кейсов
            
        Returns:
            Строка с полным кодом pytest тестов. Пустая строка в случае ошибки.
        """
        logger.info(f"🧪 Генерирую pytest тесты для намерения: {intent_type}")
        
        # Не генерируем тесты для приветствий
        if intent_type == "greeting":
            logger.info("ℹ️ Пропущена генерация тестов для приветствия")
            return ""
        
        # Используем динамическое улучшение промпта если есть запрос пользователя
        if user_query:
            prompt = self.prompt_enhancer.enhance_for_tests(
                user_query=user_query,
                intent_type=intent_type,
                context=context
            )
        else:
            # Fallback на старый метод
            prompt = self._build_test_generation_prompt(
                plan=plan,
                context=context,
                intent_type=intent_type,
                min_cases=min_test_cases,
                max_cases=max_test_cases
            )
        
        config = get_config()
        response = self.llm.generate(prompt, num_predict=config.llm_tokens_tests)
        
        # Очищаем и валидируем сгенерированные тесты
        cleaned_tests = self._clean_test_code(response)
        
        if cleaned_tests:
            logger.info(f"✅ Сгенерировано тестов (размер: {len(cleaned_tests)} символов)")
        else:
            logger.warning("⚠️ Не удалось сгенерировать валидные тесты")
        
        return cleaned_tests

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
        """Очищает сгенерированный код тестов от лишних элементов.
        
        Args:
            raw_code: Сырой код от модели
            
        Returns:
            Очищенный код тестов
        """
        if not raw_code:
            return ""
        
        lines = raw_code.split("\n")
        cleaned_lines: list[str] = []
        
        # Убираем markdown блоки кода (```python, ```)
        skip_until_code = False
        in_code_block = False
        
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
                # Ждём начала реального кода (импорт или def)
                if stripped.startswith("import") or stripped.startswith("from") or stripped.startswith("def test_"):
                    skip_until_code = False
                    cleaned_lines.append(line)
                continue
            
            # Пропускаем строки с объяснениями в начале
            if not cleaned_lines and (stripped.startswith("#") or not stripped or stripped.lower().startswith("вот")):
                continue
            
            cleaned_lines.append(line)
        
        cleaned = "\n".join(cleaned_lines).strip()
        
        # Убеждаемся что есть хотя бы один test_ функция
        if "def test_" not in cleaned and "def test" not in cleaned:
            logger.warning("⚠️ В сгенерированных тестах не найдено функций test_*")
            return ""
        
        return cleaned
