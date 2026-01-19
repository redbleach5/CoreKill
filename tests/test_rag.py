"""Тесты для RAG системы."""
import pytest
from infrastructure.rag import RAG


class TestRAG:
    """Тесты для класса RAG."""
    
    @pytest.fixture
    def rag(self):
        """Создаёт экземпляр RAG для тестов."""
        return RAG()
    
    def test_init(self, rag):
        """Тест инициализации RAG."""
        assert rag is not None
        assert hasattr(rag, 'db')
