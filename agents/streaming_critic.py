"""Стриминговая версия агента-критика.

Обеспечивает real-time стриминг:
- <think> блоков reasoning моделей
- Критического анализа по мере генерации
- Возможность прерывания

Примечание: CriticAgent использует комбинацию статического анализа (AST) 
и LLM, поэтому стриминг применяется только к LLM части.
"""
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass, field
from infrastructure.local_llm import create_llm_for_stage
from infrastructure.model_router import get_model_router
from infrastructure.reasoning_stream import get_reasoning_stream_manager
from infrastructure.reasoning_utils import is_reasoning_response
from utils.logger import get_logger
from utils.config import get_config
import ast
import re

logger = get_logger()


@dataclass
class CriticIssue:
    """Конкретная проблема, найденная критиком."""
    category: str  # security, performance, correctness, style, maintainability
    severity: str  # critical, warning, info
    location: str  # строка/функция где найдена проблема
    description: str  # описание проблемы
    evidence: str  # конкретный код/факт подтверждающий проблему
    suggestion: str  # как исправить


@dataclass 
class CriticReport:
    """Отчёт критика о качестве кода."""
    overall_score: float = 1.0  # 0.0 - 1.0
    issues: List[CriticIssue] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    summary: str = ""
    code_analyzed: bool = False
    tests_analyzed: bool = False


class StreamingCriticAgent:
    """Агент-критик с real-time стримингом LLM анализа.
    
    Расширяет функциональность CriticAgent:
    - Real-time стриминг <think> блоков при LLM анализе
    - Статический анализ выполняется синхронно (быстро)
    - Возможность прерывания LLM части
    """
    
    ISSUE_CATEGORIES = {
        "security": {"priority": 1, "label": "Безопасность"},
        "correctness": {"priority": 2, "label": "Корректность"},
        "performance": {"priority": 3, "label": "Производительность"},
        "maintainability": {"priority": 4, "label": "Поддерживаемость"},
        "style": {"priority": 5, "label": "Стиль кода"}
    }
    
    def __init__(
        self, 
        model: Optional[str] = None, 
        temperature: float = 0.1
    ) -> None:
        """Инициализация агента.
        
        Args:
            model: Модель (если None, используется лёгкая)
            temperature: Низкая температура для точности
        """
        if model is None:
            router = get_model_router()
            model_selection = router.select_model(
                task_type="intent",
                preferred_model=None,
                context={"agent": "streaming_critic"}
            )
            model = model_selection.model
        
        self.model = model
        self.temperature = temperature
        self.llm = create_llm_for_stage(
            stage="critic",
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
        logger.info("⏹️ Критический анализ прерван")
    
    def reset(self) -> None:
        """Сбрасывает состояние агента."""
        self._interrupted = False
        self.reasoning_manager.reset()
    
    async def analyze_stream(
        self,
        code: str,
        tests: str = "",
        task_description: str = "",
        validation_results: Optional[Dict[str, Any]] = None,
        stage: str = "critic"
    ) -> AsyncGenerator[tuple[str, Any], None]:
        """Анализирует код с real-time стримингом LLM части.
        
        Args:
            code: Код для анализа
            tests: Тесты
            task_description: Описание задачи
            validation_results: Результаты валидации
            stage: Этап workflow
            
        Yields:
            tuple[event_type, data]:
                - ("static_analysis", List[CriticIssue]) — результаты статического анализа
                - ("thinking", sse_event) — SSE событие для <think> блока
                - ("critic_chunk", chunk) — чанк LLM анализа
                - ("done", CriticReport) — финальный отчёт
        """
        logger.info("🔍 Критик анализирует код...")
        
        self.reset()
        
        if not code.strip():
            yield ("done", CriticReport(
                overall_score=0.0,
                summary="Код отсутствует",
                code_analyzed=False
            ))
            return
        
        report = CriticReport(code_analyzed=True, tests_analyzed=bool(tests))
        
        # 1. Статический анализ (синхронный, быстрый)
        static_issues = self._static_analysis(code)
        report.issues.extend(static_issues)
        yield ("static_analysis", static_issues)
        
        # 2. Анализ результатов валидации
        if validation_results:
            validation_issues = self._analyze_validation_results(validation_results)
            report.issues.extend(validation_issues)
        
        # 3. LLM анализ со стримингом
        try:
            llm_issues = await self._llm_analysis_stream(
                code, tests, task_description, stage
            )
            report.issues.extend(llm_issues)
        except Exception as e:
            logger.warning(f"⚠️ LLM анализ не выполнен: {e}")
        
        # 4. Сильные стороны
        report.strengths = self._find_strengths(code, tests)
        
        # 5. Общая оценка
        report.overall_score = self._calculate_score(report.issues)
        
        # 6. Summary
        report.summary = self._generate_summary(report)
        
        logger.info(f"✅ Критик завершил: {len(report.issues)} проблем, оценка {report.overall_score:.0%}")
        
        yield ("done", report)
    
    async def _llm_analysis_stream(
        self,
        code: str,
        tests: str,
        task_description: str,
        stage: str
    ) -> List[CriticIssue]:
        """LLM анализ со стримингом thinking."""
        issues: List[CriticIssue] = []
        
        code_snippet = code[:2000] if len(code) > 2000 else code
        
        prompt = f"""Analyze this Python code and find REAL issues. Only report issues you are 100% certain about.

CODE:
```python
{code_snippet}
```

TASK: {task_description or 'Not specified'}

Find issues in these categories:
1. CORRECTNESS - Logic errors, bugs, edge cases not handled
2. PERFORMANCE - Inefficient algorithms (O(n²) where O(n) possible), memory leaks
3. SECURITY - Injection risks, unsafe operations (only if not already found)

Rules:
- ONLY report issues you can prove with specific code evidence
- Do NOT make up issues or guess
- Do NOT report style issues (already checked)
- Maximum 3 most important issues

For each issue, respond in this exact format:
ISSUE: <category>|<severity: critical/warning>|<location>|<description>|<evidence from code>|<fix suggestion>

If no significant issues found, respond: NO_ISSUES

Response:"""

        config = get_config()
        llm_buffer = ""
        
        async for event_type, data in self.reasoning_manager.stream_from_llm(
            llm=self.llm,
            prompt=prompt,
            stage=stage,
            num_predict=config.llm_tokens_critic
        ):
            if self._interrupted:
                break
            
            if event_type == "content":
                llm_buffer += data
            elif event_type == "done":
                llm_buffer = data
        
        # Парсим ответ
        if is_reasoning_response(llm_buffer):
            from infrastructure.reasoning_utils import parse_reasoning_response
            parsed = parse_reasoning_response(llm_buffer)
            llm_buffer = parsed.answer
        
        if "NO_ISSUES" in llm_buffer:
            return issues
        
        for line in llm_buffer.split('\n'):
            if line.startswith('ISSUE:'):
                parts = line[6:].split('|')
                if len(parts) >= 6:
                    category = parts[0].strip().lower()
                    if category in self.ISSUE_CATEGORIES:
                        issues.append(CriticIssue(
                            category=category,
                            severity=parts[1].strip().lower() if parts[1].strip().lower() in ('critical', 'warning', 'info') else 'warning',
                            location=parts[2].strip(),
                            description=parts[3].strip(),
                            evidence=parts[4].strip(),
                            suggestion=parts[5].strip()
                        ))
        
        return issues[:3]
    
    # === Синхронный метод для обратной совместимости ===
    
    def analyze(
        self,
        code: str,
        tests: str = "",
        task_description: str = "",
        validation_results: Optional[Dict[str, Any]] = None
    ) -> CriticReport:
        """Синхронный анализ (для обратной совместимости)."""
        from agents.critic import CriticAgent
        
        sync_agent = CriticAgent(
            model=self.model,
            temperature=self.temperature
        )
        return sync_agent.analyze(code, tests, task_description, validation_results)  # type: ignore[return-value]
    
    # === Приватные методы (из CriticAgent) ===
    
    def _static_analysis(self, code: str) -> List[CriticIssue]:
        """Статический анализ без LLM."""
        issues: List[CriticIssue] = []
        
        # Проверка синтаксиса
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(CriticIssue(
                category="correctness",
                severity="critical",
                location=f"строка {e.lineno}" if e.lineno else "неизвестно",
                description="Синтаксическая ошибка Python",
                evidence=str(e.msg) if e.msg else "Некорректный синтаксис",
                suggestion="Исправьте синтаксис согласно сообщению об ошибке"
            ))
            return issues
        
        lines = code.split('\n')
        
        # Опасные паттерны
        dangerous_patterns = [
            (r'\beval\s*\(', "Использование eval() — риск выполнения произвольного кода"),
            (r'\bexec\s*\(', "Использование exec() — риск выполнения произвольного кода"),
            (r'__import__\s*\(', "Динамический импорт — потенциальный риск безопасности"),
            (r'subprocess\..*shell\s*=\s*True', "shell=True в subprocess — риск shell injection"),
            (r'os\.system\s*\(', "os.system() — используйте subprocess для безопасности"),
        ]
        
        for i, line in enumerate(lines, 1):
            for pattern, description in dangerous_patterns:
                if re.search(pattern, line):
                    issues.append(CriticIssue(
                        category="security",
                        severity="critical",
                        location=f"строка {i}",
                        description=description,
                        evidence=line.strip(),
                        suggestion="Замените на безопасную альтернативу"
                    ))
        
        # Bare except
        for i, line in enumerate(lines, 1):
            if re.match(r'\s*except\s*:', line):
                issues.append(CriticIssue(
                    category="correctness",
                    severity="warning",
                    location=f"строка {i}",
                    description="Bare except — перехватывает все исключения",
                    evidence=line.strip(),
                    suggestion="Используйте except Exception:"
                ))
        
        return issues
    
    def _analyze_validation_results(self, validation: Dict[str, Any]) -> List[CriticIssue]:
        """Анализирует результаты валидации."""
        issues: List[CriticIssue] = []
        
        pytest_result = validation.get("pytest", {})
        if not pytest_result.get("success", True):
            output = pytest_result.get("output", "")
            failed_tests = re.findall(r'FAILED\s+(\S+)', output)
            for test in failed_tests[:5]:
                issues.append(CriticIssue(
                    category="correctness",
                    severity="critical",
                    location=test,
                    description="Тест не проходит",
                    evidence=f"pytest FAILED: {test}",
                    suggestion="Исправьте код чтобы тест проходил"
                ))
        
        mypy_result = validation.get("mypy", {})
        if not mypy_result.get("success", True):
            errors = mypy_result.get("errors", "")
            for error in errors.split('\n')[:5]:
                if error.strip():
                    issues.append(CriticIssue(
                        category="correctness",
                        severity="warning",
                        location="mypy",
                        description="Ошибка типизации",
                        evidence=error.strip()[:200],
                        suggestion="Исправьте типы"
                    ))
        
        return issues
    
    def _find_strengths(self, code: str, tests: str) -> List[str]:
        """Находит сильные стороны кода."""
        strengths: List[str] = []
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return strengths
        
        has_docstrings = any(
            ast.get_docstring(node) 
            for node in ast.walk(tree) 
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        )
        if has_docstrings:
            strengths.append("✓ Документация (docstrings)")
        
        has_type_hints = any(
            node.returns is not None or any(arg.annotation for arg in node.args.args)
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        )
        if has_type_hints:
            strengths.append("✓ Аннотации типов")
        
        if tests and 'def test_' in tests:
            test_count = tests.count('def test_')
            strengths.append(f"✓ Тесты ({test_count} шт.)")
        
        return strengths
    
    def _calculate_score(self, issues: List[CriticIssue]) -> float:
        """Рассчитывает общую оценку."""
        if not issues:
            return 1.0
        
        severity_weights = {
            "critical": 0.25,
            "warning": 0.10,
            "info": 0.02
        }
        
        penalty = sum(
            severity_weights.get(issue.severity, 0.05)
            for issue in issues
        )
        
        return max(0.0, min(1.0, round(1.0 - penalty, 2)))
    
    def _generate_summary(self, report: CriticReport) -> str:
        """Генерирует краткое резюме."""
        critical = sum(1 for i in report.issues if i.severity == "critical")
        warnings = sum(1 for i in report.issues if i.severity == "warning")
        info = sum(1 for i in report.issues if i.severity == "info")
        
        if critical > 0:
            status = "❌ Требуется исправление"
        elif warnings > 0:
            status = "⚠️ Есть замечания"
        elif info > 0:
            status = "ℹ️ Можно улучшить"
        else:
            status = "✅ Код качественный"
        
        parts = []
        if critical:
            parts.append(f"{critical} критических")
        if warnings:
            parts.append(f"{warnings} предупреждений")
        if info:
            parts.append(f"{info} рекомендаций")
        
        issues_str = ", ".join(parts) if parts else "проблем не найдено"
        
        return f"{status} | {issues_str} | Оценка: {report.overall_score:.0%}"


# === Factory функция ===

def get_streaming_critic_agent(
    model: Optional[str] = None,
    temperature: float = 0.1
) -> StreamingCriticAgent:
    """Создаёт StreamingCriticAgent."""
    return StreamingCriticAgent(model=model, temperature=temperature)
