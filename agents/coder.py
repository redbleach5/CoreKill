"""Агент для генерации кода по тестам и плану (TDD)."""
from typing import Optional, Dict, Any
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


class CoderAgent:
    """Агент для генерации рабочего кода, который должен пройти сгенерированные тесты.
    
    Следует TDD-подходу: код генерируется ПОСЛЕ тестов.
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.25) -> None:
        """Инициализация агента генерации кода.
        
        Args:
            model: Модель для генерации кода (если None, выбирается из config)
            temperature: Температура генерации (0.15-0.35 по правилам)
        """
        if model is None:
            # Используем ModelRouter для выбора модели (поддерживает будущее расширение роя моделей)
            router = get_model_router()
            model_selection = router.select_model(
                task_type="coding",
                preferred_model=None,
                context={"agent": "coder"}
            )
            model = model_selection.model
        
        self.llm = LocalLLM(
            model=model,
            temperature=temperature,
            top_p=0.9
        )

    def generate_code(
        self,
        plan: str,
        tests: str,
        context: str,
        intent_type: str
    ) -> str:
        """Генерирует рабочий код на основе тестов, плана и контекста.
        
        Args:
            plan: План реализации задачи
            tests: Сгенерированные pytest тесты
            context: Собранный контекст из RAG/веб-поиска
            intent_type: Тип намерения (create/modify/debug/etc)
            
        Returns:
            Строка с полным кодом. Пустая строка в случае ошибки.
        """
        logger.info(f"💻 Генерирую код для намерения: {intent_type}")
        
        # Не генерируем код для приветствий
        if intent_type == "greeting":
            logger.info("ℹ️ Пропущена генерация кода для приветствия")
            return ""
        
        prompt = self._build_code_generation_prompt(
            plan=plan,
            tests=tests,
            context=context,
            intent_type=intent_type
        )
        
        response = self.llm.generate(prompt, num_predict=4096)
        
        # Очищаем и валидируем сгенерированный код
        cleaned_code = self._clean_code(response)
        
        if cleaned_code:
            logger.info(f"✅ Сгенерирован код (размер: {len(cleaned_code)} символов)")
        else:
            logger.warning("⚠️ Не удалось сгенерировать валидный код")
        
        return cleaned_code

    def fix_code(
        self,
        code: str,
        instructions: str,
        tests: str,
        validation_results: Dict[str, Any]
    ) -> str:
        """Исправляет код по инструкциям от Debugger Agent.
        
        Args:
            code: Исходный код с ошибками
            instructions: Конкретные инструкции от Debugger Agent (EN)
            tests: Тесты для кода
            validation_results: Результаты валидации с ошибками
            
        Returns:
            Исправленный код. Пустая строка в случае ошибки.
        """
        logger.info("🔧 Исправляю код по инструкциям от Debugger...")
        
        if not code.strip() or not instructions.strip():
            logger.warning("⚠️ Пустой код или инструкции")
            return code
        
        prompt = self._build_fix_prompt(
            code=code,
            instructions=instructions,
            tests=tests,
            validation_results=validation_results
        )
        
        response = self.llm.generate(prompt, num_predict=4096)
        
        # Очищаем исправленный код
        fixed_code = self._clean_code(response)
        
        if fixed_code:
            logger.info(f"✅ Код исправлен (размер: {len(fixed_code)} символов)")
        else:
            logger.warning("⚠️ Не удалось исправить код, возвращаю исходный")
            fixed_code = code
        
        return fixed_code

    def _build_fix_prompt(
        self,
        code: str,
        instructions: str,
        tests: str,
        validation_results: Dict[str, Any]
    ) -> str:
        """Строит промпт для исправления кода.
        
        Args:
            code: Исходный код с ошибками
            instructions: Инструкции от Debugger Agent
            tests: Тесты
            validation_results: Результаты валидации
            
        Returns:
            Промпт для исправления кода
        """
        # Извлекаем информацию об ошибках для контекста
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
1. Follow the fix instructions EXACTLY - they are specific and targeted
2. Make MINIMAL changes - only fix what is mentioned in instructions
3. Do NOT rewrite the entire code - only fix the specific issues
4. Keep all existing functionality that was working
5. Maintain type hints and docstrings
6. Ensure the code passes all tests after fixing
7. Return ONLY the fixed Python code, no explanations, no markdown

Fixed code:
"""
        return prompt

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
   Формат: \"\"\"Описание функции.
   
   Args:
       param: Описание параметра.
   
   Returns:
       Описание возвращаемого значения.
   \"\"\"
4. Следуй PEP8 и лучшим практикам Python
5. Код должен быть читаемым и понятным
6. Обрабатывай ошибки там, где это необходимо
7. Используй понятные имена переменных (snake_case)
8. Не добавляй лишних комментариев в код (только docstrings)
9. Импортируй все необходимые модули

Верни ТОЛЬКО код на Python, без объяснений и markdown разметки. Начни сразу с import statements.

Код:
"""
        return prompt

    def _clean_code(self, raw_code: str) -> str:
        """Очищает сгенерированный код от лишних элементов.
        
        Args:
            raw_code: Сырой код от модели
            
        Returns:
            Очищенный код
        """
        if not raw_code:
            return ""
        
        lines = raw_code.split("\n")
        cleaned_lines: list[str] = []
        
        # Убираем markdown блоки кода
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
                # Ждём начала реального кода (импорт, def, class)
                if (stripped.startswith("import") or 
                    stripped.startswith("from") or 
                    stripped.startswith("def ") or 
                    stripped.startswith("class ") or
                    stripped.startswith("@") or
                    stripped.startswith("#")):
                    skip_until_code = False
                    cleaned_lines.append(line)
                continue
            
            # Пропускаем строки с объяснениями в начале
            if not cleaned_lines and (not stripped or stripped.lower().startswith("вот")):
                continue
            
            cleaned_lines.append(line)
        
        cleaned = "\n".join(cleaned_lines).strip()
        
        # Убеждаемся что есть хотя бы def или class
        if "def " not in cleaned and "class " not in cleaned:
            logger.warning("⚠️ В сгенерированном коде не найдено функций или классов")
            return ""
        
        return cleaned
