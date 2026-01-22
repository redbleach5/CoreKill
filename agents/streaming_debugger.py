"""Стриминговая версия агента отладки.

Обеспечивает real-time стриминг:
- <think> блоков reasoning моделей
- Анализа ошибок по мере генерации
- Возможность прерывания
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, AsyncGenerator
from infrastructure.local_llm import create_llm_for_stage
from infrastructure.reasoning_stream import get_reasoning_stream_manager
from infrastructure.reasoning_utils import is_reasoning_response
from utils.logger import get_logger
from utils.config import get_config
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


class StreamingDebuggerAgent:
    """Агент для анализа ошибок с real-time стримингом.
    
    Расширяет функциональность DebuggerAgent:
    - Real-time стриминг <think> блоков (особенно полезно для reasoning моделей)
    - Real-time стриминг анализа
    - Возможность прерывания
    """
    
    def __init__(
        self, 
        model: Optional[str] = None, 
        temperature: float = 0.2
    ) -> None:
        """Инициализация агента.
        
        Args:
            model: Модель (если None, выбирается автоматически)
            temperature: Температура (низкая для точности)
        """
        if model is None:
            router = get_model_router()
            model_selection = router.select_model(
                task_type="coding",
                preferred_model=None,
                context={"agent": "streaming_debugger"}
            )
            model = model_selection.model
        
        self.model = model
        self.temperature = temperature
        self.llm = create_llm_for_stage(
            stage="debug",
            model=model,
            temperature=temperature,
            top_p=0.9
        )
        self.reasoning_manager = get_reasoning_stream_manager()
        self._interrupted = False
    
    def interrupt(self) -> None:
        """Прерывает текущий анализ."""
        self._interrupted = True
        self.reasoning_manager.interrupt()
        logger.info("⏹️ Анализ ошибок прерван")
    
    def reset(self) -> None:
        """Сбрасывает состояние агента."""
        self._interrupted = False
        self.reasoning_manager.reset()
    
    async def analyze_errors_stream(
        self,
        validation_results: Dict[str, Any],
        code: str,
        tests: str,
        task: str,
        stage: str = "debugging"
    ) -> AsyncGenerator[tuple[str, Any], None]:
        """Анализирует ошибки с real-time стримингом.
        
        Args:
            validation_results: Результаты валидации (pytest, mypy, bandit)
            code: Код с ошибками
            tests: Тесты
            task: Исходная задача
            stage: Этап workflow
            
        Yields:
            tuple[event_type, data]:
                - ("thinking", sse_event) — SSE событие для <think> блока
                - ("analysis_chunk", chunk) — чанк анализа
                - ("done", DebugResult) — финальный результат
        """
        logger.info("🐞 Стриминг анализа ошибок...")
        
        self.reset()
        
        # Извлекаем детали ошибок
        error_details = self._extract_error_details(validation_results)
        error_type = self._determine_error_type(validation_results)
        
        # Строим промпт
        prompt = self._build_analysis_prompt(
            task=task,
            code=code,
            tests=tests,
            error_details=error_details,
            error_type=error_type
        )
        
        config = get_config()
        analysis_buffer = ""
        full_response = ""
        
        try:
            async for event_type, data in self.reasoning_manager.stream_from_llm(
                llm=self.llm,
                prompt=prompt,
                stage=stage,
                num_predict=config.llm_tokens_debug
            ):
                if self._interrupted:
                    logger.info("⏹️ Анализ прерван")
                    break
                
                if event_type == "thinking":
                    yield ("thinking", data)
                elif event_type == "content":
                    analysis_buffer += data
                    yield ("analysis_chunk", data)
                elif event_type == "done":
                    full_response = data
            
            # Парсим результат
            response_to_parse = full_response if full_response else analysis_buffer
            debug_result = self._parse_analysis_response(
                response=response_to_parse,
                error_details=error_details,
                error_type=error_type
            )
            
            logger.info(
                f"✅ Анализ завершён. Тип: {debug_result.error_type}, "
                f"уверенность: {debug_result.confidence:.2f}"
            )
            
            yield ("done", debug_result)
            
        except Exception as e:
            logger.error(f"❌ Ошибка стриминга анализа: {e}", error=e)
            # Возвращаем базовый результат
            yield ("done", DebugResult(
                error_summary="Ошибка анализа",
                root_cause=str(e),
                fix_instructions="Fix the code to pass validation",
                confidence=0.0,
                error_type=error_type
            ))
    
    # === Синхронный метод для обратной совместимости ===
    
    def analyze_errors(
        self,
        validation_results: Dict[str, Any],
        code: str,
        tests: str,
        task: str
    ) -> DebugResult:
        """Синхронный анализ ошибок (для обратной совместимости)."""
        from agents.debugger import DebuggerAgent
        
        sync_agent = DebuggerAgent(
            model=self.model,
            temperature=self.temperature
        )
        return sync_agent.analyze_errors(validation_results, code, tests, task)  # type: ignore[return-value]
    
    # === Приватные методы ===
    
    def _extract_error_details(
        self,
        validation_results: Dict[str, Any]
    ) -> Dict[str, str]:
        """Извлекает детали ошибок из результатов валидации."""
        details: Dict[str, str] = {}
        
        # pytest
        if not validation_results.get("pytest", {}).get("success", True):
            pytest_output = validation_results.get("pytest", {}).get("output", "")
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
            
            details["pytest"] = "\n".join(error_lines[-20:])
        else:
            details["pytest"] = ""
        
        # mypy
        if not validation_results.get("mypy", {}).get("success", True):
            mypy_errors = validation_results.get("mypy", {}).get("errors", "")
            error_lines = mypy_errors.split("\n")[:15]
            details["mypy"] = "\n".join(error_lines)
        else:
            details["mypy"] = ""
        
        # bandit
        if not validation_results.get("bandit", {}).get("success", True):
            bandit_issues = validation_results.get("bandit", {}).get("issues", "")
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
        """Определяет тип основной ошибки."""
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
        """Строит промпт для анализа ошибок."""
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
        """Парсит ответ модели и создаёт DebugResult."""
        # Если был reasoning ответ — извлекаем основной контент
        if is_reasoning_response(response):
            from infrastructure.reasoning_utils import parse_reasoning_response
            parsed = parse_reasoning_response(response)
            response = parsed.answer
        
        error_summary = "Ошибки валидации найдены"
        root_cause = "Необходимо исправить код"
        fix_instructions = "Fix the code to pass validation"
        confidence = 0.5
        
        lines = response.split("\n")
        current_section = None
        
        for line in lines:
            stripped = line.strip()
            
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
                try:
                    value = float(stripped.split(":")[-1].strip())
                    confidence = max(0.0, min(1.0, value))
                except (ValueError, IndexError):
                    pass
                current_section = None
                continue
            
            if current_section == "summary" and stripped and not stripped.startswith("["):
                if error_summary == "Ошибки валидации найдены":
                    error_summary = stripped
                else:
                    error_summary += "\n" + stripped
            
            elif current_section == "cause" and stripped and not stripped.startswith("["):
                if root_cause == "Необходимо исправить код":
                    root_cause = stripped
                else:
                    root_cause += "\n" + stripped
            
            elif current_section == "instructions" and stripped and not stripped.startswith("["):
                if fix_instructions == "Fix the code to pass validation":
                    fix_instructions = stripped
                else:
                    fix_instructions += "\n" + stripped
        
        # Fallback на основе error_details
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
        
        return DebugResult(
            error_summary=error_summary.strip(),
            root_cause=root_cause.strip(),
            fix_instructions=fix_instructions.strip(),
            confidence=confidence,
            error_type=error_type
        )


# === Factory функция ===

def get_streaming_debugger_agent(
    model: Optional[str] = None,
    temperature: float = 0.2
) -> StreamingDebuggerAgent:
    """Создаёт StreamingDebuggerAgent."""
    return StreamingDebuggerAgent(model=model, temperature=temperature)
