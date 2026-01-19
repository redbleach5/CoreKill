"""Тесты для веб-поиска."""
import pytest
from infrastructure.web_search import WebSearch


class TestWebSearch:
    """Тесты для класса WebSearch."""
    
    @pytest.fixture
    def web_search(self):
        """Создаёт экземпляр WebSearch для тестов."""
        return WebSearch()
    
    def test_init(self, web_search):
        """Тест инициализации WebSearch."""
        assert web_search is not None
