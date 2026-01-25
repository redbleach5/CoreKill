"""Тесты для ProjectProfile."""
import pytest
from pathlib import Path
from infrastructure.autonomous_improver.project_profile import (
    ProjectProfile,
    ProjectDomain,
    ProjectFramework
)


class TestProjectProfile:
    """Тесты для ProjectProfile."""
    
    def test_default_python(self):
        """Тест создания профиля по умолчанию для Python."""
        profile = ProjectProfile.default_python()
        
        assert profile.language == "python"
        assert profile.domain == ProjectDomain.BACKEND
        assert profile.framework == ProjectFramework.NONE
    
    def test_detect_from_project_python(self, temp_project_dir):
        """Тест автоопределения Python проекта."""
        # Создаём requirements.txt
        (temp_project_dir / "requirements.txt").write_text("fastapi==1.0.0")
        
        profile = ProjectProfile.detect_from_project(str(temp_project_dir))
        
        assert profile.language == "python"
        assert profile.domain == ProjectDomain.BACKEND
    
    def test_detect_from_project_typescript(self, temp_project_dir):
        """Тест автоопределения TypeScript проекта."""
        # Создаём package.json
        (temp_project_dir / "package.json").write_text('{"name": "test", "dependencies": {}}')
        (temp_project_dir / "tsconfig.json").write_text("{}")
        
        profile = ProjectProfile.detect_from_project(str(temp_project_dir))
        
        assert profile.language == "typescript"
        assert profile.domain == ProjectDomain.FRONTEND
    
    def test_detect_from_project_mixed(self, temp_project_dir):
        """Тест автоопределения mixed проекта."""
        # Создаём и requirements.txt, и package.json
        (temp_project_dir / "requirements.txt").write_text("fastapi==1.0.0")
        (temp_project_dir / "package.json").write_text('{"name": "test"}')
        
        profile = ProjectProfile.detect_from_project(str(temp_project_dir))
        
        assert profile.language == "mixed"
        assert profile.domain == ProjectDomain.FULLSTACK
    
    def test_should_analyze_file(self):
        """Тест фильтрации файлов."""
        profile = ProjectProfile.default_python()
        
        # Файл должен анализироваться
        assert profile.should_analyze_file("src/main.py") == True
        
        # Тестовый файл должен быть исключён
        assert profile.should_analyze_file("tests/test_main.py") == False
        assert profile.should_analyze_file("src/main_test.py") == False
    
    def test_get_file_priority(self):
        """Тест приоритизации файлов."""
        profile = ProjectProfile.default_python()
        
        # Агентные файлы должны иметь высокий приоритет
        priority = profile.get_file_priority("agents/coder.py")
        assert priority > 5
        
        # Обычные файлы - средний приоритет
        priority = profile.get_file_priority("utils/helper.py")
        assert priority == 5
