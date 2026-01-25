"""Инкрементальный генератор кода с немедленной валидацией.

Реализует Compiler-in-the-Loop подход:
- Разбивает план на функции
- Генерирует каждую функцию отдельно
- Сразу запускает тесты
- Исправляет ошибки пока контекст свежий
- Переходит к следующей функции

Преимущества:
- Ошибка обнаруживается СРАЗУ после генерации функции
- Контекст генерации свежий при исправлении
- Меньше итераций debug-fix-validate

Использование:
    coder = IncrementalCoder(model="qwen2.5-coder:7b")
    async for step in coder.generate_with_feedback(plan, tests, context):
        logger.info(f"Функция {step.function_name}: {'✅' if step.tests_passed else '❌'}")
"""
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, AsyncGenerator, Any, Dict

from infrastructure.local_llm import create_llm_for_stage
from infrastructure.model_router import get_model_router
from utils.logger import get_logger
from utils.config import get_config

logger = get_logger()


@dataclass
class FunctionSpec:
    """Спецификация одной функции из плана."""
    name: str
    signature: str
    description: str
    dependencies: List[str] = field(default_factory=list)


@dataclass
class GenerationStep:
    """Результат одного шага генерации."""
    function_name: str
    code: str
    tests_passed: bool
    error: Optional[str] = None
    fix_attempts: int = 0
    status: str = "completed"  # generating, validating, fixing, passed, failed


class IncrementalCoder:
    """Генерирует код по частям с немедленной валидацией.
    
    Workflow:
    1. Разбивает план на функции
    2. Генерирует каждую функцию отдельно
    3. Сразу запускает тесты
    4. Исправляет ошибки пока контекст свежий
    5. Переходит к следующей функции
    """
    
    MAX_FIX_ATTEMPTS = 3
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.2
    ) -> None:
        """Инициализация инкрементального генератора.
        
        Args:
            model: Модель для генерации кода (если None, выбирается через router)
            temperature: Температура генерации (низкая для точного кода)
        """
        if model is None:
            router = get_model_router()
            model_selection = router.select_model(
                task_type="coding",
                preferred_model=None,
                context={"agent": "incremental_coder"}
            )
            model = model_selection.model
        
        self.model = model
        self.llm = create_llm_for_stage(
            stage="coding",
            model=model,
            temperature=temperature,
            top_p=0.9
        )
        self.config = get_config()
    
    async def generate_with_feedback(
        self,
        plan: str,
        tests: str,
        context: str = "",
        user_query: str = ""
    ) -> AsyncGenerator[GenerationStep, None]:
        """Генерирует код инкрементально с обратной связью.
        
        Args:
            plan: План реализации
            tests: Сгенерированные тесты
            context: Дополнительный контекст
            user_query: Оригинальный запрос пользователя (для уточнения сути задачи)
            
        Yields:
            GenerationStep для каждой функции
        """
        # Разбираем план на функции
        functions = await self._parse_plan_to_functions(plan, user_query)
        
        if not functions:
            logger.warning("⚠️ Не удалось разобрать план на функции, генерирую весь код")
            # Fallback — генерируем весь код как одну функцию
            full_code = await self._generate_full_code(plan, tests, context, user_query)
            yield GenerationStep(
                function_name="main",
                code=full_code,
                tests_passed=True,  # Валидация будет в validator_node
                status="completed"
            )
            return
        
        logger.info(f"📋 Разобрано {len(functions)} функций из плана")
        
        generated_code: List[str] = []
        
        for i, func_spec in enumerate(functions):
            logger.info(f"⚙️ [{i+1}/{len(functions)}] Генерирую: {func_spec.name}")
            
            # Генерируем функцию
            func_code = await self._generate_function(
                func_spec=func_spec,
                existing_code=generated_code,
                tests=tests,
                context=context,
                user_query=user_query
            )
            
            # Сразу валидируем
            step = await self._validate_and_fix(
                func_spec=func_spec,
                func_code=func_code,
                existing_code=generated_code,
                tests=tests,
                user_query=user_query
            )
            
            generated_code.append(step.code)
            yield step
        
        logger.info(f"✅ Генерация завершена: {len(generated_code)} функций")
    
    async def _parse_plan_to_functions(self, plan: str, user_query: str = "") -> List[FunctionSpec]:
        """Извлекает функции из плана через LLM.
        
        Args:
            plan: Текстовый план реализации
            user_query: Оригинальный запрос пользователя (для уточнения намерения)
            
        Returns:
            Список спецификаций функций
        """
        user_request_section = f"\nUSER REQUEST: {user_query}\n" if user_query else ""
        
        prompt = f"""Extract functions from this implementation plan.
{user_request_section}
PLAN:
{plan[:2000]}

Return JSON array with functions to implement:
[
  {{"name": "func_name", "signature": "def func(args) -> type", "description": "what it does", "dependencies": ["other_func"]}},
  ...
]

RULES:
1. Extract only PUBLIC functions that need to be implemented
2. Order by dependencies (independent functions first)
3. Include type hints in signature
4. Maximum 10 functions

JSON:"""
        
        try:
            response = await asyncio.to_thread(
                self.llm.generate, prompt, 1024
            )
            return self._parse_functions_json(response)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка парсинга плана: {e}")
            return []
    
    def _parse_functions_json(self, response: str) -> List[FunctionSpec]:
        """Парсит JSON с функциями.
        
        Args:
            response: Ответ LLM с JSON
            
        Returns:
            Список FunctionSpec
        """
        functions: List[FunctionSpec] = []
        
        try:
            # Ищем JSON массив в ответе
            start = response.find("[")
            end = response.rfind("]") + 1
            
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                
                for item in data:
                    if isinstance(item, dict) and "name" in item:
                        functions.append(FunctionSpec(
                            name=item.get("name", "unknown"),
                            signature=item.get("signature", f"def {item.get('name', 'func')}()"),
                            description=item.get("description", ""),
                            dependencies=item.get("dependencies", [])
                        ))
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"⚠️ Не удалось распарсить JSON функций: {e}")
        
        return functions[:10]  # Максимум 10 функций
    
    async def _generate_function(
        self,
        func_spec: FunctionSpec,
        existing_code: List[str],
        tests: str,
        context: str,
        user_query: str = ""
    ) -> str:
        """Генерирует одну функцию.
        
        Args:
            func_spec: Спецификация функции
            existing_code: Уже сгенерированный код
            tests: Тесты
            context: Контекст
            user_query: Оригинальный запрос пользователя
            
        Returns:
            Код функции
        """
        existing_str = "\n\n".join(existing_code) if existing_code else "# No existing code yet"
        
        # Извлекаем релевантные тесты для этой функции
        relevant_tests = self._extract_relevant_tests(tests, func_spec.name)
        
        user_request_section = f"\nUSER REQUEST: {user_query}\n" if user_query else ""
        
        prompt = f"""Generate ONLY the function: {func_spec.name}
{user_request_section}

SIGNATURE: {func_spec.signature}
DESCRIPTION: {func_spec.description}

ALREADY GENERATED:
```python
{existing_str[:1500]}
```

TESTS FOR THIS FUNCTION:
```python
{relevant_tests[:800]}
```

CONTEXT: {context[:500]}

RULES:
1. Generate ONLY this single function
2. Must work with existing code (use already defined functions/classes)
3. Must pass the tests
4. Include type hints and docstring
5. Python 3.12+ syntax

CODE:"""
        
        response = await asyncio.to_thread(
            self.llm.generate, prompt, self.config.llm_tokens_code
        )
        
        return self._extract_function_code(response, func_spec.name)
    
    def _extract_relevant_tests(self, tests: str, function_name: str) -> str:
        """Извлекает тесты относящиеся к конкретной функции.
        
        Args:
            tests: Все тесты
            function_name: Имя функции
            
        Returns:
            Релевантные тесты
        """
        relevant_lines: List[str] = []
        in_relevant_test = False
        indent_level = 0
        
        for line in tests.split("\n"):
            stripped = line.strip()
            
            # Начало теста
            if stripped.startswith("def test_") or stripped.startswith("async def test_"):
                # Проверяем связь с функцией
                if function_name.lower() in stripped.lower():
                    in_relevant_test = True
                    indent_level = len(line) - len(line.lstrip())
                    relevant_lines.append(line)
                else:
                    in_relevant_test = False
            elif in_relevant_test:
                # Внутри релевантного теста
                current_indent = len(line) - len(line.lstrip()) if line.strip() else indent_level + 1
                if current_indent > indent_level or not line.strip():
                    relevant_lines.append(line)
                else:
                    in_relevant_test = False
        
        # Если не нашли релевантные тесты, возвращаем первые тесты
        if not relevant_lines:
            return tests[:500]
        
        return "\n".join(relevant_lines)
    
    def _extract_function_code(self, response: str, function_name: str) -> str:
        """Извлекает код функции из ответа LLM.
        
        Args:
            response: Ответ LLM
            function_name: Имя ожидаемой функции
            
        Returns:
            Код функции
        """
        # Убираем markdown блоки
        code = response
        if "```python" in code:
            start = code.find("```python") + 9
            end = code.find("```", start)
            if end > start:
                code = code[start:end]
        elif "```" in code:
            start = code.find("```") + 3
            end = code.find("```", start)
            if end > start:
                code = code[start:end]
        
        code = code.strip()
        
        # Проверяем что код начинается с def/async def
        if not code.startswith("def ") and not code.startswith("async def "):
            # Пытаемся найти определение функции
            match = re.search(r'(async\s+)?def\s+\w+\s*\(', code)
            if match:
                code = code[match.start():]
        
        return code
    
    async def _validate_and_fix(
        self,
        func_spec: FunctionSpec,
        func_code: str,
        existing_code: List[str],
        tests: str,
        user_query: str = ""
    ) -> GenerationStep:
        """Валидирует и исправляет функцию.
        
        Args:
            func_spec: Спецификация функции
            func_code: Код функции
            existing_code: Существующий код
            tests: Тесты
            
        Returns:
            GenerationStep с результатом
        """
        # Импортируем валидатор
        from utils.validation import validate_code_quick
        
        for attempt in range(self.MAX_FIX_ATTEMPTS):
            full_code = "\n\n".join(existing_code + [func_code])
            
            # Быстрая валидация
            result = await asyncio.to_thread(
                validate_code_quick, full_code, tests
            )
            
            if result.get("passed", False):
                logger.info(f"✅ {func_spec.name}: валидация прошла")
                return GenerationStep(
                    function_name=func_spec.name,
                    code=func_code,
                    tests_passed=True,
                    fix_attempts=attempt,
                    status="passed"
                )
            
            error = result.get("error", "Unknown error")
            logger.warning(f"❌ {func_spec.name} попытка {attempt+1}: {error[:100]}")
            
            # Исправляем с контекстом ошибки (контекст свежий!)
            func_code = await self._fix_function(func_spec, func_code, error, user_query)
        
        # Не удалось исправить за MAX_FIX_ATTEMPTS попыток
        return GenerationStep(
            function_name=func_spec.name,
            code=func_code,
            tests_passed=False,
            error=result.get("error", "Validation failed"),
            fix_attempts=self.MAX_FIX_ATTEMPTS,
            status="failed"
        )
    
    async def _fix_function(
        self,
        func_spec: FunctionSpec,
        func_code: str,
        error: str,
        user_query: str = ""
    ) -> str:
        """Исправляет функцию на основе ошибки.
        
        Args:
            func_spec: Спецификация функции
            func_code: Текущий код функции
            error: Текст ошибки
            user_query: Оригинальный запрос пользователя (для контекста)
            
        Returns:
            Исправленный код функции
        """
        user_request_section = f"\nUSER REQUEST: {user_query}\n" if user_query else ""
        
        prompt = f"""Fix this Python function based on the error.
{user_request_section}
FUNCTION: {func_spec.name}

CURRENT CODE:
```python
{func_code}
```

ERROR:
{error[:500]}

Fix ONLY the error. Keep the signature, docstring, and overall structure.
Return ONLY the fixed function code.

FIXED CODE:"""
        
        response = await asyncio.to_thread(
            self.llm.generate, prompt, self.config.llm_tokens_code
        )
        
        return self._extract_function_code(response, func_spec.name)
    
    async def _generate_full_code(
        self,
        plan: str,
        tests: str,
        context: str,
        user_query: str = ""
    ) -> str:
        """Генерирует весь код (fallback когда не удалось разбить на функции).
        
        Args:
            plan: План реализации
            tests: Тесты
            context: Контекст
            user_query: Оригинальный запрос пользователя
            
        Returns:
            Полный код
        """
        user_request_section = f"\nUSER REQUEST: {user_query}\n" if user_query else ""
        
        prompt = f"""Generate Python code based on this plan.
{user_request_section}
PLAN:
{plan[:1500]}

TESTS:
```python
{tests[:1000]}
```

CONTEXT: {context[:500]}

RULES:
1. Generate complete, working code
2. Must pass the tests
3. Include type hints and docstrings
4. Python 3.12+ syntax

CODE:"""
        
        response = await asyncio.to_thread(
            self.llm.generate, prompt, self.config.llm_tokens_code
        )
        
        # Извлекаем код из ответа
        code = response
        if "```python" in code:
            start = code.find("```python") + 9
            end = code.find("```", start)
            if end > start:
                code = code[start:end]
        
        return code.strip()
