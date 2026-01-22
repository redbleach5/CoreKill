"""Тесты для Code Retrieval (Phase 4)."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from infrastructure.code_retrieval import (
    CodeExample,
    CodeRetriever,
    is_code_retrieval_enabled,
    get_code_retriever
)


class TestCodeExample:
    """Тесты для CodeExample dataclass."""
    
    def test_code_example_creation(self):
        """Проверяет создание CodeExample."""
        example = CodeExample(
            code="def foo(): pass",
            description="Test function",
            source="local"
        )
        
        assert example.code == "def foo(): pass"
        assert example.description == "Test function"
        assert example.source == "local"
        assert example.relevance_score == 0.0
        assert example.quality_score == 0.0
        assert example.language == "python"
    
    def test_code_example_formatted(self):
        """Проверяет форматирование для промпта."""
        example = CodeExample(
            code="def bar(): return 42",
            description="Returns 42",
            source="history"
        )
        
        formatted = example.formatted
        
        assert "# Example (from history):" in formatted
        assert "# Returns 42" in formatted
        assert "def bar(): return 42" in formatted
    
    def test_code_example_formatted_local(self):
        """Проверяет форматирование для local источника."""
        example = CodeExample(
            code="class Foo: pass",
            description="Foo class",
            source="local"
        )
        
        assert "from project" in example.formatted
    
    def test_code_example_formatted_github(self):
        """Проверяет форматирование для github источника."""
        example = CodeExample(
            code="async def async_foo(): pass",
            description="Async function",
            source="github"
        )
        
        assert "from GitHub" in example.formatted


class TestCodeRetriever:
    """Тесты для CodeRetriever."""
    
    def test_retriever_init(self):
        """Проверяет инициализацию."""
        retriever = CodeRetriever(
            embedding_model="test-model",
            collection_name="test_collection",
            chroma_path=".test_chroma"
        )
        
        assert retriever._embedding_model_name == "test-model"
        assert retriever._collection_name == "test_collection"
        assert retriever._chroma_path == ".test_chroma"
        assert retriever._embedding_model is None  # Ленивая инициализация
    
    def test_estimate_quality_good_code(self):
        """Проверяет оценку качества хорошего кода."""
        retriever = CodeRetriever()
        
        good_code = '''def calculate_total(items: list[int]) -> int:
    """Calculates total sum of items."""
    return sum(items)
'''
        
        score = retriever._estimate_quality(good_code)
        
        # Хороший код: def + docstring + type hints + return
        assert score >= 0.7
    
    def test_estimate_quality_bad_code(self):
        """Проверяет оценку качества плохого кода."""
        retriever = CodeRetriever()
        
        bad_code = "x = 1  # TODO: fix"
        
        score = retriever._estimate_quality(bad_code)
        
        # Плохой код: короткий, TODO, нет def/class
        assert score <= 0.5
    
    def test_estimate_quality_with_pass(self):
        """Проверяет штраф за множественные pass."""
        retriever = CodeRetriever()
        
        stub_code = """def a(): pass
def b(): pass
def c(): pass"""
        
        score = retriever._estimate_quality(stub_code)
        
        # Множественные pass снижают качество
        assert score < 0.6
    
    def test_extract_relevant_snippet_function(self):
        """Проверяет извлечение функции."""
        retriever = CodeRetriever()
        
        content = '''import os

def calculate_sum(numbers: list) -> int:
    """Calculate sum."""
    return sum(numbers)

def other_func():
    pass
'''
        
        snippet = retriever._extract_relevant_snippet(content, "calculate sum")
        
        assert snippet is not None
        assert "calculate_sum" in snippet
        assert "sum(numbers)" in snippet
    
    def test_extract_relevant_snippet_invalid_syntax(self):
        """Проверяет обработку синтаксически неверного кода."""
        retriever = CodeRetriever()
        
        invalid_code = "def broken(: pass"
        
        result = retriever._extract_relevant_snippet(invalid_code, "test")
        
        assert result is None
    
    def test_rank_examples(self):
        """Проверяет ранжирование примеров."""
        retriever = CodeRetriever()
        
        examples = [
            CodeExample(
                code="def a(): pass",
                description="A",
                source="github",
                relevance_score=0.8
            ),
            CodeExample(
                code='def b() -> int:\n    """Doc."""\n    return 1',
                description="B",
                source="local",
                relevance_score=0.7
            ),
        ]
        
        ranked = retriever._rank_examples(examples, "test")
        
        # Local с лучшим качеством должен быть выше github
        assert len(ranked) == 2
        assert ranked[0].source == "local"
    
    def test_get_stats_not_initialized(self):
        """Проверяет статистику без инициализации."""
        retriever = CodeRetriever()
        
        stats = retriever.get_stats()
        
        assert stats["initialized"] is False
        assert stats["count"] == 0


class TestIsCodeRetrievalEnabled:
    """Тесты для is_code_retrieval_enabled."""
    
    @patch('infrastructure.code_retrieval.get_config')
    def test_enabled_true(self, mock_config):
        """Проверяет что возвращает True если enabled."""
        mock_config.return_value._config_data = {
            "code_retrieval": {"enabled": True}
        }
        
        assert is_code_retrieval_enabled() is True
    
    @patch('infrastructure.code_retrieval.get_config')
    def test_enabled_false(self, mock_config):
        """Проверяет что возвращает False если disabled."""
        mock_config.return_value._config_data = {
            "code_retrieval": {"enabled": False}
        }
        
        assert is_code_retrieval_enabled() is False
    
    @patch('infrastructure.code_retrieval.get_config')
    def test_missing_config(self, mock_config):
        """Проверяет что возвращает False если секция отсутствует."""
        mock_config.return_value._config_data = {}
        
        assert is_code_retrieval_enabled() is False


class TestGetCodeRetriever:
    """Тесты для get_code_retriever."""
    
    @patch('infrastructure.code_retrieval.is_code_retrieval_enabled')
    def test_returns_none_if_disabled(self, mock_enabled):
        """Проверяет что возвращает None если отключено."""
        mock_enabled.return_value = False
        
        result = get_code_retriever()
        
        assert result is None
    
    @patch('infrastructure.code_retrieval.is_code_retrieval_enabled')
    @patch('infrastructure.code_retrieval.get_config')
    def test_returns_retriever_if_enabled(self, mock_config, mock_enabled):
        """Проверяет что возвращает CodeRetriever если включено."""
        mock_enabled.return_value = True
        mock_config.return_value._config_data = {
            "code_retrieval": {
                "embedding_model": "test-model",
                "chroma_path": ".test_chroma"
            }
        }
        
        result = get_code_retriever()
        
        assert result is not None
        assert isinstance(result, CodeRetriever)
        assert result._embedding_model_name == "test-model"
