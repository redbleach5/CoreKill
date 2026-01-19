"""Тесты для RAG системы."""
import pytest
from infrastructure.rag import RAGSystem


class TestRAG:
    """Тесты для класса RAGSystem."""
    
    @pytest.fixture
    def rag(self):
        """Создаёт экземпляр RAGSystem для тестов."""
        return RAGSystem(collection_name="test_collection", persist_directory=".chromadb_test")
    
    def test_init(self, rag):
        """Тест инициализации RAGSystem."""
        assert rag is not None
        assert hasattr(rag, 'collection')
