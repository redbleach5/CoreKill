"""Агент-критик для анализа недостатков сгенерированного кода.

Использует лёгкую модель для быстрого и объективного анализа результатов.
Фокусируется на РЕАЛЬНЫХ проблемах с конкретными фактами, а не придуманных.
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from infrastructure.local_llm import create_llm_for_stage
from infrastructure.model_router import get_model_router
from utils.logger import get_logger
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


class CriticAgent:
    """Агент-критик для объективного анализа кода.
    
    Принципы работы:
    1. Только ФАКТЫ — каждая проблема подкреплена конкретным кодом
    2. Без придумывания — если не уверен, не указывает
    3. Приоритет критических проблем — безопасность, корректность
    4. Конструктивность — каждая проблема с предложением решения
    """
    
    # Категории проблем с приоритетами
    ISSUE_CATEGORIES = {
        "security": {"priority": 1, "label": "Безопасность"},
        "correctness": {"priority": 2, "label": "Корректность"},
        "performance": {"priority": 3, "label": "Производительность"},
        "maintainability": {"priority": 4, "label": "Поддерживаемость"},
        "style": {"priority": 5, "label": "Стиль кода"}
    }
    
    def __init__(self, model: Optional[str] = None, temperature: float = 0.1) -> None:
        """Инициализация агента-критика.
        
        Args:
            model: Модель для анализа (если None, используется лёгкая модель)
            temperature: Низкая температура для точного анализа
        """
        if model is None:
            router = get_model_router()
            model_selection = router.select_model(
                task_type="intent",  # Используем лёгкую модель
                preferred_model=None,
                context={"agent": "critic"}
            )
            model = model_selection.model
        
        self.llm = create_llm_for_stage(
            stage="critic",
            model=model,
            temperature=temperature,
            top_p=0.9
        )
    
    def analyze(
        self,
        code: str,
        tests: str = "",
        task_description: str = "",
        validation_results: Optional[Dict[str, Any]] = None
    ) -> CriticReport:
        """Анализирует код и находит реальные проблемы.
        
        Args:
            code: Сгенерированный код
            tests: Сгенерированные тесты
            task_description: Описание задачи
            validation_results: Результаты валидации (pytest, mypy, etc)
            
        Returns:
            CriticReport с найденными проблемами
        """
        logger.info("🔍 Критик анализирует код...")
        
        if not code.strip():
            return CriticReport(
                overall_score=0.0,
                summary="Код отсутствует",
                code_analyzed=False
            )
        
        report = CriticReport(code_analyzed=True, tests_analyzed=bool(tests))
        
        # 1. Статический анализ (без LLM) — гарантированные факты
        static_issues = self._static_analysis(code)
        report.issues.extend(static_issues)
        
        # 2. Анализ результатов валидации (если есть)
        if validation_results:
            validation_issues = self._analyze_validation_results(validation_results)
            report.issues.extend(validation_issues)
        
        # 3. LLM анализ — только для сложных паттернов
        llm_issues = self._llm_analysis(code, tests, task_description)
        report.issues.extend(llm_issues)
        
        # 4. Определяем сильные стороны
        report.strengths = self._find_strengths(code, tests)
        
        # 5. Считаем общую оценку
        report.overall_score = self._calculate_score(report.issues)
        
        # 6. Формируем summary
        report.summary = self._generate_summary(report)
        
        logger.info(f"✅ Критик завершил анализ: {len(report.issues)} проблем, оценка {report.overall_score:.0%}")
        
        return report
    
    def _static_analysis(self, code: str) -> List[CriticIssue]:
        """Статический анализ без LLM — только гарантированные факты."""
        issues = []
        
        # 1. Проверка синтаксиса Python
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
            return issues  # Дальнейший анализ невозможен
        
        lines = code.split('\n')
        
        # 2. Проверка опасных паттернов (безопасность)
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
        
        # 3. Проверка отсутствия type hints
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Проверяем аргументы без аннотаций
                args_without_hints = [
                    arg.arg for arg in node.args.args 
                    if arg.annotation is None and arg.arg != 'self'
                ]
                if args_without_hints:
                    issues.append(CriticIssue(
                        category="maintainability",
                        severity="info",
                        location=f"функция {node.name}()",
                        description="Отсутствуют type hints для параметров",
                        evidence=f"Параметры без типов: {', '.join(args_without_hints)}",
                        suggestion="Добавьте аннотации типов для улучшения читаемости"
                    ))
                
                # Проверяем отсутствие return type
                if node.returns is None and node.name != '__init__':
                    issues.append(CriticIssue(
                        category="maintainability",
                        severity="info",
                        location=f"функция {node.name}()",
                        description="Отсутствует аннотация возвращаемого типа",
                        evidence=f"def {node.name}(...) без -> Type",
                        suggestion="Добавьте -> ReturnType после параметров"
                    ))
                
                # Проверяем отсутствие docstring
                if not ast.get_docstring(node):
                    issues.append(CriticIssue(
                        category="maintainability",
                        severity="info",
                        location=f"функция {node.name}()",
                        description="Отсутствует docstring",
                        evidence=f"Функция {node.name} без документации",
                        suggestion="Добавьте docstring с описанием, Args, Returns"
                    ))
        
        # 4. Проверка слишком длинных функций
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                end_lineno = getattr(node, 'end_lineno', None)
                func_lines = (end_lineno - node.lineno + 1) if end_lineno is not None else 0
                if func_lines > 50:
                    issues.append(CriticIssue(
                        category="maintainability",
                        severity="warning",
                        location=f"функция {node.name}()",
                        description=f"Слишком длинная функция ({func_lines} строк)",
                        evidence=f"Рекомендуется не более 50 строк на функцию",
                        suggestion="Разбейте на несколько меньших функций"
                    ))
        
        # 5. Проверка bare except
        for i, line in enumerate(lines, 1):
            if re.match(r'\s*except\s*:', line):
                issues.append(CriticIssue(
                    category="correctness",
                    severity="warning",
                    location=f"строка {i}",
                    description="Bare except — перехватывает все исключения включая SystemExit",
                    evidence=line.strip(),
                    suggestion="Используйте except Exception: или конкретный тип исключения"
                ))
        
        # 6. Проверка TODO/FIXME
        for i, line in enumerate(lines, 1):
            if re.search(r'\b(TODO|FIXME|XXX|HACK)\b', line, re.IGNORECASE):
                issues.append(CriticIssue(
                    category="maintainability",
                    severity="info",
                    location=f"строка {i}",
                    description="Найден маркер незавершённой работы",
                    evidence=line.strip(),
                    suggestion="Завершите отмеченную задачу или удалите маркер"
                ))
        
        return issues
    
    def _analyze_validation_results(self, validation: Dict[str, Any]) -> List[CriticIssue]:
        """Анализирует результаты валидации."""
        issues = []
        
        # pytest
        pytest_result = validation.get("pytest", {})
        if not pytest_result.get("success", True):
            output = pytest_result.get("output", "")
            # Извлекаем конкретные ошибки
            failed_tests = re.findall(r'FAILED\s+(\S+)', output)
            for test in failed_tests[:5]:  # Максимум 5
                issues.append(CriticIssue(
                    category="correctness",
                    severity="critical",
                    location=test,
                    description="Тест не проходит",
                    evidence=f"pytest FAILED: {test}",
                    suggestion="Исправьте код чтобы тест проходил"
                ))
        
        # mypy
        mypy_result = validation.get("mypy", {})
        if not mypy_result.get("success", True):
            errors = mypy_result.get("errors", "")
            error_lines = errors.split('\n')[:5]
            for error in error_lines:
                if error.strip():
                    issues.append(CriticIssue(
                        category="correctness",
                        severity="warning",
                        location="mypy",
                        description="Ошибка типизации",
                        evidence=error.strip()[:200],
                        suggestion="Исправьте типы согласно сообщению mypy"
                    ))
        
        # bandit (безопасность)
        bandit_result = validation.get("bandit", {})
        if not bandit_result.get("success", True):
            bandit_issues = bandit_result.get("issues", "")
            if bandit_issues:
                issues.append(CriticIssue(
                    category="security",
                    severity="warning",
                    location="bandit",
                    description="Найдены проблемы безопасности",
                    evidence=str(bandit_issues)[:300],
                    suggestion="Исправьте проблемы безопасности"
                ))
        
        return issues
    
    def _llm_analysis(self, code: str, tests: str, task_description: str) -> List[CriticIssue]:
        """LLM анализ для сложных паттернов."""
        issues: List[CriticIssue] = []
        
        # Ограничиваем размер для быстрого анализа
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

        from utils.config import get_config
        config = get_config()
        response = self.llm.generate(prompt, num_predict=config.llm_tokens_critic)
        
        # Парсим ответ
        if "NO_ISSUES" in response:
            return issues
        
        for line in response.split('\n'):
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
        
        return issues[:3]  # Максимум 3 от LLM
    
    def _find_strengths(self, code: str, tests: str) -> List[str]:
        """Находит сильные стороны кода."""
        strengths: List[str] = []
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return strengths
        
        # Проверяем наличие docstrings
        has_docstrings = any(
            ast.get_docstring(node) 
            for node in ast.walk(tree) 
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        )
        if has_docstrings:
            strengths.append("✓ Документация (docstrings)")
        
        # Проверяем наличие type hints
        has_type_hints = any(
            node.returns is not None or any(arg.annotation for arg in node.args.args)
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        )
        if has_type_hints:
            strengths.append("✓ Аннотации типов")
        
        # Проверяем наличие обработки ошибок
        has_error_handling = any(
            isinstance(node, ast.Try)
            for node in ast.walk(tree)
        )
        if has_error_handling:
            strengths.append("✓ Обработка исключений")
        
        # Проверяем наличие тестов
        if tests and 'def test_' in tests:
            test_count = tests.count('def test_')
            strengths.append(f"✓ Тесты ({test_count} шт.)")
        
        # Проверяем модульность
        func_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
        if func_count >= 2:
            strengths.append(f"✓ Модульность ({func_count} функций)")
        
        return strengths
    
    def _calculate_score(self, issues: List[CriticIssue]) -> float:
        """Рассчитывает общую оценку на основе проблем."""
        if not issues:
            return 1.0
        
        # Веса по severity
        severity_weights = {
            "critical": 0.25,
            "warning": 0.10,
            "info": 0.02
        }
        
        # Считаем штраф
        penalty = sum(
            severity_weights.get(issue.severity, 0.05)
            for issue in issues
        )
        
        # Ограничиваем от 0 до 1
        score = max(0.0, min(1.0, 1.0 - penalty))
        
        return round(score, 2)
    
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


# Singleton
_critic_agent: Optional[CriticAgent] = None


def get_critic_agent() -> CriticAgent:
    """Возвращает singleton экземпляр CriticAgent."""
    global _critic_agent
    if _critic_agent is None:
        _critic_agent = CriticAgent()
    return _critic_agent
