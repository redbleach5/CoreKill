"""Агент для анализа ошибок и генерации инструкций по исправлению кода.

Поддерживает два режима работы:
- Structured Output (Pydantic): generate_structured() с гарантированным форматом
- Legacy: ручной парсинг текста (fallback)

Режим выбирается через config.toml:
    [structured_output]
    enabled_agents = ["intent", "debugger"]
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from infrastructure.local_llm import create_llm_for_stage
from utils.logger import get_logger
from infrastructure.model_router import get_model_router
from utils.structured_helpers import generate_with_fallback, is_structured_output_enabled
from models.agent_responses import DebugResponse, ErrorType
from agents.base import BaseAgent


logger = get_logger()


@dataclass
class DebugResult:
    """Результат анализа ошибок от Debugger Agent."""
    error_summary: str  # Краткое описание ошибок (RU)
    root_cause: str  # Основная причина ошибок (RU)
    fix_instructions: str  # Конкретные инструкции для Coder (EN)
    confidence: float  # Уверенность в диагнозе (0.0-1.0)
    error_type: str  # "pytest", "mypy", "bandit", "syntax", "multiple"


class DebuggerAgent(BaseAgent):
    """Агент для анализа ошибок валидации и генерации инструкций по исправлению.
    
    Анализирует результаты валидации (pytest, mypy, bandit), определяет причину ошибок
    и генерирует конкретные инструкции для Coder Agent по исправлению кода.
    """
    
    def __init__(self, model: Optional[str] = None, temperature: float = 0.2) -> None:
        """Инициализация Debugger Agent.
        
        Args:
            model: Модель для анализа ошибок (если None, выбирается из config)
            temperature: Температура генерации (низкая для точности анализа)
        """
        # Инициализация базового класса (LLM создаётся автоматически)
        super().__init__(
            model=model,
            temperature=temperature,
            stage="debug"
        )
    
    def analyze_errors(
        self,
        validation_results: Dict[str, Any],
        code: str,
        tests: str,
        task: str
    ) -> DebugResult:
        """Анализирует ошибки валидации и генерирует инструкции по исправлению.
        
        Использует structured output если включён в config.toml,
        иначе fallback на legacy парсинг.
        
        Args:
            validation_results: Результаты валидации (pytest, mypy, bandit)
            code: Исходный код с ошибками
            tests: Тесты для кода
            task: Исходная задача пользователя
            
        Returns:
            DebugResult с анализом ошибок и инструкциями для исправления
        """
        logger.info("🐞 Анализирую ошибки валидации...")
        
        # Извлекаем детали ошибок
        error_details = self._extract_error_details(validation_results)
        
        # Определяем тип ошибки
        error_type = self._determine_error_type(validation_results)
        
        # Проверяем, включён ли structured output для debugger
        if is_structured_output_enabled("debugger"):
            debug_result = self._analyze_structured(
                task=task,
                code=code,
                tests=tests,
                error_details=error_details,
                error_type=error_type
            )
        else:
            debug_result = self._analyze_legacy(
                task=task,
                code=code,
                tests=tests,
                error_details=error_details,
                error_type=error_type
            )
        
        logger.info(
            f"✅ Анализ завершён. Тип ошибки: {debug_result.error_type}, "
            f"уверенность: {debug_result.confidence:.2f}"
        )
        
        return debug_result
    
    def _analyze_structured(
        self,
        task: str,
        code: str,
        tests: str,
        error_details: Dict[str, str],
        error_type: str
    ) -> DebugResult:
        """Анализирует ошибки через structured output (Pydantic).
        
        Args:
            task: Исходная задача
            code: Код с ошибками
            tests: Тесты
            error_details: Детали ошибок
            error_type: Тип ошибки
            
        Returns:
            DebugResult с анализом ошибок
        """
        error_sections = []
        if error_details.get("pytest"):
            error_sections.append(f"pytest errors:\n{error_details['pytest']}")
        if error_details.get("mypy"):
            error_sections.append(f"mypy errors:\n{error_details['mypy']}")
        if error_details.get("bandit"):
            error_sections.append(f"bandit issues:\n{error_details['bandit']}")
        
        errors_text = "\n\n".join(error_sections)
        
        prompt = f"""Analyze Python code errors and provide fix instructions.

TASK: {task}

CODE (with errors):
```python
{code[:1500]}
```

TESTS:
```python
{tests[:1000]}
```

VALIDATION ERRORS:
{errors_text}

ERROR TYPES: syntax, runtime, logic, type, import, test
- syntax: SyntaxError, IndentationError
- runtime: RuntimeError, ValueError, KeyError
- logic: Wrong output, incorrect algorithm
- type: Type mismatch, wrong annotations
- import: ModuleNotFoundError, ImportError
- test: AssertionError, test failure

Analyze errors and provide:
1. error_type: one of the types above
2. error_location: file:line or function name
3. root_cause: brief explanation of why code fails
4. fix_instructions: specific steps to fix (in English, actionable)
5. confidence: 0.0-1.0"""

        from utils.config import get_config
        config = get_config()
        
        # Используем generate_with_fallback
        response = generate_with_fallback(
            llm=self.llm,
            prompt=prompt,
            response_model=DebugResponse,
            fallback_fn=lambda: self._analyze_legacy_response(
                task, code, tests, error_details, error_type
            ),
            agent_name="debugger",
            num_predict=config.llm_tokens_debug
        )
        
        # Конвертируем DebugResponse -> DebugResult
        resp_error_type = response.error_type if isinstance(response.error_type, str) else response.error_type.value
        
        return DebugResult(
            error_summary=f"{resp_error_type} error at {response.error_location}",
            root_cause=response.root_cause,
            fix_instructions=response.fix_instructions,
            confidence=response.confidence,
            error_type=error_type  # Используем наш определённый тип (pytest/mypy/bandit)
        )
    
    def _analyze_legacy_response(
        self,
        task: str,
        code: str,
        tests: str,
        error_details: Dict[str, str],
        error_type: str
    ) -> DebugResponse:
        """Legacy анализ, возвращает DebugResponse для совместимости с fallback.
        
        Используется как fallback для generate_with_fallback.
        """
        result = self._analyze_legacy(task, code, tests, error_details, error_type)
        
        # Маппинг error_type на ErrorType enum
        error_type_map = {
            "pytest": "test",
            "mypy": "type",
            "bandit": "runtime",  # security issues → runtime
            "syntax": "syntax",
            "multiple": "logic"
        }
        mapped_type = error_type_map.get(result.error_type, "logic")
        
        return DebugResponse(
            error_type=ErrorType(mapped_type),
            error_location="unknown",
            root_cause=result.root_cause,
            fix_instructions=result.fix_instructions,
            confidence=result.confidence
        )
    
    def _analyze_legacy(
        self,
        task: str,
        code: str,
        tests: str,
        error_details: Dict[str, str],
        error_type: str
    ) -> DebugResult:
        """Legacy анализ через ручной парсинг текста.
        
        Args:
            task: Исходная задача
            code: Код с ошибками
            tests: Тесты
            error_details: Детали ошибок
            error_type: Тип ошибки
            
        Returns:
            DebugResult с анализом ошибок
        """
        # Строим промпт для анализа
        analysis_prompt = self._build_analysis_prompt(
            task=task,
            code=code,
            tests=tests,
            error_details=error_details,
            error_type=error_type
        )
        
        # Получаем анализ от LLM
        from utils.config import get_config
        config = get_config()
        analysis_response = self.llm.generate(analysis_prompt, num_predict=config.llm_tokens_debug)
        
        # Парсим ответ
        return self._parse_analysis_response(
            response=analysis_response,
            error_details=error_details,
            error_type=error_type
        )
    
    # Методы _extract_error_details и _determine_error_type теперь в BaseAgent
    
    def _build_analysis_prompt(
        self,
        task: str,
        code: str,
        tests: str,
        error_details: Dict[str, str],
        error_type: str
    ) -> str:
        """Строит промпт для анализа ошибок.
        
        Args:
            task: Исходная задача
            code: Код с ошибками
            tests: Тесты
            error_details: Детали ошибок
            error_type: Тип ошибки
            
        Returns:
            Промпт для LLM
        """
        from infrastructure.prompt_templates import build_debug_analysis_prompt
        return build_debug_analysis_prompt(
            task=task,
            code=code,
            tests=tests,
            error_details=error_details,
            error_type=error_type
        )
    
    def _parse_analysis_response(
        self,
        response: str,
        error_details: Dict[str, str],
        error_type: str
    ) -> DebugResult:
        """Парсит ответ модели и создаёт DebugResult.
        
        Args:
            response: Ответ модели
            error_details: Детали ошибок
            error_type: Тип ошибки
            
        Returns:
            DebugResult
        """
        # Инициализируем значениями по умолчанию
        error_summary = "Ошибки валидации найдены"
        root_cause = "Необходимо исправить код"
        fix_instructions = "Fix the code to pass validation"
        confidence = 0.5
        
        lines = response.split("\n")
        current_section = None
        
        for line in lines:
            stripped = line.strip()
            
            # Определяем секцию
            if "ОПИСАНИЕ_ОШИБОК:" in stripped or "ОПИСАНИЕ:" in stripped:
                current_section = "summary"
                continue
            elif "ПРИЧИНА:" in stripped or "ПРИЧИНА_ОШИБКИ:" in stripped:
                current_section = "cause"
                continue
            elif "ИНСТРУКЦИИ_ДЛЯ_ИСПРАВЛЕНИЯ:" in stripped or "ИНСТРУКЦИИ:" in stripped:
                current_section = "instructions"
                continue
            elif "УВЕРЕННОСТЬ:" in stripped:
                # Парсим уверенность
                try:
                    value = float(stripped.split(":")[-1].strip())
                    confidence = max(0.0, min(1.0, value))
                except (ValueError, IndexError):
                    pass
                current_section = None
                continue
            
            # Собираем содержимое секций
            if current_section == "summary" and stripped and not stripped.startswith("["):
                if not error_summary or error_summary == "Ошибки валидации найдены":
                    error_summary = stripped
                else:
                    error_summary += "\n" + stripped
            
            elif current_section == "cause" and stripped and not stripped.startswith("["):
                if not root_cause or root_cause == "Необходимо исправить код":
                    root_cause = stripped
                else:
                    root_cause += "\n" + stripped
            
            elif current_section == "instructions" and stripped and not stripped.startswith("["):
                if not fix_instructions or fix_instructions == "Fix the code to pass validation":
                    fix_instructions = stripped
                else:
                    fix_instructions += "\n" + stripped
        
        # Если не удалось распарсить, создаём базовые значения на основе error_details
        if error_summary == "Ошибки валидации найдены":
            errors_found = []
            if error_details.get("pytest"):
                errors_found.append("pytest тесты не проходят")
            if error_details.get("mypy"):
                errors_found.append("mypy нашёл ошибки типизации")
            if error_details.get("bandit"):
                errors_found.append("bandit нашёл проблемы безопасности")
            error_summary = "; ".join(errors_found) if errors_found else "Ошибки валидации"
        
        if fix_instructions == "Fix the code to pass validation":
            if error_details.get("pytest"):
                fix_instructions = "Fix the code to make all pytest tests pass"
            elif error_details.get("mypy"):
                fix_instructions = "Fix type annotations to satisfy mypy strict mode"
            elif error_details.get("bandit"):
                fix_instructions = "Fix security issues identified by bandit"
            else:
                fix_instructions = "Fix the code to pass all validation checks"
        
        return DebugResult(
            error_summary=error_summary.strip(),
            root_cause=root_cause.strip(),
            fix_instructions=fix_instructions.strip(),
            confidence=confidence,
            error_type=error_type
        )
