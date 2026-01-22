"""Специализированные агенты-рецензенты для multi-agent debate.

Три рецензента с разными фокусами анализируют код:
- SecurityReviewer — уязвимости и безопасность
- PerformanceReviewer — производительность и алгоритмы
- CorrectnessReviewer — логика и обработка ошибок
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from infrastructure.local_llm import create_llm_for_stage
from utils.logger import get_logger

logger = get_logger()


class IssueSeverity(str, Enum):
    """Серьёзность проблемы."""
    CRITICAL = "critical"  # Блокирует релиз
    HIGH = "high"          # Нужно исправить
    MEDIUM = "medium"      # Желательно исправить
    LOW = "low"            # Косметическое


class IssueCategory(str, Enum):
    """Категория проблемы."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    CORRECTNESS = "correctness"
    MAINTAINABILITY = "maintainability"
    STYLE = "style"


@dataclass
class ReviewIssue:
    """Проблема найденная рецензентом."""
    category: IssueCategory
    severity: IssueSeverity
    location: str
    description: str
    evidence: str
    suggestion: str
    reviewer: str
    
    def __eq__(self, other: object) -> bool:
        """Сравнение по описанию и местоположению."""
        if not isinstance(other, ReviewIssue):
            return False
        return self.description == other.description and self.location == other.location
    
    def __hash__(self) -> int:
        """Хэш для использования в set."""
        return hash((self.description, self.location))


@dataclass
class ReviewResult:
    """Результат ревью."""
    issues: list[ReviewIssue]
    approved: bool
    summary: str


class BaseReviewer:
    """Базовый класс для рецензентов.
    
    Каждый рецензент фокусируется на своей области и возвращает
    структурированный список проблем.
    """
    
    ROLE: str = "Code Reviewer"
    FOCUS: str = "general code quality issues"
    
    def __init__(self, model: str | None = None):
        """Инициализирует рецензента.
        
        Args:
            model: Модель для LLM (None = default)
        """
        self.llm = create_llm_for_stage(
            stage="critic",
            model=model,
            temperature=0.1  # Низкая для точности
        )
        self._model = model
    
    def review(
        self,
        code: str,
        tests: str = "",
        previous_issues: list[ReviewIssue] | None = None
    ) -> ReviewResult:
        """Проводит ревью кода.
        
        Args:
            code: Код для проверки
            tests: Тесты (опционально)
            previous_issues: Уже найденные проблемы (чтобы не дублировать)
            
        Returns:
            ReviewResult с найденными проблемами
        """
        logger.debug(f"🔍 {self.ROLE} начинает ревью...")
        
        prompt = self._build_prompt(code, tests, previous_issues)
        response = self.llm.generate(prompt, num_predict=1024)
        result = self._parse_response(response)
        
        logger.debug(f"   {self.ROLE}: найдено {len(result.issues)} проблем")
        
        return result
    
    def _build_prompt(
        self,
        code: str,
        tests: str,
        previous_issues: list[ReviewIssue] | None
    ) -> str:
        """Строит промпт для ревью."""
        previous = ""
        if previous_issues:
            issues_list = "\n".join(
                f"- [{i.severity.value}] {i.category.value}: {i.description}"
                for i in previous_issues
            )
            previous = f"\nAlready found issues (DO NOT repeat these):\n{issues_list}\n"
        
        tests_section = ""
        if tests.strip():
            tests_section = f"\nTESTS:\n```python\n{tests[:500]}\n```"
        
        return f"""You are a {self.ROLE}. Focus ONLY on: {self.FOCUS}

CODE:
```python
{code[:3000]}
```
{tests_section}
{previous}
Find NEW issues (not already listed). For each issue, output EXACTLY this format:
ISSUE: <category>|<severity>|<location>|<description>|<evidence>|<suggestion>

Categories: security, performance, correctness, maintainability
Severities: critical, high, medium, low

Example:
ISSUE: security|high|line 15|SQL injection vulnerability|query = f"SELECT * FROM users WHERE id = {{user_id}}"|Use parameterized queries

If no NEW issues found, output: NO_ISSUES

Response:"""
    
    def _parse_response(self, response: str) -> ReviewResult:
        """Парсит ответ LLM."""
        issues: list[ReviewIssue] = []
        
        if "NO_ISSUES" in response.upper():
            return ReviewResult(
                issues=[],
                approved=True,
                summary="Проблем не найдено"
            )
        
        for line in response.split('\n'):
            line = line.strip()
            if line.upper().startswith('ISSUE:'):
                parts = line[6:].split('|')
                if len(parts) >= 6:
                    try:
                        category_str = parts[0].strip().lower()
                        severity_str = parts[1].strip().lower()
                        
                        # Валидация enum значений
                        try:
                            category = IssueCategory(category_str)
                        except ValueError:
                            category = IssueCategory.CORRECTNESS
                        
                        try:
                            severity = IssueSeverity(severity_str)
                        except ValueError:
                            severity = IssueSeverity.MEDIUM
                        
                        issues.append(ReviewIssue(
                            category=category,
                            severity=severity,
                            location=parts[2].strip(),
                            description=parts[3].strip(),
                            evidence=parts[4].strip(),
                            suggestion=parts[5].strip(),
                            reviewer=self.ROLE
                        ))
                    except (ValueError, IndexError):
                        continue
        
        has_blocking = any(
            i.severity in (IssueSeverity.CRITICAL, IssueSeverity.HIGH)
            for i in issues
        )
        
        return ReviewResult(
            issues=issues,
            approved=not has_blocking,
            summary=f"Найдено {len(issues)} проблем"
        )


class SecurityReviewer(BaseReviewer):
    """Рецензент безопасности.
    
    Фокусируется на уязвимостях: injection, path traversal,
    hardcoded secrets, unsafe deserialization.
    """
    
    ROLE = "Security Expert"
    FOCUS = """
- SQL/NoSQL injection (f-strings in queries, string concatenation)
- Command injection (subprocess with shell=True, os.system, eval, exec)
- Path traversal (../, user input in file paths)
- Hardcoded secrets/passwords/API keys
- Unsafe deserialization (pickle.load, yaml.load without Loader)
- SSRF vulnerabilities (user-controlled URLs)
- XSS in web contexts (unescaped user input in HTML)
- Insecure random (random instead of secrets for tokens)
"""


class PerformanceReviewer(BaseReviewer):
    """Рецензент производительности.
    
    Фокусируется на алгоритмической сложности, утечках памяти,
    неоптимальных паттернах.
    """
    
    ROLE = "Performance Expert"
    FOCUS = """
- O(n²) or worse algorithms where O(n) or O(n log n) is possible
- Nested loops that could be optimized with sets/dicts
- Unnecessary iterations (multiple passes when one is enough)
- Memory leaks (unclosed files, connections, missing context managers)
- N+1 query problems (queries in loops)
- Missing caching for expensive operations
- Blocking I/O in async context
- Creating objects in loops when could be created once
"""


class CorrectnessReviewer(BaseReviewer):
    """Рецензент корректности.
    
    Фокусируется на логических ошибках, edge cases,
    обработке ошибок.
    """
    
    ROLE = "Correctness Expert"
    FOCUS = """
- Logic errors (wrong conditions, inverted logic)
- Off-by-one errors (< vs <=, range issues)
- Unhandled edge cases (None, empty list, empty string, negative numbers, zero)
- Type mismatches (int vs str, list vs None)
- Race conditions in concurrent code
- Missing error handling (bare except, swallowing exceptions)
- Uninitialized variables
- Incorrect return types
"""


def get_all_reviewers(model: str | None = None) -> list[BaseReviewer]:
    """Возвращает список всех рецензентов.
    
    Args:
        model: Модель для LLM
        
    Returns:
        Список рецензентов
    """
    return [
        SecurityReviewer(model),
        PerformanceReviewer(model),
        CorrectnessReviewer(model),
    ]
