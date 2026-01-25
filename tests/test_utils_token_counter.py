"""Тесты для utils/token_counter.py."""
import pytest
from utils.token_counter import (
    estimate_tokens,
    estimate_workflow_tokens,
    check_token_limit
)


class TestEstimateTokens:
    """Тесты для estimate_tokens."""
    
    @pytest.mark.utils

    
    def test_estimate_tokens_empty(self):
        """Тест оценки токенов для пустой строки."""
        assert estimate_tokens("") == 0
    
    @pytest.mark.utils

    
    def test_estimate_tokens_simple(self):
        """Тест оценки токенов для простого текста."""
        text = "Hello world"
        tokens = estimate_tokens(text)
        
        # Должно быть примерно 2-3 токена
        assert tokens >= 1
        assert tokens <= 5
    
    @pytest.mark.utils

    
    def test_estimate_tokens_long_text(self):
        """Тест оценки токенов для длинного текста."""
        text = "This is a longer text with many words that should result in more tokens. " * 10
        tokens = estimate_tokens(text)
        
        # Должно быть больше токенов
        assert tokens > 10
    
    @pytest.mark.utils

    
    def test_estimate_tokens_code(self):
        """Тест оценки токенов для кода."""
        code = """
def hello():
    return "world"
"""
        tokens = estimate_tokens(code)
        
        assert tokens > 0


class TestEstimateWorkflowTokens:
    """Тесты для estimate_workflow_tokens."""
    
    @pytest.mark.utils

    
    def test_estimate_workflow_tokens_all_empty(self):
        """Тест оценки токенов когда всё пусто."""
        total = estimate_workflow_tokens(
            task="",
            plan="",
            context="",
            tests="",
            code="",
            prompts_used=[]
        )
        
        assert total == 0
    
    @pytest.mark.utils

    
    def test_estimate_workflow_tokens_with_content(self):
        """Тест оценки токенов с содержимым."""
        total = estimate_workflow_tokens(
            task="Create a calculator",
            plan="Step 1: Create functions\nStep 2: Add tests",
            context="Some context here",
            tests="def test_calc(): pass",
            code="def add(a, b): return a + b",
            prompts_used=["Prompt 1", "Prompt 2"]
        )
        
        assert total > 0
    
    @pytest.mark.utils

    
    def test_estimate_workflow_tokens_prompts(self):
        """Тест что промпты учитываются."""
        total_with_prompts = estimate_workflow_tokens(
            task="Test",
            plan="",
            context="",
            tests="",
            code="",
            prompts_used=["Prompt 1", "Prompt 2", "Prompt 3"]
        )
        
        total_without_prompts = estimate_workflow_tokens(
            task="Test",
            plan="",
            context="",
            tests="",
            code="",
            prompts_used=[]
        )
        
        assert total_with_prompts > total_without_prompts


class TestCheckTokenLimit:
    """Тесты для check_token_limit."""
    
    @pytest.mark.utils

    
    def test_check_token_limit_below_warning(self):
        """Тест когда токены ниже предупреждения."""
        result = check_token_limit(
            current_tokens=10000,
            warning_threshold=30000,
            max_tokens=50000
        )
        
        assert result["warning"] is False
        assert result["error"] is False
        assert "ok" in result["message"].lower() or "в пределах" in result["message"].lower()
    
    @pytest.mark.utils

    
    def test_check_token_limit_warning(self):
        """Тест предупреждения при приближении к лимиту."""
        result = check_token_limit(
            current_tokens=35000,
            warning_threshold=30000,
            max_tokens=50000
        )
        
        assert result["warning"] is True
        assert result["error"] is False
        # Проверяем что сообщение содержит предупреждение (на русском)
        message_lower = result["message"].lower()
        assert ("приближение" in message_lower or 
                "лимит" in message_lower or
                "warning" in message_lower)
    
    @pytest.mark.utils

    
    def test_check_token_limit_error(self):
        """Тест ошибки при превышении лимита."""
        result = check_token_limit(
            current_tokens=55000,
            warning_threshold=30000,
            max_tokens=50000
        )
        
        assert result["error"] is True
        assert "error" in result["message"].lower() or "превышен" in result["message"].lower()
    
    @pytest.mark.utils

    
    def test_check_token_limit_exact_threshold(self):
        """Тест на границе предупреждения."""
        result = check_token_limit(
            current_tokens=30000,
            warning_threshold=30000,
            max_tokens=50000
        )
        
        assert result["warning"] is True
