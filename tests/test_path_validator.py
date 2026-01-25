"""Тесты для PathValidator."""
import pytest
from pathlib import Path
from fastapi import HTTPException
from utils.path_validator import validate_file_path, validate_directory_path, get_project_root
import tempfile
import os


class TestGetProjectRoot:
    """Тесты для get_project_root."""
    
    def test_get_project_root_with_path(self):
        """Тест получения корня проекта с указанным путём."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = get_project_root(tmpdir)
            assert root == Path(tmpdir).resolve()
    
    def test_get_project_root_without_path(self):
        """Тест получения корня проекта без указанного пути."""
        root = get_project_root()
        # Должен вернуть текущую рабочую директорию
        assert isinstance(root, Path)
        assert root.exists()


class TestValidateFilePath:
    """Тесты для validate_file_path."""
    
    def test_validate_file_path_valid(self):
        """Тест валидации корректного пути к файлу."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")
            
            result = validate_file_path(str(test_file), project_path=tmpdir)
            assert result == test_file.resolve()
    
    def test_validate_file_path_outside_project(self):
        """Тест валидации пути вне проекта."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Создаём файл вне проекта
            outside_file = Path(tmpdir).parent / "outside.txt"
            outside_file.write_text("test")
            
            with pytest.raises(HTTPException) as exc_info:
                validate_file_path(str(outside_file), project_path=tmpdir)
            
            assert exc_info.value.status_code == 403
    
    def test_validate_file_path_empty(self):
        """Тест валидации пустого пути."""
        with pytest.raises(HTTPException) as exc_info:
            validate_file_path("")
        
        assert exc_info.value.status_code == 400
    
    def test_validate_file_path_nonexistent(self):
        """Тест валидации несуществующего файла."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = Path(tmpdir) / "nonexistent.txt"
            
            # Валидатор должен пройти (проверяет только путь, не существование)
            result = validate_file_path(str(nonexistent), project_path=tmpdir)
            assert result == nonexistent.resolve()
    
    def test_validate_file_path_path_traversal(self):
        """Тест защиты от path traversal атаки."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Попытка выйти за пределы проекта через ..
            malicious_path = str(Path(tmpdir) / ".." / ".." / "etc" / "passwd")
            
            with pytest.raises(HTTPException) as exc_info:
                validate_file_path(malicious_path, project_path=tmpdir)
            
            assert exc_info.value.status_code in (400, 403)


class TestValidateDirectoryPath:
    """Тесты для validate_directory_path."""
    
    def test_validate_directory_path_valid(self):
        """Тест валидации корректного пути к директории."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "subdir"
            test_dir.mkdir()
            
            result = validate_directory_path(str(test_dir), project_path=tmpdir)
            assert result == test_dir.resolve()
    
    def test_validate_directory_path_outside_project(self):
        """Тест валидации директории вне проекта."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outside_dir = Path(tmpdir).parent / "outside"
            outside_dir.mkdir(exist_ok=True)
            
            with pytest.raises(HTTPException) as exc_info:
                validate_directory_path(str(outside_dir), project_path=tmpdir)
            
            assert exc_info.value.status_code == 403
    
    def test_validate_directory_path_not_directory(self):
        """Тест валидации пути, который не является директорией."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            
            with pytest.raises(HTTPException) as exc_info:
                validate_directory_path(str(test_file), project_path=tmpdir)
            
            assert exc_info.value.status_code == 400
    
    def test_validate_directory_path_empty(self):
        """Тест валидации пустого пути."""
        with pytest.raises(HTTPException) as exc_info:
            validate_directory_path("")
        
        assert exc_info.value.status_code == 400
