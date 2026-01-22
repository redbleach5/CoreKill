"""Единый PromptBuilder для CoderAgent.

Устраняет дублирование промптов и централизует логику построения промптов.
"""
from typing import Optional, Dict, Any, List
from infrastructure.code_retrieval import CodeExample
from infrastructure.code_style import get_code_style_config
from utils.config import get_config
from utils.logger import get_logger
from utils.intent_helpers import get_intent_description

logger = get_logger()


class CoderPromptBuilder:
    """Единый билдер промптов для генерации и исправления кода.
    
    Использует конфигурацию из config.toml для лимитов длины и стиля кода.
    """
    
    def __init__(self) -> None:
        """Инициализация билдера."""
        self.config = get_config()
        self.style_config = get_code_style_config()
        self._load_prompt_limits()
    
    def _load_prompt_limits(self) -> None:
        """Загружает лимиты длины из config.toml."""
        try:
            limits = self.config._config_data.get("prompt_limits", {})
            self.max_tests_length = limits.get("max_tests_length", 2000)
            self.max_tests_length_fix = limits.get("max_tests_length_fix", 1000)
            self.max_context_length = limits.get("max_context_length", 1000)
            self.max_validation_errors_length = limits.get("max_validation_errors_length", 300)
        except Exception as e:
            logger.warning(f"Ошибка загрузки prompt_limits: {e}, используем значения по умолчанию")
            self.max_tests_length = 2000
            self.max_tests_length_fix = 1000
            self.max_context_length = 1000
            self.max_validation_errors_length = 300
    
    def _truncate(self, text: str, max_length: int) -> str:
        """Обрезает текст до максимальной длины.
        
        Args:
            text: Текст для обрезки
            max_length: Максимальная длина
            
        Returns:
            Обрезанный текст
        """
        if len(text) <= max_length:
            return text
        return text[:max_length] + "\n... (truncated)"
    
    def build_generation_prompt(
        self,
        plan: str,
        tests: str,
        context: str,
        intent_type: str,
        user_query: Optional[str] = None,
        examples: Optional[List[CodeExample]] = None
    ) -> str:
        """Строит промпт для генерации кода.
        
        Args:
            plan: План реализации
            tests: Тесты для кода
            context: Контекст из RAG
            intent_type: Тип намерения (create/modify/etc)
            user_query: Оригинальный запрос пользователя
            examples: Few-shot примеры кода
            
        Returns:
            Промпт для генерации кода
        """
        # Обрезаем тесты и контекст
        truncated_tests = self._truncate(tests, self.max_tests_length)
        truncated_context = self._truncate(context, self.max_context_length) if context.strip() else ""
        
        # Описание типа задачи (используем унифицированную функцию)
        intent_desc = get_intent_description(intent_type, format="short") or "выполнить задачу"
        
        # Секция контекста
        context_section = ""
        if truncated_context:
            context_section = f"\nКонтекст из базы знаний:\n{truncated_context}\n"
        
        # Если есть примеры, используем few-shot подход
        if examples:
            examples_str = "\n\n".join(ex.formatted for ex in examples[:3])
            
            task_section = user_query if user_query else plan
            
            return f"""Generate Python code similar in STYLE to these examples:

{examples_str}

---

YOUR TASK:
{task_section}

PLAN:
{plan}

TESTS TO PASS:
```python
{truncated_tests}
```
{context_section}
RULES:
1. Follow the STYLE of the examples above (naming, docstrings, type hints)
2. Use same naming conventions as examples
3. Must pass all tests
4. Include all necessary imports
5. Return ONLY Python code, no explanations

CODE:
"""
        
        # Стандартный промпт без примеров
        style_requirements = self.style_config.get_style_requirements()
        
        prompt = f"""Ты - эксперт по написанию чистого Python кода. Реализуй код, который пройдёт следующие тесты.

Тип задачи: {intent_desc}

План реализации:
{plan}
{context_section}
Тесты, которые должен пройти код:
{truncated_tests}

Требования к коду:
{style_requirements}
10. Код должен проходить ВСЕ предоставленные тесты
11. Код должен быть читаемым и понятным
12. Обрабатывай ошибки там, где это необходимо
13. Импортируй все необходимые модули
14. Не добавляй лишних комментариев в код (только docstrings)

Верни ТОЛЬКО код на Python, без объяснений и markdown разметки. Начни сразу с import statements.

Код:
"""
        return prompt
    
    def build_fix_prompt(
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
        # Обрезаем тесты
        truncated_tests = self._truncate(tests, self.max_tests_length_fix)
        
        # Извлекаем информацию об ошибках
        error_summary = []
        if not validation_results.get("pytest", {}).get("success", True):
            pytest_output = validation_results.get("pytest", {}).get("output", "")
            error_summary.append(f"pytest errors: {self._truncate(pytest_output, self.max_validation_errors_length)}")
        if not validation_results.get("mypy", {}).get("success", True):
            mypy_errors = validation_results.get("mypy", {}).get("errors", "")
            error_summary.append(f"mypy errors: {self._truncate(mypy_errors, self.max_validation_errors_length)}")
        if not validation_results.get("bandit", {}).get("success", True):
            bandit_issues = validation_results.get("bandit", {}).get("issues", "")
            error_summary.append(f"bandit issues: {self._truncate(bandit_issues, self.max_validation_errors_length)}")
        
        errors_context = "\n".join(error_summary) if error_summary else "No specific error details"
        
        prompt = f"""You are an expert Python code fixer. Fix the code according to the specific instructions from Debugger Agent.

Current code (with errors):
```python
{code}
```

Tests:
```python
{truncated_tests}
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


# === Удобная функция для импорта ===

def get_coder_prompt_builder() -> CoderPromptBuilder:
    """Возвращает экземпляр CoderPromptBuilder.
    
    Returns:
        Экземпляр CoderPromptBuilder
    """
    return CoderPromptBuilder()
