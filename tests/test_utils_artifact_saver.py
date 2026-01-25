"""Тесты для utils/artifact_saver.py."""
import pytest
import tempfile
import json
from pathlib import Path
from utils.artifact_saver import ArtifactSaver


class TestArtifactSaverInit:
    """Тесты инициализации ArtifactSaver."""
    
    @pytest.mark.utils

    
    def test_init_default_directory(self):
        """Тест инициализации с директорией по умолчанию."""
        saver = ArtifactSaver()
        
        assert saver.base_output_dir == Path("output")
        assert saver.current_task_dir is None
    
    @pytest.mark.utils

    
    def test_init_custom_directory(self):
        """Тест инициализации с кастомной директорией."""
        saver = ArtifactSaver(base_output_dir="custom_output")
        
        assert saver.base_output_dir == Path("custom_output")


class TestArtifactSaverCreateTaskDirectory:
    """Тесты для create_task_directory."""
    
    @pytest.mark.utils

    
    def test_create_task_directory(self):
        """Тест создания директории задачи."""
        with tempfile.TemporaryDirectory() as tmpdir:
            saver = ArtifactSaver(base_output_dir=tmpdir)
            
            task_dir = saver.create_task_directory("Test task")
            
            assert task_dir.exists()
            assert task_dir.is_dir()
            assert saver.current_task_dir == task_dir
    
    @pytest.mark.utils

    
    def test_create_task_directory_safe_name(self):
        """Тест безопасного имени директории."""
        with tempfile.TemporaryDirectory() as tmpdir:
            saver = ArtifactSaver(base_output_dir=tmpdir)
            
            # Имя с недопустимыми символами
            task_dir = saver.create_task_directory("Test/task:name*with?invalid<chars>")
            
            # Должно быть безопасное имя
            assert task_dir.exists()
            assert "/" not in task_dir.name or ":" not in task_dir.name


class TestArtifactSaverSaveCode:
    """Тесты для save_code."""
    
    @pytest.mark.utils

    
    def test_save_code(self):
        """Тест сохранения кода."""
        with tempfile.TemporaryDirectory() as tmpdir:
            saver = ArtifactSaver(base_output_dir=tmpdir)
            saver.create_task_directory("Test task")
            
            code = "def hello():\n    return 'world'"
            file_path = saver.save_code(code, "test.py")
            
            assert file_path.exists()
            assert file_path.read_text() == code
    
    @pytest.mark.utils

    
    def test_save_code_default_filename(self):
        """Тест сохранения кода с именем по умолчанию."""
        with tempfile.TemporaryDirectory() as tmpdir:
            saver = ArtifactSaver(base_output_dir=tmpdir)
            saver.create_task_directory("Test task")
            
            code = "print('hello')"
            file_path = saver.save_code(code)
            
            assert file_path.name == "code.py"
            assert file_path.read_text() == code
    
    @pytest.mark.utils

    
    def test_save_code_no_directory(self):
        """Тест сохранения кода без создания директории."""
        with tempfile.TemporaryDirectory() as tmpdir:
            saver = ArtifactSaver(base_output_dir=tmpdir)
            
            with pytest.raises(ValueError):
                saver.save_code("code", "test.py")


class TestArtifactSaverSaveTests:
    """Тесты для save_tests."""
    
    @pytest.mark.utils

    
    def test_save_tests(self):
        """Тест сохранения тестов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            saver = ArtifactSaver(base_output_dir=tmpdir)
            saver.create_task_directory("Test task")
            
            tests = "def test_hello():\n    assert hello() == 'world'"
            file_path = saver.save_tests(tests, "test_code.py")
            
            assert file_path.exists()
            assert file_path.read_text() == tests


class TestArtifactSaverSaveReflection:
    """Тесты для save_reflection."""
    
    @pytest.mark.utils

    
    def test_save_reflection(self):
        """Тест сохранения рефлексии."""
        with tempfile.TemporaryDirectory() as tmpdir:
            saver = ArtifactSaver(base_output_dir=tmpdir)
            saver.create_task_directory("Test task")
            
            reflection_data = {
                "planning_score": 0.8,
                "research_score": 0.7,
                "testing_score": 0.9,
                "coding_score": 0.85,
                "overall_score": 0.81,
                "analysis": "Test analysis",
                "improvements": "Test improvements",
                "should_retry": False
            }
            file_path = saver.save_reflection(reflection_data, "reflection.md")
            
            assert file_path.exists()
            content = file_path.read_text()
            assert "Рефлексия" in content or "Reflection" in content
            assert "0.80" in content or "0.8" in content


class TestArtifactSaverSaveMetrics:
    """Тесты для save_metrics."""
    
    @pytest.mark.utils

    
    def test_save_metrics(self):
        """Тест сохранения метрик."""
        with tempfile.TemporaryDirectory() as tmpdir:
            saver = ArtifactSaver(base_output_dir=tmpdir)
            saver.create_task_directory("Test task")
            
            metrics = {"duration": 10.5, "tokens": 1000}
            file_path = saver.save_metrics(metrics, "metrics.json")
            
            assert file_path.exists()
            loaded_metrics = json.loads(file_path.read_text())
            # Функция добавляет timestamp, проверяем что основные метрики есть
            assert loaded_metrics["duration"] == metrics["duration"]
            assert loaded_metrics["tokens"] == metrics["tokens"]
            assert "timestamp" in loaded_metrics


class TestArtifactSaverSaveAllArtifacts:
    """Тесты для save_all_artifacts."""
    
    @pytest.mark.utils

    
    def test_save_all_artifacts(self):
        """Тест сохранения всех артефактов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            saver = ArtifactSaver(base_output_dir=tmpdir)
            
            saver.save_all_artifacts(
                task="Test task",
                code="def hello(): pass",
                tests="def test_hello(): pass",
                reflection_data={
                    "analysis": "Test analysis",
                    "improvements": "Test improvements",
                    "planning_score": 0.8,
                    "overall_score": 0.75
                },
                metrics={"duration": 10.0}
            )
            
            # Проверяем что директория создана
            assert saver.current_task_dir is not None
            assert saver.current_task_dir.exists()
            
            # Проверяем что файлы созданы
            assert (saver.current_task_dir / "code.py").exists()
            assert (saver.current_task_dir / "tests.py").exists()
            assert (saver.current_task_dir / "reflection.md").exists()
            assert (saver.current_task_dir / "metrics.json").exists()
    
    @pytest.mark.utils

    
    def test_save_all_artifacts_partial(self):
        """Тест сохранения части артефактов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            saver = ArtifactSaver(base_output_dir=tmpdir)
            
            saver.save_all_artifacts(
                task="Test task",
                code="def hello(): pass",
                tests=None,
                reflection_data=None,
                metrics=None
            )
            
            # Должен быть создан только код
            assert (saver.current_task_dir / "code.py").exists()
            assert not (saver.current_task_dir / "tests.py").exists()
