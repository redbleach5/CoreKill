"""Тесты для роутера базы данных."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

# Мокаем setup_log_filter до импорта
with patch('backend.middleware.log_filter.setup_log_filter'):
    from backend.api import app


@pytest.fixture
def client():
    """Создает тестовый клиент FastAPI."""
    with patch('backend.api.initialize_ollama_pool', new_callable=AsyncMock), \
         patch('backend.api.get_performance_metrics'), \
         patch('backend.api.EventStore'), \
         patch('backend.api.get_shutdown_manager'), \
         patch('backend.api.setup_log_filter'):
        yield TestClient(app)


class TestBackupDatabase:
    """Тесты для backup endpoints."""
    
    @patch('backend.routers.database.DatabaseManager')
    @pytest.mark.backend

    def test_backup_database_success(self, mock_db_manager, client):
        """Тест успешного создания бэкапа."""
        from pathlib import Path
        
        mock_manager_instance = Mock()
        mock_manager_instance.backup_database = Mock(return_value=Path("/path/to/backup.db"))
        mock_db_manager.return_value = mock_manager_instance
        
        response = client.post(
            "/api/databases/backup",
            json={
                "database": "test_db",
                "name": "backup_2026"
            },
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "success"
        assert "backup_path" in data
    
    @patch('backend.routers.database.DatabaseManager')
    @pytest.mark.backend

    def test_backup_all_databases(self, mock_db_manager, client):
        """Тест создания бэкапа всех баз данных."""
        from pathlib import Path
        from dataclasses import dataclass
        
        @dataclass
        class MockDB:
            name: str
        
        mock_manager_instance = Mock()
        mock_manager_instance.discover_databases = Mock(return_value=[
            MockDB(name="db1"),
            MockDB(name="db2")
        ])
        mock_manager_instance.backup_database = Mock(side_effect=[
            Path("/path/to/backup1.db"),
            Path("/path/to/backup2.db")
        ])
        mock_db_manager.return_value = mock_manager_instance
        
        response = client.post(
            "/api/databases/backup",
            json={},  # Без указания database - бэкап всех
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "backups" in data


class TestRestoreDatabase:
    """Тесты для restore endpoints."""
    
    @patch('backend.routers.database.DatabaseManager')
    @patch('backend.routers.database.Path')
    @pytest.mark.backend

    def test_restore_database_success(self, mock_path, mock_db_manager, client):
        """Тест успешного восстановления базы данных."""
        from pathlib import Path
        
        # Мокаем Path.exists()
        mock_backup_path = Mock(spec=Path)
        mock_backup_path.exists.return_value = True
        mock_path.return_value = mock_backup_path
        
        mock_manager_instance = Mock()
        mock_manager_instance.restore_database = Mock()
        mock_db_manager.return_value = mock_manager_instance
        
        response = client.post(
            "/api/databases/restore",
            json={
                "backup_path": "/path/to/backup.db",
                "target_database": "test_db"
            },
            headers={"Host": "localhost:8000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "success"
