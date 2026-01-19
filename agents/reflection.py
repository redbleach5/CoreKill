"""Агент для рефлексии и анализа результатов выполнения задачи."""
from dataclasses import dataclass
from typing import Dict, Optional, Any
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


@dataclass
class ReflectionResult:
    """Результат рефлексии и оценки качества."""
    planning_score: float  # 0.0 - 1.0
    research_score: float  # 0.0 - 1.0
    testing_score: float   # 0.0 - 1.0
    coding_score: float    # 0.0 - 1.0
    overall_score: float   # 0.0 - 1.0
    analysis: str  # Текстовый анализ что прошло хорошо/плохо
    improvements: str  # Предложения по улучшению
    should_retry: bool  # Нужно ли попробовать другую альтернативу


class ReflectionAgent:
    """Агент для анализа результатов работы системы и оценки качества.
    
    Оценивает различные аспекты выполнения задачи и предлагает улучшения.
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.25) -> None:
        """Инициализация агента рефлексии.
        
        Args:
            model: Модель для анализа (если None, выбирается из config)
            temperature: Температура генерации
        """
        if model is None:
            # Используем ModelRouter для выбора модели (поддерживает будущее расширение роя моделей)
            router = get_model_router()
            model_selection = router.select_model(
                task_type="reflection",
                preferred_model=None,
                context={"agent": "reflection"}
            )
            model = model_selection.model
        
        self.llm = LocalLLM(
            model=model,
            temperature=temperature,
            top_p=0.9
        )
        self.quality_threshold = 0.7  # Порог для предложения повторной попытки

    def reflect(
        self,
        task: str,
        plan: str,
        context: str,
        tests: str,
        code: str,
        validation_results: Dict[str, Any]
    ) -> ReflectionResult:
        """Проводит рефлексию над результатами выполнения задачи.
        
        Args:
            task: Исходная задача пользователя
            plan: План реализации
            context: Собранный контекст
            tests: Сгенерированные тесты
            code: Сгенерированный код
            validation_results: Результаты валидации (pytest, mypy, bandit)
            
        Returns:
            ReflectionResult с оценками и рекомендациями
        """
        logger.info("🔍 Провожу рефлексию над результатами...")
        
        # Сначала вычисляем базовые оценки на основе валидации
        base_scores = self._calculate_base_scores(validation_results, tests, code)
        
        # Затем получаем детальный анализ от LLM
        analysis_prompt = self._build_analysis_prompt(
            task=task,
            plan=plan,
            context=context,
            tests=tests,
            code=code,
            validation_results=validation_results,
            base_scores=base_scores
        )
        
        config = get_config()
        analysis_response = self.llm.generate(analysis_prompt, num_predict=config.llm_tokens_analysis)
        
        # Парсим ответ и объединяем с базовыми оценками
        reflection_result = self._parse_reflection_response(
            analysis_response,
            base_scores,
            validation_results
        )
        
        logger.info(
            f"✅ Рефлексия завершена. Общая оценка: {reflection_result.overall_score:.2f}"
        )
        
        return reflection_result

    def _calculate_base_scores(
        self,
        validation_results: Dict[str, Any],
        tests: str,
        code: str
    ) -> Dict[str, float]:
        """Вычисляет базовые оценки на основе объективных метрик.
        
        Args:
            validation_results: Результаты валидации
            tests: Сгенерированные тесты
            code: Сгенерированный код
            
        Returns:
            Словарь с базовыми оценками
        """
        scores: Dict[str, float] = {
            "planning": 0.7,  # Базовое значение, уточняется LLM
            "research": 0.7,
            "testing": 0.7,
            "coding": 0.7
        }
        
        # Оценка тестирования
        if tests:
            # Проверяем количество тестов
            test_count = tests.count("def test_")
            if test_count >= 5:
                scores["testing"] = 0.9
            elif test_count >= 3:
                scores["testing"] = 0.8
            elif test_count > 0:
                scores["testing"] = 0.6
            else:
                scores["testing"] = 0.3
        else:
            scores["testing"] = 0.2
        
        # Оценка кодирования на основе валидации
        pytest_passed = validation_results.get("pytest", {}).get("success", False)
        mypy_passed = validation_results.get("mypy", {}).get("success", False)
        bandit_passed = validation_results.get("bandit", {}).get("success", False)
        
        # Вычисляем coding_score как комбинацию валидационных проверок
        coding_score = 0.0
        checks_passed = 0
        total_checks = 0
        
        if tests:  # pytest только если есть тесты
            total_checks += 1
            if pytest_passed:
                checks_passed += 1
                coding_score += 0.5  # pytest весит больше
        
        total_checks += 1
        if mypy_passed:
            checks_passed += 1
            coding_score += 0.25
        
        total_checks += 1
        if bandit_passed:
            checks_passed += 1
            coding_score += 0.25
        
        # Если все проверки прошли
        if total_checks > 0 and checks_passed == total_checks:
            scores["coding"] = min(coding_score + 0.2, 1.0)
        elif checks_passed > 0:
            scores["coding"] = coding_score
        else:
            scores["coding"] = 0.3
        
        # Оценка исследования на основе наличия контекста
        # (это будет уточнено LLM, здесь базовая оценка)
        scores["research"] = 0.7
        
        return scores

    def _build_analysis_prompt(
        self,
        task: str,
        plan: str,
        context: str,
        tests: str,
        code: str,
        validation_results: Dict[str, Any],
        base_scores: Dict[str, float]
    ) -> str:
        """Строит промпт для детального анализа."""
        
        validation_summary = f"""
Результаты валидации:
- pytest: {'✅ ПРОЙДЕН' if validation_results.get('pytest', {}).get('success') else '❌ НЕ ПРОЙДЕН'}
- mypy: {'✅ ПРОЙДЕН' if validation_results.get('mypy', {}).get('success') else '❌ НЕ ПРОЙДЕН'}
- bandit: {'✅ ПРОЙДЕН' if validation_results.get('bandit', {}).get('success') else '❌ НЕ ПРОЙДЕН'}
"""
        
        prompt = f"""Ты - эксперт по анализу качества кода и процессов разработки. Проанализируй выполнение задачи.

Задача: {task}

План:
{plan}

Собранный контекст (длина: {len(context)} символов):
{context[:500] if context else 'Контекст не собран'}

Сгенерированные тесты (длина: {len(tests)} символов, количество: {tests.count('def test_')}):
{tests[:300] if tests else 'Тесты не сгенерированы'}

Сгенерированный код (длина: {len(code)} символов):
{code[:500] if code else 'Код не сгенерирован'}

{validation_summary}

Базовые оценки:
- Planning: {base_scores['planning']:.2f}
- Research: {base_scores['research']:.2f}
- Testing: {base_scores['testing']:.2f}
- Coding: {base_scores['coding']:.2f}

Проанализируй и ответь в следующем формате (строго придерживайся формата):

ОЦЕНКИ:
planning: [0.0-1.0]
research: [0.0-1.0]
testing: [0.0-1.0]
coding: [0.0-1.0]
overall: [0.0-1.0]

АНАЛИЗ:
[Что прошло хорошо, что плохо, какие проблемы]

УЛУЧШЕНИЯ:
[Конкретные предложения: новый план / другая стратегия / изменения в промптах]

НУЖНА_ПОВТОРНАЯ_ПОПЫТКА: [да/нет]
"""
        return prompt

    def _parse_reflection_response(
        self,
        response: str,
        base_scores: Dict[str, float],
        validation_results: Dict[str, Any]
    ) -> ReflectionResult:
        """Парсит ответ модели и создаёт ReflectionResult.
        
        Args:
            response: Ответ модели
            base_scores: Базовые оценки
            validation_results: Результаты валидации
            
        Returns:
            ReflectionResult
        """
        # Инициализируем значениями по умолчанию
        planning_score = base_scores.get("planning", 0.7)
        research_score = base_scores.get("research", 0.7)
        testing_score = base_scores.get("testing", 0.7)
        coding_score = base_scores.get("coding", 0.7)
        overall_score = 0.7
        
        analysis = ""
        improvements = ""
        should_retry = False
        
        # Парсим оценки
        lines = response.split("\n")
        current_section = None
        
        for line in lines:
            stripped = line.strip()
            
            if "ОЦЕНКИ:" in stripped or "ОЦЕНКА:" in stripped:
                current_section = "scores"
                continue
            elif "АНАЛИЗ:" in stripped:
                current_section = "analysis"
                continue
            elif "УЛУЧШЕНИЯ:" in stripped or "УЛУЧШЕНИЕ:" in stripped:
                current_section = "improvements"
                continue
            elif "НУЖНА_ПОВТОРНАЯ_ПОПЫТКА:" in stripped or "ПОВТОР:" in stripped:
                current_section = "retry"
                continue
            
            # Парсим оценки
            if current_section == "scores":
                if "planning:" in stripped.lower():
                    try:
                        value = float(stripped.split(":")[-1].strip())
                        planning_score = max(0.0, min(1.0, value))
                    except (ValueError, IndexError):
                        pass
                elif "research:" in stripped.lower():
                    try:
                        value = float(stripped.split(":")[-1].strip())
                        research_score = max(0.0, min(1.0, value))
                    except (ValueError, IndexError):
                        pass
                elif "testing:" in stripped.lower():
                    try:
                        value = float(stripped.split(":")[-1].strip())
                        testing_score = max(0.0, min(1.0, value))
                    except (ValueError, IndexError):
                        pass
                elif "coding:" in stripped.lower():
                    try:
                        value = float(stripped.split(":")[-1].strip())
                        coding_score = max(0.0, min(1.0, value))
                    except (ValueError, IndexError):
                        pass
                elif "overall:" in stripped.lower() or "общая:" in stripped.lower():
                    try:
                        value = float(stripped.split(":")[-1].strip())
                        overall_score = max(0.0, min(1.0, value))
                    except (ValueError, IndexError):
                        pass
            
            # Собираем анализ
            elif current_section == "analysis" and stripped:
                if not analysis or analysis.endswith(":"):
                    analysis = stripped
                else:
                    analysis += "\n" + stripped
            
            # Собираем улучшения
            elif current_section == "improvements" and stripped:
                if not improvements or improvements.endswith(":"):
                    improvements = stripped
                else:
                    improvements += "\n" + stripped
            
            # Парсим флаг повторной попытки
            elif current_section == "retry":
                if "да" in stripped.lower() or "yes" in stripped.lower() or "true" in stripped.lower():
                    should_retry = True
        
        # Если overall не был найден, вычисляем среднее
        if overall_score == 0.7 and (planning_score != 0.7 or research_score != 0.7 or 
                                     testing_score != 0.7 or coding_score != 0.7):
            overall_score = (planning_score + research_score + testing_score + coding_score) / 4.0
        
        # Определяем нужно ли повторять на основе overall_score
        if overall_score < self.quality_threshold:
            should_retry = True
        
        # Если анализ и улучшения пустые, добавляем базовые
        if not analysis:
            analysis = "Базовый анализ на основе валидационных проверок."
        if not improvements:
            if should_retry:
                improvements = "Качество ниже порога 0.7. Рекомендуется попробовать альтернативный подход."
            else:
                improvements = "Код прошёл все проверки. Возможны небольшие улучшения в читаемости или оптимизации."
        
        return ReflectionResult(
            planning_score=planning_score,
            research_score=research_score,
            testing_score=testing_score,
            coding_score=coding_score,
            overall_score=overall_score,
            analysis=analysis.strip(),
            improvements=improvements.strip(),
            should_retry=should_retry
        )
