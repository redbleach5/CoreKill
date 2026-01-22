"""Тесты для Multi-Agent Debate (Phase 5)."""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from agents.specialized_reviewers import (
    IssueSeverity,
    IssueCategory,
    ReviewIssue,
    ReviewResult,
    BaseReviewer,
    SecurityReviewer,
    PerformanceReviewer,
    CorrectnessReviewer,
    get_all_reviewers,
)
from infrastructure.debate import (
    DebateRound,
    DebateResult,
    DebateOrchestrator,
    is_debate_enabled,
    run_debate_if_enabled,
)


class TestIssueSeverity:
    """Тесты для IssueSeverity enum."""
    
    def test_severity_values(self):
        """Проверяет значения severity."""
        assert IssueSeverity.CRITICAL.value == "critical"
        assert IssueSeverity.HIGH.value == "high"
        assert IssueSeverity.MEDIUM.value == "medium"
        assert IssueSeverity.LOW.value == "low"


class TestIssueCategory:
    """Тесты для IssueCategory enum."""
    
    def test_category_values(self):
        """Проверяет значения category."""
        assert IssueCategory.SECURITY.value == "security"
        assert IssueCategory.PERFORMANCE.value == "performance"
        assert IssueCategory.CORRECTNESS.value == "correctness"


class TestReviewIssue:
    """Тесты для ReviewIssue dataclass."""
    
    def test_review_issue_creation(self):
        """Проверяет создание ReviewIssue."""
        issue = ReviewIssue(
            category=IssueCategory.SECURITY,
            severity=IssueSeverity.HIGH,
            location="line 15",
            description="SQL injection",
            evidence="f'SELECT * FROM users WHERE id = {user_id}'",
            suggestion="Use parameterized queries",
            reviewer="Security Expert"
        )
        
        assert issue.category == IssueCategory.SECURITY
        assert issue.severity == IssueSeverity.HIGH
        assert issue.location == "line 15"
        assert issue.description == "SQL injection"
    
    def test_review_issue_equality(self):
        """Проверяет сравнение issues."""
        issue1 = ReviewIssue(
            category=IssueCategory.SECURITY,
            severity=IssueSeverity.HIGH,
            location="line 15",
            description="SQL injection",
            evidence="code",
            suggestion="fix",
            reviewer="Security Expert"
        )
        issue2 = ReviewIssue(
            category=IssueCategory.SECURITY,
            severity=IssueSeverity.MEDIUM,  # Разная severity
            location="line 15",
            description="SQL injection",  # Одинаковый description
            evidence="other code",
            suggestion="other fix",
            reviewer="Other"
        )
        
        # Равны по description и location
        assert issue1 == issue2
    
    def test_review_issue_hash(self):
        """Проверяет хэширование для set."""
        issue1 = ReviewIssue(
            category=IssueCategory.SECURITY,
            severity=IssueSeverity.HIGH,
            location="line 15",
            description="SQL injection",
            evidence="code",
            suggestion="fix",
            reviewer="Expert"
        )
        issue2 = ReviewIssue(
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.LOW,
            location="line 15",
            description="SQL injection",
            evidence="other",
            suggestion="other",
            reviewer="Other"
        )
        
        # Должны быть одинаковые хэши
        assert hash(issue1) == hash(issue2)


class TestReviewResult:
    """Тесты для ReviewResult dataclass."""
    
    def test_review_result_approved(self):
        """Проверяет approved результат."""
        result = ReviewResult(
            issues=[],
            approved=True,
            summary="Проблем не найдено"
        )
        
        assert result.approved is True
        assert len(result.issues) == 0
    
    def test_review_result_not_approved(self):
        """Проверяет not approved результат."""
        issue = ReviewIssue(
            category=IssueCategory.SECURITY,
            severity=IssueSeverity.CRITICAL,
            location="line 1",
            description="Critical issue",
            evidence="code",
            suggestion="fix",
            reviewer="Expert"
        )
        result = ReviewResult(
            issues=[issue],
            approved=False,
            summary="Найдено 1 проблем"
        )
        
        assert result.approved is False
        assert len(result.issues) == 1


class TestBaseReviewer:
    """Тесты для BaseReviewer."""
    
    @patch('agents.specialized_reviewers.create_llm_for_stage')
    def test_reviewer_init(self, mock_llm):
        """Проверяет инициализацию."""
        mock_llm.return_value = Mock()
        
        reviewer = BaseReviewer(model="test-model")
        
        assert reviewer._model == "test-model"
        mock_llm.assert_called_once()
    
    @patch('agents.specialized_reviewers.create_llm_for_stage')
    def test_parse_response_no_issues(self, mock_llm):
        """Проверяет парсинг NO_ISSUES."""
        mock_llm.return_value = Mock()
        reviewer = BaseReviewer()
        
        result = reviewer._parse_response("NO_ISSUES")
        
        assert result.approved is True
        assert len(result.issues) == 0
    
    @patch('agents.specialized_reviewers.create_llm_for_stage')
    def test_parse_response_with_issues(self, mock_llm):
        """Проверяет парсинг issues."""
        mock_llm.return_value = Mock()
        reviewer = BaseReviewer()
        
        response = """
ISSUE: security|high|line 15|SQL injection|f"SELECT..."|Use params
ISSUE: performance|medium|line 20|O(n^2)|nested loops|Use set
"""
        
        result = reviewer._parse_response(response)
        
        assert len(result.issues) == 2
        assert result.issues[0].category == IssueCategory.SECURITY
        assert result.issues[0].severity == IssueSeverity.HIGH
        assert result.issues[1].category == IssueCategory.PERFORMANCE
        assert result.issues[1].severity == IssueSeverity.MEDIUM
    
    @patch('agents.specialized_reviewers.create_llm_for_stage')
    def test_parse_response_invalid_category(self, mock_llm):
        """Проверяет обработку невалидной категории."""
        mock_llm.return_value = Mock()
        reviewer = BaseReviewer()
        
        response = "ISSUE: invalid_category|high|line 1|desc|evidence|suggestion"
        
        result = reviewer._parse_response(response)
        
        # Fallback на CORRECTNESS
        assert len(result.issues) == 1
        assert result.issues[0].category == IssueCategory.CORRECTNESS


class TestSpecializedReviewers:
    """Тесты для специализированных рецензентов."""
    
    @patch('agents.specialized_reviewers.create_llm_for_stage')
    def test_security_reviewer_focus(self, mock_llm):
        """Проверяет фокус SecurityReviewer."""
        mock_llm.return_value = Mock()
        
        reviewer = SecurityReviewer()
        
        assert "SQL" in reviewer.FOCUS
        assert "injection" in reviewer.FOCUS
        assert "Security Expert" == reviewer.ROLE
    
    @patch('agents.specialized_reviewers.create_llm_for_stage')
    def test_performance_reviewer_focus(self, mock_llm):
        """Проверяет фокус PerformanceReviewer."""
        mock_llm.return_value = Mock()
        
        reviewer = PerformanceReviewer()
        
        assert "O(n²)" in reviewer.FOCUS
        assert "Performance Expert" == reviewer.ROLE
    
    @patch('agents.specialized_reviewers.create_llm_for_stage')
    def test_correctness_reviewer_focus(self, mock_llm):
        """Проверяет фокус CorrectnessReviewer."""
        mock_llm.return_value = Mock()
        
        reviewer = CorrectnessReviewer()
        
        assert "Logic errors" in reviewer.FOCUS
        assert "Correctness Expert" == reviewer.ROLE
    
    @patch('agents.specialized_reviewers.create_llm_for_stage')
    def test_get_all_reviewers(self, mock_llm):
        """Проверяет get_all_reviewers."""
        mock_llm.return_value = Mock()
        
        reviewers = get_all_reviewers()
        
        assert len(reviewers) == 3
        assert isinstance(reviewers[0], SecurityReviewer)
        assert isinstance(reviewers[1], PerformanceReviewer)
        assert isinstance(reviewers[2], CorrectnessReviewer)


class TestDebateRound:
    """Тесты для DebateRound dataclass."""
    
    def test_debate_round_creation(self):
        """Проверяет создание DebateRound."""
        round_ = DebateRound(
            round_number=1,
            code_version="def foo(): pass",
            issues_found=[],
            issues_fixed=[]
        )
        
        assert round_.round_number == 1
        assert round_.code_version == "def foo(): pass"


class TestDebateResult:
    """Тесты для DebateResult dataclass."""
    
    def test_debate_result_to_dict(self):
        """Проверяет сериализацию в dict."""
        issue = ReviewIssue(
            category=IssueCategory.SECURITY,
            severity=IssueSeverity.HIGH,
            location="line 1",
            description="Issue",
            evidence="code",
            suggestion="fix",
            reviewer="Expert"
        )
        result = DebateResult(
            final_code="def foo(): pass",
            all_issues=[issue],
            rounds=[DebateRound(1, "code", [issue], ["Issue"])],
            consensus_reached=True,
            total_rounds=1
        )
        
        d = result.to_dict()
        
        assert d["consensus"] is True
        assert d["rounds"] == 1
        assert len(d["issues"]) == 1
        assert d["issues"][0]["category"] == "security"
        assert d["fixed_count"] == 1


class TestDebateOrchestrator:
    """Тесты для DebateOrchestrator."""
    
    @patch('infrastructure.debate.get_all_reviewers')
    @patch('infrastructure.debate.get_config')
    def test_orchestrator_init(self, mock_config, mock_reviewers):
        """Проверяет инициализацию."""
        mock_config.return_value._config_data = {"multi_agent_debate": {"max_rounds": 5}}
        mock_reviewers.return_value = []
        
        orchestrator = DebateOrchestrator()
        
        assert orchestrator.max_rounds == 5
    
    @patch('infrastructure.debate.get_all_reviewers')
    @patch('infrastructure.debate.get_config')
    def test_extract_code_python_block(self, mock_config, mock_reviewers):
        """Проверяет извлечение кода из ```python блока."""
        mock_config.return_value._config_data = {}
        mock_reviewers.return_value = []
        
        orchestrator = DebateOrchestrator()
        
        response = """Here is the code:
```python
def foo():
    return 42
```
"""
        
        code = orchestrator._extract_code(response)
        
        assert "def foo():" in code
        assert "return 42" in code
    
    @patch('infrastructure.debate.get_all_reviewers')
    @patch('infrastructure.debate.get_config')
    def test_extract_code_plain_block(self, mock_config, mock_reviewers):
        """Проверяет извлечение кода из ``` блока."""
        mock_config.return_value._config_data = {}
        mock_reviewers.return_value = []
        
        orchestrator = DebateOrchestrator()
        
        response = """```
def bar():
    pass
```"""
        
        code = orchestrator._extract_code(response)
        
        assert "def bar():" in code


class TestIsDebateEnabled:
    """Тесты для is_debate_enabled."""
    
    @patch('infrastructure.debate.get_config')
    def test_enabled_true(self, mock_config):
        """Проверяет enabled=true."""
        mock_config.return_value._config_data = {
            "multi_agent_debate": {"enabled": True}
        }
        
        assert is_debate_enabled() is True
    
    @patch('infrastructure.debate.get_config')
    def test_enabled_false(self, mock_config):
        """Проверяет enabled=false."""
        mock_config.return_value._config_data = {
            "multi_agent_debate": {"enabled": False}
        }
        
        assert is_debate_enabled() is False
    
    @patch('infrastructure.debate.get_config')
    def test_missing_config(self, mock_config):
        """Проверяет отсутствие секции."""
        mock_config.return_value._config_data = {}
        
        assert is_debate_enabled() is False


class TestRunDebateIfEnabled:
    """Тесты для run_debate_if_enabled."""
    
    @pytest.mark.asyncio
    @patch('infrastructure.debate.is_debate_enabled')
    async def test_returns_original_if_disabled(self, mock_enabled):
        """Проверяет возврат оригинала если отключено."""
        mock_enabled.return_value = False
        
        code, result = await run_debate_if_enabled("def foo(): pass")
        
        assert code == "def foo(): pass"
        assert result is None
    
    @pytest.mark.asyncio
    @patch('infrastructure.debate.DebateOrchestrator')
    @patch('infrastructure.debate.is_debate_enabled')
    async def test_runs_debate_if_enabled(self, mock_enabled, mock_orch_class):
        """Проверяет запуск дебатов если включено."""
        mock_enabled.return_value = True
        
        mock_result = DebateResult(
            final_code="def foo(): return 42",
            all_issues=[],
            rounds=[],
            consensus_reached=True,
            total_rounds=1
        )
        
        mock_orch = AsyncMock()
        mock_orch.debate.return_value = mock_result
        mock_orch_class.return_value = mock_orch
        
        code, result = await run_debate_if_enabled("def foo(): pass")
        
        assert code == "def foo(): return 42"
        assert result is not None
        assert result.consensus_reached is True
