"""Стриминговая версия агента рефлексии.

Обеспечивает real-time стриминг:
- <think> блоков reasoning моделей
- Анализа качества по мере генерации
- Возможность прерывания
"""
from dataclasses import dataclass
from typing import Dict, Optional, Any, AsyncGenerator
from infrastructure.local_llm import create_llm_for_stage
from infrastructure.reasoning_stream import get_reasoning_stream_manager
from infrastructure.reasoning_utils import is_reasoning_response
from utils.logger import get_logger
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


class StreamingReflectionAgent:
    """Агент для рефлексии с real-time стримингом.
    
    Расширяет функциональность ReflectionAgent:
    - Real-time стриминг <think> блоков
    - Real-time стриминг анализа
    - Возможность прерывания
    """

    def __init__(
        self, 
        model: Optional[str] = None, 
        temperature: float = 0.25
    ) -> None:
        """Инициализация агента.
        
        Args:
            model: Модель (если None, выбирается автоматически)
            temperature: Температура генерации
        """
        if model is None:
            router = get_model_router()
            model_selection = router.select_model(
                task_type="reflection",
                preferred_model=None,
                context={"agent": "streaming_reflection"}
            )
            model = model_selection.model
        
        self.model = model
        self.temperature = temperature
        self.llm = create_llm_for_stage(
            stage="reflection",
            model=model,
            temperature=temperature,
            top_p=0.9
        )
        self.quality_threshold = 0.7
        self.reasoning_manager = get_reasoning_stream_manager()
        self._interrupted = False
    
    def interrupt(self) -> None:
        """Прерывает текущую рефлексию."""
        self._interrupted = True
        self.reasoning_manager.interrupt()
        logger.info("⏹️ Рефлексия прервана")
    
    def reset(self) -> None:
        """Сбрасывает состояние агента."""
        self._interrupted = False
        self.reasoning_manager.reset()
    
    async def reflect_stream(
        self,
        task: str,
        plan: str,
        context: str,
        tests: str,
        code: str,
        validation_results: Dict[str, Any],
        stage: str = "reflection"
    ) -> AsyncGenerator[tuple[str, Any], None]:
        """Проводит рефлексию с real-time стримингом.
        
        Args:
            task: Исходная задача
            plan: План реализации
            context: Контекст
            tests: Тесты
            code: Код
            validation_results: Результаты валидации
            stage: Этап workflow
            
        Yields:
            tuple[event_type, data]:
                - ("thinking", sse_event) — SSE событие для <think> блока
                - ("reflection_chunk", chunk) — чанк анализа
                - ("done", ReflectionResult) — финальный результат
        """
        logger.info("🔍 Стриминг рефлексии...")
        
        self.reset()
        
        # Базовые оценки на основе валидации
        base_scores = self._calculate_base_scores(validation_results, tests, code)
        
        # Строим промпт
        prompt = self._build_analysis_prompt(
            task=task,
            plan=plan,
            context=context,
            tests=tests,
            code=code,
            validation_results=validation_results,
            base_scores=base_scores
        )
        
        config = get_config()
        reflection_buffer = ""
        full_response = ""
        
        try:
            async for event_type, data in self.reasoning_manager.stream_from_llm(
                llm=self.llm,
                prompt=prompt,
                stage=stage,
                num_predict=config.llm_tokens_analysis
            ):
                if self._interrupted:
                    logger.info("⏹️ Рефлексия прервана")
                    break
                
                if event_type == "thinking":
                    yield ("thinking", data)
                elif event_type == "content":
                    reflection_buffer += data
                    yield ("reflection_chunk", data)
                elif event_type == "done":
                    full_response = data
            
            # Парсим результат
            response_to_parse = full_response if full_response else reflection_buffer
            reflection_result = self._parse_reflection_response(
                response_to_parse,
                base_scores,
                validation_results
            )
            
            logger.info(f"✅ Рефлексия завершена. Оценка: {reflection_result.overall_score:.2f}")
            
            yield ("done", reflection_result)
            
        except Exception as e:
            logger.error(f"❌ Ошибка стриминга рефлексии: {e}", error=e)
            yield ("done", ReflectionResult(
                planning_score=0.5,
                research_score=0.5,
                testing_score=0.5,
                coding_score=0.5,
                overall_score=0.5,
                analysis="Ошибка анализа",
                improvements=str(e),
                should_retry=True
            ))
    
    # === Синхронный метод для обратной совместимости ===
    
    def reflect(
        self,
        task: str,
        plan: str,
        context: str,
        tests: str,
        code: str,
        validation_results: Dict[str, Any]
    ) -> ReflectionResult:
        """Синхронная рефлексия (для обратной совместимости)."""
        from agents.reflection import ReflectionAgent
        
        sync_agent = ReflectionAgent(
            model=self.model,
            temperature=self.temperature
        )
        return sync_agent.reflect(task, plan, context, tests, code, validation_results)  # type: ignore[return-value]
    
    # === Приватные методы ===
    
    def _calculate_base_scores(
        self,
        validation_results: Dict[str, Any],
        tests: str,
        code: str
    ) -> Dict[str, float]:
        """Вычисляет базовые оценки на основе метрик."""
        scores: Dict[str, float] = {
            "planning": 0.7,
            "research": 0.7,
            "testing": 0.7,
            "coding": 0.7
        }
        
        # Оценка тестирования
        if tests:
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
        
        # Оценка кодирования
        pytest_passed = validation_results.get("pytest", {}).get("success", False)
        mypy_passed = validation_results.get("mypy", {}).get("success", False)
        bandit_passed = validation_results.get("bandit", {}).get("success", False)
        
        coding_score = 0.0
        checks_passed = 0
        total_checks = 0
        
        if tests:
            total_checks += 1
            if pytest_passed:
                checks_passed += 1
                coding_score += 0.5
        
        total_checks += 1
        if mypy_passed:
            checks_passed += 1
            coding_score += 0.25
        
        total_checks += 1
        if bandit_passed:
            checks_passed += 1
            coding_score += 0.25
        
        if total_checks > 0 and checks_passed == total_checks:
            scores["coding"] = min(coding_score + 0.2, 1.0)
        elif checks_passed > 0:
            scores["coding"] = coding_score
        else:
            scores["coding"] = 0.3
        
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
        """Строит промпт для анализа."""
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
        """Парсит ответ модели и создаёт ReflectionResult."""
        # Если был reasoning ответ — извлекаем основной контент
        if is_reasoning_response(response):
            from infrastructure.reasoning_utils import parse_reasoning_response
            parsed = parse_reasoning_response(response)
            response = parsed.answer
        
        planning_score = base_scores.get("planning", 0.7)
        research_score = base_scores.get("research", 0.7)
        testing_score = base_scores.get("testing", 0.7)
        coding_score = base_scores.get("coding", 0.7)
        overall_score = 0.7
        
        analysis = ""
        improvements = ""
        should_retry = False
        
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
            
            elif current_section == "analysis" and stripped:
                if not analysis or analysis.endswith(":"):
                    analysis = stripped
                else:
                    analysis += "\n" + stripped
            
            elif current_section == "improvements" and stripped:
                if not improvements or improvements.endswith(":"):
                    improvements = stripped
                else:
                    improvements += "\n" + stripped
            
            elif current_section == "retry":
                if "да" in stripped.lower() or "yes" in stripped.lower() or "true" in stripped.lower():
                    should_retry = True
        
        # Если overall не найден, вычисляем среднее
        if overall_score == 0.7 and (planning_score != 0.7 or research_score != 0.7 or 
                                     testing_score != 0.7 or coding_score != 0.7):
            overall_score = (planning_score + research_score + testing_score + coding_score) / 4.0
        
        # Определяем нужно ли повторять
        if overall_score < self.quality_threshold:
            should_retry = True
        
        if not analysis:
            analysis = "Базовый анализ на основе валидационных проверок."
        if not improvements:
            if should_retry:
                improvements = "Качество ниже порога 0.7. Рекомендуется попробовать альтернативный подход."
            else:
                improvements = "Код прошёл все проверки."
        
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


# === Factory функция ===

def get_streaming_reflection_agent(
    model: Optional[str] = None,
    temperature: float = 0.25
) -> StreamingReflectionAgent:
    """Создаёт StreamingReflectionAgent."""
    return StreamingReflectionAgent(model=model, temperature=temperature)
