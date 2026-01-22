"""Оркестратор multi-agent дебатов для критического анализа кода.

Несколько агентов с разными фокусами проверяют код:
- SecurityReviewer — безопасность
- PerformanceReviewer — производительность
- CorrectnessReviewer — корректность

Если найдены критические проблемы, код исправляется и проверяется снова.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from agents.specialized_reviewers import (
    BaseReviewer,
    ReviewIssue,
    ReviewResult,
    IssueSeverity,
    get_all_reviewers,
)
from utils.config import get_config
from utils.logger import get_logger

logger = get_logger()


@dataclass
class DebateRound:
    """Один раунд дебатов."""
    round_number: int
    code_version: str
    issues_found: list[ReviewIssue]
    issues_fixed: list[str]


@dataclass
class DebateResult:
    """Результат дебатов."""
    final_code: str
    all_issues: list[ReviewIssue]
    rounds: list[DebateRound]
    consensus_reached: bool
    total_rounds: int
    
    def to_dict(self) -> dict[str, Any]:
        """Преобразует результат в словарь для сериализации."""
        return {
            "issues": [
                {
                    "category": i.category.value,
                    "severity": i.severity.value,
                    "location": i.location,
                    "description": i.description,
                    "reviewer": i.reviewer
                }
                for i in self.all_issues
            ],
            "rounds": self.total_rounds,
            "consensus": self.consensus_reached,
            "fixed_count": sum(len(r.issues_fixed) for r in self.rounds)
        }


class DebateOrchestrator:
    """Оркестрирует дебаты между агентами-рецензентами.
    
    Проводит несколько раундов ревью, пока не будет достигнут консенсус
    или не закончатся попытки.
    """
    
    def __init__(
        self,
        model: str | None = None,
        max_rounds: int | None = None,
        reviewers: list[BaseReviewer] | None = None
    ):
        """Инициализирует оркестратор.
        
        Args:
            model: Модель для LLM
            max_rounds: Максимум раундов (None = из config)
            reviewers: Список рецензентов (None = все)
        """
        config = get_config()
        debate_config = config._config_data.get("multi_agent_debate", {})
        
        self.max_rounds = max_rounds or debate_config.get("max_rounds", 3)
        self.reviewers = reviewers or get_all_reviewers(model)
        self._model = model
    
    async def debate(
        self,
        code: str,
        tests: str = "",
        task: str = ""
    ) -> DebateResult:
        """Проводит дебаты о качестве кода.
        
        Args:
            code: Код для ревью
            tests: Тесты
            task: Описание задачи
            
        Returns:
            DebateResult с финальным кодом и списком issues
        """
        logger.info("🎭 Начинаю multi-agent дебаты...")
        
        all_issues: list[ReviewIssue] = []
        rounds: list[DebateRound] = []
        current_code = code
        
        for round_num in range(1, self.max_rounds + 1):
            logger.info(f"🔄 Раунд {round_num}/{self.max_rounds}")
            
            # Все рецензенты проверяют код параллельно
            round_issues = await self._collect_reviews(
                current_code, tests, all_issues
            )
            
            # Фильтруем дубликаты
            new_issues = [
                i for i in round_issues
                if i not in all_issues
            ]
            all_issues.extend(new_issues)
            
            logger.info(f"   Найдено {len(new_issues)} новых проблем")
            
            # Проверяем есть ли критические/высокие проблемы
            high_severity = [
                i for i in new_issues
                if i.severity in (IssueSeverity.CRITICAL, IssueSeverity.HIGH)
            ]
            
            if not high_severity:
                # Консенсус достигнут
                logger.info("✅ Консенсус достигнут!")
                rounds.append(DebateRound(
                    round_number=round_num,
                    code_version=current_code,
                    issues_found=new_issues,
                    issues_fixed=[]
                ))
                break
            
            # Исправляем критические проблемы
            fixed_descriptions: list[str] = []
            for issue in high_severity:
                logger.info(f"   🔧 Исправляю: {issue.description[:50]}...")
                fixed_code = await self._fix_issue(current_code, issue)
                if fixed_code != current_code:
                    current_code = fixed_code
                    fixed_descriptions.append(issue.description)
            
            rounds.append(DebateRound(
                round_number=round_num,
                code_version=current_code,
                issues_found=new_issues,
                issues_fixed=fixed_descriptions
            ))
        
        # Определяем достигнут ли консенсус
        remaining_critical = any(
            i.severity in (IssueSeverity.CRITICAL, IssueSeverity.HIGH)
            for i in all_issues
            if i.description not in [d for r in rounds for d in r.issues_fixed]
        )
        consensus = not remaining_critical
        
        logger.info(
            f"🎭 Дебаты завершены: {len(rounds)} раундов, "
            f"{len(all_issues)} проблем, консенсус: {'✅' if consensus else '❌'}"
        )
        
        return DebateResult(
            final_code=current_code,
            all_issues=all_issues,
            rounds=rounds,
            consensus_reached=consensus,
            total_rounds=len(rounds)
        )
    
    async def _collect_reviews(
        self,
        code: str,
        tests: str,
        previous_issues: list[ReviewIssue]
    ) -> list[ReviewIssue]:
        """Собирает отзывы от всех рецензентов параллельно."""
        all_issues: list[ReviewIssue] = []
        
        # Запускаем рецензентов параллельно
        tasks = [
            asyncio.to_thread(r.review, code, tests, previous_issues)
            for r in self.reviewers
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            reviewer_name = self.reviewers[i].ROLE if i < len(self.reviewers) else "Unknown"
            
            if isinstance(result, Exception):
                logger.warning(f"⚠️ {reviewer_name} failed: {result}")
            elif isinstance(result, ReviewResult):
                all_issues.extend(result.issues)
                if result.issues:
                    logger.debug(f"   {reviewer_name}: {len(result.issues)} issues")
        
        return all_issues
    
    async def _fix_issue(self, code: str, issue: ReviewIssue) -> str:
        """Исправляет конкретную проблему через LLM."""
        from infrastructure.local_llm import create_llm_for_stage
        
        llm = create_llm_for_stage(
            stage="coding",
            model=self._model,
            temperature=0.1
        )
        
        prompt = f"""Fix this specific issue in the code:

ISSUE: {issue.description}
CATEGORY: {issue.category.value}
SEVERITY: {issue.severity.value}
LOCATION: {issue.location}
EVIDENCE: {issue.evidence}
SUGGESTION: {issue.suggestion}

CODE:
```python
{code}
```

RULES:
1. Fix ONLY the specified issue
2. Do NOT change anything else
3. Keep all existing functionality
4. Return ONLY the fixed Python code, no explanations

FIXED CODE:"""
        
        response = await asyncio.to_thread(llm.generate, prompt, 4096)
        
        # Извлекаем код из ответа
        fixed = self._extract_code(response)
        
        if fixed and len(fixed) > 50:
            return fixed
        
        return code  # Если не удалось — возвращаем оригинал
    
    def _extract_code(self, response: str) -> str:
        """Извлекает код из ответа LLM."""
        # Ищем блок ```python
        if "```python" in response:
            start = response.find("```python") + 9
            end = response.find("```", start)
            if end > start:
                return response[start:end].strip()
        
        # Ищем просто ```
        if "```" in response:
            start = response.find("```") + 3
            # Пропускаем имя языка если есть
            if response[start:start+10].strip().isalpha():
                start = response.find("\n", start) + 1
            end = response.find("```", start)
            if end > start:
                return response[start:end].strip()
        
        # Возвращаем как есть если нет блоков
        return response.strip()


def is_debate_enabled() -> bool:
    """Проверяет включены ли дебаты в конфигурации."""
    config = get_config()
    debate_config = config._config_data.get("multi_agent_debate", {})
    return debate_config.get("enabled", False)


async def run_debate_if_enabled(
    code: str,
    tests: str = "",
    task: str = "",
    model: str | None = None
) -> tuple[str, DebateResult | None]:
    """Запускает дебаты если они включены.
    
    Args:
        code: Код для ревью
        tests: Тесты
        task: Описание задачи
        model: Модель для LLM
        
    Returns:
        Tuple (final_code, DebateResult или None если отключено)
    """
    if not is_debate_enabled():
        return code, None
    
    orchestrator = DebateOrchestrator(model=model)
    result = await orchestrator.debate(code, tests, task)
    
    return result.final_code, result
