"""Тесты для адаптеров."""
import pytest
from pathlib import Path
from infrastructure.autonomous_improver.adapters import (
    PythonAdapter,
    FrontendAdapter,
    MultiAdapter
)


class TestPythonAdapter:
    """Тесты для PythonAdapter."""
    
    def test_language(self):
        """Тест свойства language."""
        adapter = PythonAdapter()
        assert adapter.language == "python"
    
    def test_file_extensions(self):
        """Тест поддерживаемых расширений."""
        adapter = PythonAdapter()
        assert ".py" in adapter.file_extensions
    
    def test_discover_files(self, temp_project_dir, sample_python_file):
        """Тест поиска Python файлов."""
        adapter = PythonAdapter()
        files = adapter.discover_files(temp_project_dir)
        
        assert len(files) >= 1
        assert sample_python_file in files
    
    def test_analyze_structure(self, sample_python_file):
        """Тест анализа структуры Python файла."""
        adapter = PythonAdapter()
        structure = adapter.analyze_structure(sample_python_file)
        
        assert structure is not None
        assert len(structure.functions) >= 1
    
    def test_validate_file_path(self):
        """Тест валидации пути."""
        adapter = PythonAdapter()
        
        # Несуществующий файл
        fake_path = Path("/nonexistent/file.py")
        assert adapter._validate_file_path(fake_path) == False
        
        # Существующий файл (если есть)
        # Этот тест требует реального файла, поэтому пропускаем


class TestFrontendAdapter:
    """Тесты для FrontendAdapter."""
    
    def test_language(self):
        """Тест свойства language."""
        adapter = FrontendAdapter()
        assert adapter.language == "frontend"
    
    def test_file_extensions(self):
        """Тест поддерживаемых расширений."""
        adapter = FrontendAdapter()
        assert ".ts" in adapter.file_extensions
        assert ".tsx" in adapter.file_extensions
        assert ".js" in adapter.file_extensions
        assert ".html" in adapter.file_extensions
        assert ".md" in adapter.file_extensions
        assert ".json" in adapter.file_extensions
    
    def test_analyze_structure_typescript(self, sample_typescript_file):
        """Тест анализа TypeScript файла."""
        adapter = FrontendAdapter()
        structure = adapter.analyze_structure(sample_typescript_file)
        
        assert structure is not None
        assert structure.file_type == "typescript"
        assert len(structure.components) >= 1
    
    def test_analyze_structure_html(self, sample_html_file):
        """Тест анализа HTML файла."""
        adapter = FrontendAdapter()
        structure = adapter.analyze_structure(sample_html_file)
        
        assert structure is not None
        assert structure.file_type == "html"


class TestMultiAdapter:
    """Тесты для MultiAdapter."""
    
    def test_language(self):
        """Тест свойства language."""
        adapter = MultiAdapter([PythonAdapter(), FrontendAdapter()])
        assert adapter.language == "mixed"
    
    def test_file_extensions(self):
        """Тест поддерживаемых расширений."""
        adapter = MultiAdapter([PythonAdapter(), FrontendAdapter()])
        extensions = adapter.file_extensions
        
        assert ".py" in extensions
        assert ".ts" in extensions
        assert ".tsx" in extensions
    
    def test_get_adapter_for_file(self, sample_python_file, sample_typescript_file):
        """Тест выбора адаптера для файла."""
        adapter = MultiAdapter([PythonAdapter(), FrontendAdapter()])
        
        # Python файл должен использовать PythonAdapter
        python_adapter = adapter._get_adapter_for_file(sample_python_file)
        assert python_adapter is not None
        assert python_adapter.language == "python"
        
        # TypeScript файл должен использовать FrontendAdapter
        ts_adapter = adapter._get_adapter_for_file(sample_typescript_file)
        assert ts_adapter is not None
        assert ts_adapter.language == "frontend"
