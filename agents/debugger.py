"""Агент для анализа ошибок и генерации инструкций по исправлению кода."""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from infrastructure.local_llm import LocalLLM
from utils.logger import get_logger
from infrastructure.model_router import get_model_router


logger = get_logger()


@dataclass
class DebugResult:
    """Результат анализа ошибок от Debugger Agent."""
    error_summary: str  # Краткое описание ошибок (RU)
    root_cause: str  # Основная причина ошибок (RU)
    fix_instructions: str  # Конкретные инструкции для Coder (EN)
    confidence: float  # Уверенность в диагнозе (0.0-1.0)
    error_type: str  # "pytest", "mypy", "bandit", "syntax", "multiple"


class DebuggerAgent:
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
        if model is None:
            router = get_model_router()
            model_selection = router.select_model(
                task_type="coding",  # Debugger использует ту же модель что и Coder
                preferred_model=None,
                context={"agent": "debugger"}
            )
            model = model_selection.model
        
        self.llm = LocalLLM(
            model=model,
            temperature=temperature,
            top_p=0.9
        )
    
    def analyze_errors(
        self,
        validation_results: Dict[str, Any],
        code: str,
        tests: str,
        task: str
    ) -> DebugResult:
        """Анализирует ошибки валидации и генерирует инструкции по исправлению.
        
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
        debug_result = self._parse_analysis_response(
            response=analysis_response,
            error_details=error_details,
            error_type=error_type
        )
        
        logger.info(
            f"✅ Анализ завершён. Тип ошибки: {debug_result.error_type}, "
            f"уверенность: {debug_result.confidence:.2f}"
        )
        
        return debug_result
    
    def _extract_error_details(
        self,
        validation_results: Dict[str, Any]
    ) -> Dict[str, str]:
        """Извлекает детали ошибок из результатов валидации.
        
        Args:
            validation_results: Результаты валидации
            
        Returns:
            Словарь с деталями ошибок для каждого валидатора
        """
        details: Dict[str, str] = {}
        
        # Ошибки pytest
        if not validation_results.get("pytest", {}).get("success", True):
            pytest_output = validation_results.get("pytest", {}).get("output", "")
            # Извлекаем traceback и основные ошибки
            lines = pytest_output.split("\n")
            error_lines: List[str] = []
            in_traceback = False
            
            for line in lines:
                if "FAILED" in line or "ERROR" in line:
                    error_lines.append(line)
                elif "Traceback" in line:
                    in_traceback = True
                    error_lines.append(line)
                elif in_traceback and line.strip() and not line.startswith(" "):
                    error_lines.append(line)
                    if "AssertionError" in line or ":" in line:
                        in_traceback = False
            
            details["pytest"] = "\n".join(error_lines[-20:])  # Последние 20 строк
        else:
            details["pytest"] = ""
        
        # Ошибки mypy
        if not validation_results.get("mypy", {}).get("success", True):
            mypy_errors = validation_results.get("mypy", {}).get("errors", "")
            # Берем первые несколько ошибок
            error_lines = mypy_errors.split("\n")[:15]
            details["mypy"] = "\n".join(error_lines)
        else:
            details["mypy"] = ""
        
        # Проблемы bandit
        if not validation_results.get("bandit", {}).get("success", True):
            bandit_issues = validation_results.get("bandit", {}).get("issues", "")
            # Берем важные части
            lines = bandit_issues.split("\n")
            issue_lines = [line for line in lines if "Issue:" in line or "Severity:" in line][:10]
            details["bandit"] = "\n".join(issue_lines)
        else:
            details["bandit"] = ""
        
        return details
    
    def _determine_error_type(
        self,
        validation_results: Dict[str, Any]
    ) -> str:
        """Определяет тип основной ошибки.
        
        Args:
            validation_results: Результаты валидации
            
        Returns:
            Тип ошибки: "pytest", "mypy", "bandit", "multiple"
        """
        errors: List[str] = []
        
        if not validation_results.get("pytest", {}).get("success", True):
            errors.append("pytest")
        if not validation_results.get("mypy", {}).get("success", True):
            errors.append("mypy")
        if not validation_results.get("bandit", {}).get("success", True):
            errors.append("bandit")
        
        if len(errors) > 1:
            return "multiple"
        elif len(errors) == 1:
            return errors[0]
        else:
            return "unknown"
    
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
        error_sections = []
        
        if error_details.get("pytest"):
            error_sections.append(f"pytest ошибки:\n{error_details['pytest']}")
        if error_details.get("mypy"):
            error_sections.append(f"mypy ошибки:\n{error_details['mypy']}")
        if error_details.get("bandit"):
            error_sections.append(f"bandit проблемы:\n{error_details['bandit']}")
        
        errors_text = "\n\n".join(error_sections)
        
        prompt = f"""Ты - эксперт по отладке Python кода. Проанализируй ошибки и создай конкретные инструкции для исправления.

Исходная задача: {task}

Текущий код (с ошибками):
```python
{code[:1500]}
```

Тесты:
```python
{tests[:1000]}
```

Ошибки валидации:
{errors_text}

Проанализируй и ответь строго в следующем формате:

ОПИСАНИЕ_ОШИБОК:
[Краткое описание найденных ошибок на русском языке]

ПРИЧИНА:
[Основная причина ошибок на русском языке. Объясни почему код не работает.]

ИНСТРУКЦИИ_ДЛЯ_ИСПРАВЛЕНИЯ:
[Конкретные, атомарные инструкции на английском языке для Coder Agent. 
Каждая инструкция должна быть чёткой и выполнимой. 
Формат: "Fix X by doing Y" или "Add Z to function A" или "Change type annotation from X to Y"]
[ВАЖНО: Инструкции должны быть конкретными и направленными на исправление конкретных ошибок из валидации]

УВЕРЕННОСТЬ: [0.0-1.0]
[Оценка уверенности в диагнозе]
"""
        return prompt
    
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
