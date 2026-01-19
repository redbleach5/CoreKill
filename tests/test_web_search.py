"""Тесты для веб-поиска."""
import pytest
from infrastructure.web_search import (
    web_search, 
    tavily_search, 
    duckduckgo_search, 
    google_search
)


class TestWebSearch:
    """Тесты для функций веб-поиска."""
    
    def test_web_search_empty_query(self):
        """Тест веб-поиска с пустым запросом."""
        results = web_search("")
        assert results == []
    
    def test_web_search_returns_list(self):
        """Тест что веб-поиск возвращает список."""
        # Не делаем реальный запрос в тестах, проверяем только типы
        results = web_search("", max_results=3)
        assert isinstance(results, list)
