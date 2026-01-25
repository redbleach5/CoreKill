"""Тесты для infrastructure/task_checkpointer.py."""
import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from infrastructure.task_checkpointer import TaskCheckpointer, TaskMetadata
from infrastructure.workflow_state import AgentState


class TestTaskMetadata:
    """Тесты для TaskMetadata."""
    
    @pytest.mark.infrastructure

    
    def test_task_metadata_creation(self):
        """Тест создания TaskMetadata."""
        metadata = TaskMetadata(
            task_id="test-123",
            task_text="Test task",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
            last_stage="intent",
            status="running",
            iteration=1,
            model="test-model"
        )
        
        assert metadata.task_id == "test-123"
        assert metadata.task_text == "Test task"
        assert metadata.status == "running"
    
    @pytest.mark.infrastructure

    
    def test_task_metadata_to_dict(self):
        """Тест сериализации в словарь."""
        metadata = TaskMetadata(
            task_id="test-123",
            task_text="Test task",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
            last_stage="intent",
            status="running",
            iteration=1
        )
        
        data = metadata.to_dict()
        
        assert isinstance(data, dict)
        assert data["task_id"] == "test-123"
        assert data["task_text"] == "Test task"
    
    @pytest.mark.infrastructure

    
    def test_task_metadata_from_dict(self):
        """Тест восстановления из словаря."""
        data = {
            "task_id": "test-123",
            "task_text": "Test task",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "last_stage": "intent",
            "status": "running",
            "iteration": 1,
            "model": None
        }
        
        metadata = TaskMetadata.from_dict(data)
        
        assert metadata.task_id == "test-123"
        assert metadata.task_text == "Test task"
        assert metadata.status == "running"


class TestTaskCheckpointerInit:
    """Тесты инициализации TaskCheckpointer."""
    
    @pytest.mark.infrastructure

    
    def test_init_creates_directory(self):
        """Тест создания директории при инициализации."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir)
            
            assert Path(tmpdir).exists()
            assert checkpointer.checkpoint_dir == Path(tmpdir)
    
    @pytest.mark.infrastructure

    
    def test_init_default_directory(self):
        """Тест инициализации с директорией по умолчанию."""
        checkpointer = TaskCheckpointer()
        
        assert checkpointer.checkpoint_dir == Path(".task_checkpoints")
        assert checkpointer.max_age_hours == 24


class TestTaskCheckpointerSave:
    """Тесты для сохранения checkpoint."""
    
    @pytest.mark.infrastructure

    
    def test_save_checkpoint(self):
        """Тест сохранения checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir)
            
            state = AgentState(
                task="Test task",
                task_id="test-123",
                model="test-model"
            )
            
            checkpointer.save_checkpoint("test-123", state, "intent", "running")
            
            # Проверяем что файлы созданы
            task_dir = checkpointer._get_task_dir("test-123")
            assert task_dir.exists()
            assert (task_dir / "metadata.json").exists()
            assert (task_dir / "state.json").exists()
    
    @pytest.mark.infrastructure

    
    def test_save_checkpoint_metadata_content(self):
        """Тест содержимого сохранённого metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir)
            
            state = AgentState(task="Test", task_id="test-123")
            
            checkpointer.save_checkpoint("test-123", state, "intent", "running")
            
            # Читаем metadata
            task_dir = checkpointer._get_task_dir("test-123")
            with open(task_dir / "metadata.json", "r") as f:
                saved_metadata = json.load(f)
            
            assert saved_metadata["task_id"] == "test-123"
            assert saved_metadata["last_stage"] == "intent"
            assert saved_metadata["status"] == "running"


class TestTaskCheckpointerLoad:
    """Тесты для загрузки checkpoint."""
    
    @pytest.mark.infrastructure

    
    def test_load_checkpoint(self):
        """Тест загрузки checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir)
            
            # Сохраняем checkpoint
            state = AgentState(
                task="Test task",
                task_id="test-123",
                model="test-model"
            )
            checkpointer.save_checkpoint("test-123", state, "intent", "running")
            
            # Загружаем checkpoint
            result = checkpointer.load_checkpoint("test-123")
            
            assert result is not None
            loaded_state, loaded_metadata = result
            assert loaded_state is not None
            assert loaded_metadata is not None
            assert loaded_state["task"] == "Test task"
            assert loaded_metadata.task_id == "test-123"
    
    @pytest.mark.infrastructure

    
    def test_load_checkpoint_not_found(self):
        """Тест загрузки несуществующего checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir)
            
            result = checkpointer.load_checkpoint("non-existent")
            
            assert result is None


class TestTaskCheckpointerList:
    """Тесты для списка checkpoint."""
    
    @pytest.mark.infrastructure

    
    def test_list_all_tasks(self):
        """Тест получения списка всех задач."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir)
            
            # Создаём несколько checkpoint
            for i in range(3):
                state = AgentState(task=f"Task {i}", task_id=f"task-{i}")
                checkpointer.save_checkpoint(f"task-{i}", state, "intent", "running")
            
            tasks = checkpointer.list_all_tasks()
            
            assert len(tasks) == 3
            assert all(isinstance(task, TaskMetadata) for task in tasks)
            assert all(task.task_id in [f"task-{i}" for i in range(3)] for task in tasks)
    
    @pytest.mark.infrastructure

    
    def test_list_active_tasks(self):
        """Тест получения списка активных задач."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir)
            
            # Создаём активные и завершённые задачи
            for i, status in enumerate(["running", "paused", "completed"]):
                state = AgentState(task=f"Task {i}", task_id=f"task-{i}")
                checkpointer.save_checkpoint(f"task-{i}", state, "intent", status)
            
            active_tasks = checkpointer.list_active_tasks()
            
            # Только running и paused считаются активными
            assert len(active_tasks) == 2
            assert all(isinstance(task, TaskMetadata) for task in active_tasks)
            assert all(task.status in ["running", "paused"] for task in active_tasks)


class TestTaskCheckpointerCleanup:
    """Тесты для очистки старых checkpoint."""
    
    @pytest.mark.infrastructure

    
    def test_cleanup_old_checkpoints(self):
        """Тест очистки старых checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir, max_age_hours=1)
            
            # Создаём старый checkpoint (имитируем старый файл)
            old_task_dir = checkpointer._get_task_dir("old-task")
            old_task_dir.mkdir(parents=True)
            
            old_metadata = TaskMetadata(
                task_id="old-task",
                task_text="Old task",
                created_at=(datetime.now() - timedelta(hours=2)).isoformat(),
                updated_at=(datetime.now() - timedelta(hours=2)).isoformat(),
                last_stage="intent",
                status="completed",
                iteration=1
            )
            
            with open(old_task_dir / "metadata.json", "w") as f:
                json.dump(old_metadata.to_dict(), f)
            
            # Создаём новый checkpoint
            new_state = AgentState(task="New task", task_id="new-task")
            checkpointer.save_checkpoint("new-task", new_state, "intent", "running")
            
            # Очищаем старые
            checkpointer._cleanup_old_checkpoints()
            
            # Старый должен быть удалён, новый остаться
            assert not old_task_dir.exists()
            assert checkpointer._get_task_dir("new-task").exists()
    
    @pytest.mark.infrastructure

    
    def test_delete_checkpoint(self):
        """Тест удаления checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir)
            
            # Создаём checkpoint
            state = AgentState(task="Test", task_id="test-123")
            checkpointer.save_checkpoint("test-123", state, "intent", "running")
            
            task_dir = checkpointer._get_task_dir("test-123")
            assert task_dir.exists()
            
            # Удаляем
            checkpointer.delete_checkpoint("test-123")
            
            assert not task_dir.exists()


class TestTaskCheckpointerSerialization:
    """Тесты для сериализации состояния."""
    
    @pytest.mark.infrastructure

    
    def test_serialize_state_simple(self):
        """Тест сериализации простого состояния."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir)
            
            state = AgentState(
                task="Test task",
                task_id="test-123",
                model="test-model",
                temperature=0.25
            )
            
            serialized = checkpointer._serialize_state(state)
            
            assert isinstance(serialized, dict)
            assert serialized["task"] == "Test task"
            assert serialized["task_id"] == "test-123"
            assert serialized["model"] == "test-model"
            assert serialized["temperature"] == 0.25
    
    @pytest.mark.infrastructure

    
    def test_serialize_state_with_none(self):
        """Тест сериализации состояния с None значениями."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpointer = TaskCheckpointer(checkpoint_dir=tmpdir)
            
            state = AgentState(
                task="Test",
                task_id="test-123",
                plan=None,
                code=None
            )
            
            serialized = checkpointer._serialize_state(state)
            
            assert serialized["plan"] is None
            assert serialized["code"] is None
