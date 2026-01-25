"""Базовый класс для всех агентов.

Устраняет дублирование кода между синхронными и стриминговыми агентами.
Содержит общую логику:
- Инициализация LLM
- Очистка кода
- Обработка reasoning ответов
- Извлечение деталей ошибок (для DebuggerAgent)
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING
from infrastructure.local_llm import create_llm_for_stage
from infrastructure.model_router import get_model_router
from infrastructure.reasoning_utils import (
    is_reasoning_response,
    extract_code_from_reasoning
)
from utils.logger import get_logger

if TYPE_CHECKING:
    from infrastructure.coder_interfaces import ILLM

logger = get_logger()


class BaseAgent(ABC):
    """Базовый класс для всех агентов.
    
    Предоставляет общую функциональность:
    - Инициализация LLM через ModelRouter
    - Очистка сгенерированного кода
    - Обработка reasoning ответов
    
    Все агенты должны наследоваться от этого класса.
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.25,
        stage: str = "default",
        llm: Optional['ILLM'] = None
    ) -> None:
        """Инициализация базового агента.
        
        Args:
            model: Модель для использования (если None, выбирается через ModelRouter)
            temperature: Температура генерации
            stage: Этап workflow (для выбора модели и конфигурации)
            llm: LLM для использования (для тестирования, по умолчанию создаётся автоматически)
        """
        # Вызываем super().__init__() для правильной инициализации ABC
        super().__init__()
        
        if llm is not None:
            self.llm = llm
            self.model = getattr(llm, 'model', model) or "unknown"
        else:
            self.model, self.llm = self._init_llm(model, temperature, stage)
        
        self.temperature = temperature
        self.stage = stage
    
    def _init_llm(
        self,
        model: Optional[str],
        temperature: float,
        stage: str
    ) -> tuple[str, 'ILLM']:
        """Инициализирует LLM для агента.
        
        Использует ModelRouter для автоматического выбора модели если не указана.
        
        Args:
            model: Модель для использования (опционально)
            temperature: Температура генерации
            stage: Этап workflow
            
        Returns:
            tuple[model_name, llm_instance]
        """
        if model is None:
            router = get_model_router()
            model_selection = router.select_model(
                task_type="coding",  # Большинство агентов работают с кодом
                preferred_model=None,
                context={"agent": self.__class__.__name__.lower().replace("agent", "")}
            )
            model = model_selection.model
            logger.debug(f"🤖 ModelRouter выбрал модель: {model} для {self.__class__.__name__}")
        
        llm = create_llm_for_stage(
            stage=stage,
            model=model,
            temperature=temperature,
            top_p=0.9
        )
        
        return model, llm
    
    def reset(self) -> None:
        """Сбрасывает состояние агента.
        
        Общий метод для всех стриминговых агентов.
        Сбрасывает флаг прерывания и состояние reasoning менеджера.
        """
        self._interrupted = False
        if hasattr(self, 'reasoning_manager') and self.reasoning_manager:
            self.reasoning_manager.reset()
    
    def _switch_to_fallback_model(
        self,
        failed_model: str,
        task_type: str = "coding",
        complexity: Optional[Any] = None
    ) -> bool:
        """Переключается на запасную модель при ошибке основной.
        
        Args:
            failed_model: Модель которая не сработала
            task_type: Тип задачи (coding, testing, planning, etc.)
            complexity: Сложность задачи (если известна)
            
        Returns:
            True если переключение успешно, False если запасной модели нет
        """
        from utils.model_checker import TaskComplexity
        
        router = get_model_router()
        
        # Преобразуем complexity в TaskComplexity если нужно
        task_complexity = None
        if complexity:
            if isinstance(complexity, TaskComplexity):
                task_complexity = complexity
            elif isinstance(complexity, str):
                try:
                    task_complexity = TaskComplexity[complexity.upper()]
                except KeyError:
                    pass
        
        # Получаем запасную модель
        fallback_selection = router.get_fallback_model(
            failed_model=failed_model,
            task_type=task_type,
            complexity=task_complexity
        )
        
        if not fallback_selection:
            logger.error(f"❌ Нет доступных запасных моделей для {failed_model}")
            return False
        
        new_model = fallback_selection.model
        logger.info(
            f"🔄 Переключаюсь с {failed_model} на {new_model} "
            f"(причина: {fallback_selection.reason})"
        )
        
        # Пересоздаём LLM с новой моделью
        self.model = new_model
        try:
            self.llm = create_llm_for_stage(
                stage=self.stage,
                model=new_model,
                temperature=self.temperature,
                top_p=0.9
            )
            # Проверяем доступность новой модели перед переключением
            from utils.model_checker import check_model_available
            if not check_model_available(new_model):
                logger.error(f"❌ Запасная модель {new_model} также недоступна")
                return False
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при переключении на модель {new_model}: {e}")
            return False
    
    def _clean_code(self, raw_code: str) -> str:
        """Очищает сгенерированный код от markdown и лишних элементов.
        
        Удаляет:
        - Markdown блоки кода (```python ... ```)
        - Текстовые объяснения в начале/конце
        - Пустые строки в начале
        
        Args:
            raw_code: Сырой код от модели
            
        Returns:
            Очищенный код или пустая строка если код невалиден
        """
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
        
        # Убеждаемся что есть хотя бы def или class
        if "def " not in cleaned and "class " not in cleaned:
            logger.warning("⚠️ В сгенерированном коде не найдено функций или классов")
            return ""
        
        return cleaned
    
    def _extract_content_from_reasoning(self, response: str) -> str:
        """Извлекает контент из reasoning ответа.
        
        Если ответ содержит <think> блоки, извлекает только основной контент.
        Иначе возвращает ответ как есть.
        
        Args:
            response: Полный ответ от модели (может содержать <think> блоки)
            
        Returns:
            Извлечённый контент без thinking блоков
        """
        if not response:
            return ""
        
        if is_reasoning_response(response):
            # Извлекаем код из reasoning ответа
            extracted = extract_code_from_reasoning(response)
            logger.debug(f"🧠 Извлечён контент из reasoning ответа ({len(extracted)} символов)")
            return extracted
        
        return response
    
    def _clean_code_from_reasoning(self, response: str) -> str:
        """Извлекает и очищает код из reasoning ответа.
        
        Комбинирует _extract_content_from_reasoning и _clean_code.
        
        Args:
            response: Полный ответ от модели
            
        Returns:
            Очищенный код
        """
        content = self._extract_content_from_reasoning(response)
        return self._clean_code(content)
    
    def _extract_error_details(
        self,
        validation_results: Dict[str, Any]
    ) -> Dict[str, str]:
        """Извлекает детали ошибок из результатов валидации.
        
        Общий метод для DebuggerAgent и StreamingDebuggerAgent.
        
        Args:
            validation_results: Результаты валидации (pytest, mypy, bandit)
            
        Returns:
            Словарь с деталями ошибок для каждого валидатора
        """
        from typing import Dict, Any, List
        
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
        
        Общий метод для DebuggerAgent и StreamingDebuggerAgent.
        
        Args:
            validation_results: Результаты валидации
            
        Returns:
            Тип ошибки: "pytest", "mypy", "bandit", "multiple", "unknown"
        """
        from typing import List
        
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
