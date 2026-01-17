"""Тесты для Context Engine v0.1."""
import pytest
import tempfile
from pathlib import Path
from infrastructure.context_engine import (
    CodeChunker,
    RelevanceScorer,
    ContextComposer,
    ContextEngine,
    CodeChunk
)


@pytest.fixture
def sample_code() -> str:
    """Пример кода для тестирования."""
    return '''"""
Модуль для работы с конфигурацией.
"""
from typing import Dict, Optional

class ConfigManager:
    """Менеджер конфигурации."""
    
    def __init__(self, config: Dict):
        """Инициализация менеджера."""
        self.config = config
    
    def get(self, key: str) -> Optional[str]:
        """Получить значение по ключу."""
        return self.config.get(key)
    
    def set(self, key: str, value: str) -> None:
        """Установить значение."""
        self.config[key] = value

def load_config(path: str) -> Dict:
    """Загрузить конфигурацию из файла."""
    with open(path, 'r') as f:
        return json.load(f)
'''


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Создаёт временный проект для тестирования."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    # Создаём файл с кодом
    code_file = project_dir / "config.py"
    code_file.write_text('''
class ConfigManager:
    """Менеджер конфигурации."""
    def __init__(self):
        self.data = {}
    
    def get(self, key: str):
        return self.data.get(key)
''')
    
    # Создаём ещё один файл
    utils_file = project_dir / "utils.py"
    utils_file.write_text('''
def helper_function(x: int) -> int:
    """Вспомогательная функция."""
    return x * 2
''')
    
    return project_dir


class TestCodeChunker:
    """Тесты для CodeChunker."""
    
    def test_chunk_file_with_classes(self, sample_code: str):
        """Тест разбиения файла с классами."""
        chunker = CodeChunker()
        chunks = chunker.chunk_file("test.py", sample_code)
        
        assert len(chunks) > 0
        
        # Проверяем, что найдены класс и функции
        chunk_types = [ch.chunk_type for ch in chunks]
        assert 'class' in chunk_types
        assert 'function' in chunk_types
        
        # Проверяем метаданные
        config_chunk = next(ch for ch in chunks if ch.name == "ConfigManager")
        assert config_chunk.chunk_type == "class"
        assert "ConfigManager" in config_chunk.signature
        assert "Менеджер конфигурации" in config_chunk.docstring
    
    def test_chunk_file_simple(self):
        """Тест разбиения простого файла."""
        chunker = CodeChunker()
        simple_code = "x = 1\ny = 2\nprint(x + y)"
        chunks = chunker.chunk_file("simple.py", simple_code)
        
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "module"
        assert chunks[0].name == "simple"
    
    def test_chunk_size_limit(self):
        """Тест соблюдения лимита размера чанка."""
        # Создаём большой файл
        large_code = "class LargeClass:\n" + "    def method(self):\n        pass\n" * 100
        chunker = CodeChunker(max_chunk_tokens=50)
        chunks = chunker.chunk_file("large.py", large_code)
        
        # Проверяем, что чанки не слишком большие
        for chunk in chunks:
            assert chunk.estimated_tokens() <= chunker.max_chunk_tokens * 1.5  # Небольшой запас


class TestRelevanceScorer:
    """Тесты для RelevanceScorer."""
    
    def test_score_chunks_basic(self):
        """Тест базовой оценки релевантности."""
        scorer = RelevanceScorer()
        
        chunks = [
            CodeChunk(
                id="1",
                file_path="config.py",
                start_line=1,
                end_line=10,
                content="class ConfigManager: pass",
                chunk_type="class",
                name="ConfigManager",
                signature="class ConfigManager:"
            ),
            CodeChunk(
                id="2",
                file_path="utils.py",
                start_line=1,
                end_line=5,
                content="def helper(): pass",
                chunk_type="function",
                name="helper"
            )
        ]
        
        scored = scorer.score_chunks("config manager", chunks)
        
        assert len(scored) == 2
        # ConfigManager должен быть релевантнее для запроса "config manager"
        assert scored[0].chunk.name == "ConfigManager"
        assert scored[0].score > scored[1].score
        assert "config" in scored[0].matched_keywords
    
    def test_score_empty_query(self):
        """Тест оценки с пустым запросом."""
        scorer = RelevanceScorer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                start_line=1,
                end_line=5,
                content="x = 1",
                chunk_type="module",
                name="test"
            )
        ]
        
        scored = scorer.score_chunks("", chunks)
        assert len(scored) == 1
        assert scored[0].score == 0.0
    
    def test_score_with_keywords_in_name(self):
        """Тест бонуса за совпадение в имени."""
        scorer = RelevanceScorer()
        
        chunks = [
            CodeChunk(
                id="1",
                file_path="auth.py",
                start_line=1,
                end_line=10,
                content="def authenticate(): pass",
                chunk_type="function",
                name="authenticate",
                signature="def authenticate():"
            )
        ]
        
        scored = scorer.score_chunks("authenticate", chunks)
        
        assert len(scored) == 1
        assert scored[0].score > 0
        assert "authenticate" in scored[0].matched_keywords


class TestContextComposer:
    """Тесты для ContextComposer."""
    
    def test_compose_basic(self):
        """Тест базовой сборки контекста."""
        composer = ContextComposer(max_tokens=1000)
        
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                start_line=1,
                end_line=5,
                content="def test(): pass",
                chunk_type="function",
                name="test"
            )
        ]
        
        scored = [
            ScoredChunk(
                chunk=chunks[0],
                score=0.9,
                matched_keywords=["test"]
            )
        ]
        
        context = composer.compose(scored, "test")
        
        assert context
        assert "test.py" in context
        assert "test" in context
        assert "def test" in context or "test()" in context
    
    def test_compose_respects_token_limit(self):
        """Тест соблюдения лимита токенов."""
        composer = ContextComposer(max_tokens=100)  # Маленький лимит
        
        # Создаём много больших чанков
        chunks = []
        for i in range(10):
            large_content = f"class Class{i}:\n" + "    def method(self):\n        pass\n" * 20
            chunks.append(
                CodeChunk(
                    id=str(i),
                    file_path=f"file{i}.py",
                    start_line=1,
                    end_line=50,
                    content=large_content,
                    chunk_type="class",
                    name=f"Class{i}"
                )
            )
        
        scored = [ScoredChunk(chunk=ch, score=0.9) for ch in chunks]
        context = composer.compose(scored, "test")
        
        # Контекст должен быть ограничен лимитом токенов
        estimated_tokens = len(context) // 4
        assert estimated_tokens <= composer.max_tokens * 1.2  # Небольшой запас
    
    def test_compose_empty(self):
        """Тест сборки пустого контекста."""
        composer = ContextComposer()
        context = composer.compose([], "")
        assert context == ""


class TestContextEngine:
    """Тесты для ContextEngine."""
    
    def test_index_project(self, sample_project: Path):
        """Тест индексации проекта."""
        engine = ContextEngine()
        index = engine.index_project(str(sample_project))
        
        assert len(index) >= 2  # Должны быть проиндексированы оба файла
        assert "config.py" in index or any("config" in path for path in index.keys())
        assert "utils.py" in index or any("utils" in path for path in index.keys())
        
        # Проверяем, что чанки созданы
        for file_path, chunks in index.items():
            assert len(chunks) > 0
    
    def test_get_context(self, sample_project: Path):
        """Тест получения контекста для запроса."""
        engine = ContextEngine(max_context_tokens=500)
        context = engine.get_context("config manager", str(sample_project))
        
        assert context
        assert "config" in context.lower()
    
    def test_get_context_empty_query(self, sample_project: Path):
        """Тест получения контекста с пустым запросом."""
        engine = ContextEngine()
        context = engine.get_context("", str(sample_project))
        
        # Может быть пустым или содержать что-то
        # В зависимости от реализации, но не должен падать
        assert isinstance(context, str)
    
    def test_cache_usage(self, sample_project: Path):
        """Тест использования кэша."""
        engine = ContextEngine()
        
        # Первая индексация
        index1 = engine.index_project(str(sample_project))
        
        # Вторая индексация должна использовать кэш
        index2 = engine.index_project(str(sample_project))
        
        # Проверяем, что индексы одинаковые
        assert len(index1) == len(index2)
    
    def test_index_nonexistent_project(self):
        """Тест индексации несуществующего проекта."""
        engine = ContextEngine()
        
        with pytest.raises(ValueError, match="не найден"):
            engine.index_project("/nonexistent/path")
    
    def test_index_with_custom_extensions(self, sample_project: Path):
        """Тест индексации с кастомными расширениями."""
        engine = ContextEngine()
        
        # Создаём .txt файл
        txt_file = sample_project / "readme.txt"
        txt_file.write_text("This is a readme")
        
        # Индексируем только .txt файлы
        index = engine.index_project(str(sample_project), extensions=['.txt'])
        
        # Проверяем, что .py файлы не попали в индекс
        assert all(path.endswith('.txt') for path in index.keys())
