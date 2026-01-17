"""Агент для генерации pytest тестов до написания кода (TDD)."""
from typing import Optional
from infrastructure.local_llm import LocalLLM
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
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.18) -> None:
        """Инициализация агента генерации тестов.
        
        Args:
            model: Модель для генерации тестов (если None, выбирается из config)
            temperature: Температура генерации (0.15-0.2 по правилам, низкая для точности)
        """
        if model is None:
            # Используем ModelRouter для выбора модели (поддерживает будущее расширение роя моделей)
            router = get_model_router()
            model_selection = router.select_model(
                task_type="testing",
                preferred_model=None,
                context={"agent": "test_generator"}
            )
            model = model_selection.model
        
        self.llm = LocalLLM(
            model=model,
            temperature=temperature,
            top_p=0.9
        )

    def generate_tests(
        self,
        plan: str,
        context: str,
        intent_type: str,
        min_test_cases: int = 3,
        max_test_cases: int = 5
    ) -> str:
        """Генерирует pytest тесты на основе плана, контекста и намерения.
        
        Args:
            plan: План реализации задачи
            context: Собранный контекст из RAG/веб-поиска
            intent_type: Тип намерения (create/modify/debug/etc)
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
        
        prompt = self._build_test_generation_prompt(
            plan=plan,
            context=context,
            intent_type=intent_type,
            min_cases=min_test_cases,
            max_cases=max_test_cases
        )
        
        response = self.llm.generate(prompt, num_predict=2048)
        
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
        
        intent_descriptions = {
            "create": "создание новой функции/класса/модуля",
            "modify": "изменение существующего кода",
            "debug": "исправление ошибок",
            "optimize": "оптимизация производительности",
            "explain": "объяснение кода (тесты на документацию)",
            "test": "написание тестов",
            "refactor": "рефакторинг кода"
        }
        
        intent_desc = intent_descriptions.get(intent_type, "выполнение задачи")
        
        context_section = ""
        if context.strip():
            context_section = f"""
Контекст из базы знаний:
{context}
"""
        
        prompt = f"""Ты - эксперт по написанию тестов на Python. Сгенерируй pytest тесты для следующей задачи.

Тип задачи: {intent_desc}

План реализации:
{plan}
{context_section}
Требования к тестам:
1. Используй pytest (import pytest)
2. Напиши минимум {min_cases}, максимум {max_cases} осмысленных тестовых кейсов
3. Тесты должны покрывать:
   - Основной функционал (happy path)
   - Граничные случаи (edge cases)
   - Обработку ошибок (если применимо)
4. Используй понятные имена тестов (test_название_функции_сценарий)
5. Включай assert statements с понятными сообщениями
6. Если нужны фикстуры или моки - используй pytest.fixture и unittest.mock
7. Код должен быть готов к запуску (без заглушек, с правильными импортами)

Верни ТОЛЬКО код тестов на Python, без объяснений и markdown разметки. Начни сразу с import statements.

Код тестов:
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
