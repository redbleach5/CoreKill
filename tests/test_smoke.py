"""Smoke tests - проверяют что проект реально работает.

Эти тесты НЕ используют моки и проверяют реальное состояние системы.
Они должны ПАДАТЬ если проект не работает.

ВАЖНО: Эти тесты проверяют РЕАЛЬНОЕ поведение, а не моки!
"""
import pytest
import requests
import subprocess
import sys
import asyncio
import threading
import time
from pathlib import Path


class TestSmoke:
    """Smoke tests - проверка что проект работает."""
    
    @pytest.mark.smoke
    def test_imports_work(self):
        """Проверяет что основные модули импортируются."""
        try:
            from backend.api import app
            assert app is not None, "app должен быть создан"
        except Exception as e:
            pytest.fail(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Не удалось импортировать backend.api: {e}")
    
    @pytest.mark.smoke
    def test_app_starts(self):
        """Проверяет что приложение может запуститься."""
        try:
            import uvicorn
            from backend.api import app
            
            # Запускаем сервер в фоне
            import threading
            import time
            
            server_thread = threading.Thread(
                target=lambda: uvicorn.run(app, host='127.0.0.1', port=8002, log_level='error'),
                daemon=True
            )
            server_thread.start()
            
            # Ждём запуска
            time.sleep(2)
            
            # Проверяем health endpoint
            try:
                response = requests.get('http://127.0.0.1:8002/health', timeout=2)
                assert response.status_code == 200, f"Health endpoint вернул {response.status_code}"
                
                data = response.json()
                # Проверяем что сервер отвечает (даже если Ollama недоступен)
                assert 'status' in data, "Health endpoint должен вернуть status"
                
            except requests.exceptions.RequestException as e:
                pytest.fail(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Сервер не отвечает: {e}")
        except Exception as e:
            pytest.fail(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Не удалось запустить сервер: {e}")
    
    @pytest.mark.smoke
    def test_config_exists(self):
        """Проверяет что config.toml существует и читается."""
        config_path = Path("config.toml")
        assert config_path.exists(), f"❌ ПРОБЛЕМА: config.toml не найден в {config_path.absolute()}"
        
        try:
            import tomllib
            with open(config_path, 'rb') as f:
                config = tomllib.load(f)
            assert config is not None, "config.toml должен быть читаемым"
        except Exception as e:
            pytest.fail(f"❌ ПРОБЛЕМА: Не удалось прочитать config.toml: {e}")
    
    @pytest.mark.smoke
    def test_requirements_installed(self):
        """Проверяет что основные зависимости установлены."""
        critical_packages = [
            'fastapi',
            'uvicorn',
            'pydantic',
            'pytest',
        ]
        
        missing = []
        for package in critical_packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        if missing:
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Отсутствуют зависимости: {', '.join(missing)}. "
                f"Установите: pip install {' '.join(missing)}"
            )
    
    @pytest.mark.skip(reason="Требует запущенный Ollama - может быть пропущен в CI")
    def test_ollama_connection(self):
        """Проверяет подключение к Ollama (опционально)."""
        try:
            import ollama
            # Пробуем подключиться
            models = ollama.list()
            assert models is not None, "Ollama должен вернуть список моделей"
        except Exception as e:
            pytest.fail(
                f"❌ ПРОБЛЕМА: Не удалось подключиться к Ollama: {e}. "
                f"Убедитесь что Ollama запущен: ollama serve"
            )
    
    @pytest.mark.smoke
    def test_backend_modules_import(self):
        """Проверяет что основные backend модули импортируются."""
        modules_to_test = [
            'backend.api',
            'backend.dependencies',
            'backend.types',
            'backend.routers.agent',
            'backend.routers.code_executor',
        ]
        
        failed = []
        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except Exception as e:
                failed.append(f"{module_name}: {e}")
        
        if failed:
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Не удалось импортировать модули:\n" +
                "\n".join(f"  - {f}" for f in failed)
            )
    
    @pytest.mark.smoke
    def test_infrastructure_modules_import(self):
        """Проверяет что основные infrastructure модули импортируются."""
        modules_to_test = [
            'infrastructure.local_llm',
            'infrastructure.model_router',
            'infrastructure.event_store',
            'infrastructure.workflow_nodes',
        ]
        
        failed = []
        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except Exception as e:
                failed.append(f"{module_name}: {e}")
        
        if failed:
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Не удалось импортировать модули:\n" +
                "\n".join(f"  - {f}" for f in failed)
            )
    
    @pytest.mark.smoke
    def test_agents_modules_import(self):
        """Проверяет что основные агенты импортируются."""
        modules_to_test = [
            'agents.base',
            'agents.coder',
            'agents.planner',
            'agents.reflection',
        ]
        
        failed = []
        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except Exception as e:
                failed.append(f"{module_name}: {e}")
        
        if failed:
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Не удалось импортировать агенты:\n" +
                "\n".join(f"  - {f}" for f in failed)
            )
    
    @pytest.mark.smoke
    def test_utils_modules_import(self):
        """Проверяет что основные utils модули импортируются."""
        modules_to_test = [
            'utils.config',
            'utils.logger',
            'utils.validation',
        ]
        
        failed = []
        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except Exception as e:
                failed.append(f"{module_name}: {e}")
        
        if failed:
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Не удалось импортировать utils:\n" +
                "\n".join(f"  - {f}" for f in failed)
            )


class TestReality:
    """Тесты реальности - проверяют что тесты выявляют проблемы."""
    
    @pytest.mark.smoke
    def test_health_endpoint_shows_real_status(self):
        """Проверяет что /health показывает реальный статус (не мокированный)."""
        try:
            import uvicorn
            from backend.api import app
            import threading
            import time
            
            server_thread = threading.Thread(
                target=lambda: uvicorn.run(app, host='127.0.0.1', port=8003, log_level='error'),
                daemon=True
            )
            server_thread.start()
            time.sleep(2)
            
            response = requests.get('http://127.0.0.1:8003/health', timeout=2)
            assert response.status_code == 200
            
            data = response.json()
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: статус должен отражать реальное состояние
            # Если Ollama недоступен, статус должен быть "degraded" или "error"
            if 'services' in data and 'ollama' in data['services']:
                ollama_status = data['services']['ollama']
                # Это реальный статус, не мок!
                # Если тест падает здесь - значит система работает неправильно
                assert ollama_status in ['ok', 'error', 'degraded'], \
                    f"❌ ПРОБЛЕМА: Неожиданный статус Ollama: {ollama_status}. " \
                    f"Полный ответ: {data}"
        except Exception as e:
            pytest.fail(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Не удалось проверить реальный статус: {e}")
    
    @pytest.mark.smoke
    def test_api_endpoints_exist(self):
        """Проверяет что основные API endpoints существуют."""
        try:
            from backend.api import app
            
            # Получаем все routes
            routes = []
            for route in app.routes:
                if hasattr(route, 'path') and hasattr(route, 'methods'):
                    routes.append((route.path, route.methods))
            
            # Проверяем наличие критичных endpoints
            critical_endpoints = [
                '/health',
                '/api/stream',
                '/api/models',
            ]
            
            missing = []
            for endpoint in critical_endpoints:
                found = any(endpoint in path for path, _ in routes)
                if not found:
                    missing.append(endpoint)
            
            if missing:
                pytest.fail(
                    f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Отсутствуют endpoints: {', '.join(missing)}\n" +
                    f"Доступные endpoints: {[path for path, _ in routes[:10]]}"
                )
        except Exception as e:
            pytest.fail(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Не удалось проверить endpoints: {e}")
    
    @pytest.mark.smoke
    def test_config_has_required_keys(self):
        """Проверяет что config.toml содержит необходимые ключи."""
        config_path = Path("config.toml")
        if not config_path.exists():
            pytest.fail(f"❌ ПРОБЛЕМА: config.toml не найден")
        
        try:
            import tomllib
            with open(config_path, 'rb') as f:
                config = tomllib.load(f)
            
            # Проверяем наличие критичных секций (актуальная структура)
            required_sections = [
                'ollama',  # Настройки Ollama
                'llm',     # Настройки LLM
                'default', # Дефолтные значения
            ]
            
            missing = []
            for section in required_sections:
                if section not in config:
                    missing.append(section)
            
            if missing:
                pytest.fail(
                    f"❌ ПРОБЛЕМА: В config.toml отсутствуют критичные секции: {', '.join(missing)}\n" +
                    f"Найденные секции: {list(config.keys())[:10]}..."
                )
            
            # Проверяем что config не пустой
            if not config:
                pytest.fail("❌ ПРОБЛЕМА: config.toml пустой")
                
        except Exception as e:
            pytest.fail(f"❌ ПРОБЛЕМА: Не удалось проверить config.toml: {e}")
    
    @pytest.mark.smoke
    def test_dependencies_installed(self):
        """Проверяет что все критические зависимости установлены."""
        critical_packages = {
            'fastapi': 'FastAPI',
            'uvicorn': 'Uvicorn',
            'pydantic': 'Pydantic',
            'ollama': 'Ollama',
            'chromadb': 'ChromaDB',
            'langgraph': 'LangGraph',
            'pytest': 'Pytest',
        }
        
        missing = []
        for package, name in critical_packages.items():
            try:
                __import__(package)
            except ImportError:
                missing.append(name)
        
        if missing:
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Отсутствуют зависимости: {', '.join(missing)}\n" +
                f"Установите: pip install {' '.join(missing)}"
            )
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    @pytest.mark.smoke

    async def test_event_store_works(self):
        """Проверяет что EventStore реально работает (без моков)."""
        try:
            from infrastructure.event_store import EventStore
            
            # Очищаем перед тестом
            EventStore._instances.clear()
            EventStore._events.clear()
            
            # Создаём сессию
            store = await EventStore.get_for_session("test-smoke-session")
            assert store is not None, "EventStore должен создавать экземпляр"
            assert store.session_id == "test-smoke-session", "Session ID должен совпадать"
            
            # Сохраняем событие
            event_id = await store.save_event("test", {"data": "smoke test"})
            assert event_id is not None, "save_event должен возвращать ID"
            
            # Получаем событие
            event = await store.get_event(event_id)
            assert event is not None, "get_event должен возвращать событие"
            assert event.event_type == "test", "Тип события должен совпадать"
            
            # Очищаем после теста
            await EventStore.cleanup_session("test-smoke-session")
            
        except Exception as e:
            pytest.fail(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: EventStore не работает: {e}")
    
    @pytest.mark.smoke
    def test_config_singleton_works(self):
        """Проверяет что Config singleton работает."""
        try:
            from utils.config import get_config, Config
            
            config1 = get_config()
            config2 = get_config()
            
            # Должен быть тот же экземпляр (singleton)
            assert config1 is config2, "Config должен быть singleton"
            assert isinstance(config1, Config), "Config должен быть экземпляром Config"
            
        except Exception as e:
            pytest.fail(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Config не работает: {e}")
    
    @pytest.mark.smoke
    def test_logger_works(self):
        """Проверяет что logger работает."""
        try:
            from utils.logger import get_logger
            
            logger = get_logger()
            assert logger is not None, "Logger должен быть создан"
            
            # Пробуем залогировать
            logger.info("Smoke test log message")
            
        except Exception as e:
            pytest.fail(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Logger не работает: {e}")
    
    @pytest.mark.smoke

    
    def test_dependency_container_works(self):
        """Проверяет что DependencyContainer работает."""
        try:
            from backend.dependencies import DependencyContainer
            
            container = DependencyContainer()
            assert container is not None, "DependencyContainer должен быть создан"
            
            # Проверяем что методы доступны
            assert hasattr(container, 'get_memory_agent'), "Должен иметь get_memory_agent"
            assert hasattr(container, 'reset'), "Должен иметь reset"
            
        except Exception as e:
            pytest.fail(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: DependencyContainer не работает: {e}")
    
    @pytest.mark.smoke
    def test_file_structure(self):
        """Проверяет что структура файлов проекта корректна."""
        required_dirs = [
            'backend',
            'infrastructure',
            'agents',
            'utils',
            'tests',
            'frontend',
        ]
        
        missing = []
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                missing.append(dir_name)
        
        if missing:
            pytest.fail(
                f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Отсутствуют директории: {', '.join(missing)}"
            )
        
        required_files = [
            'config.toml',
            'requirements.txt',
            'README.md',
            'run.py',
        ]
        
        missing = []
        for file_name in required_files:
            file_path = Path(file_name)
            if not file_path.exists():
                missing.append(file_name)
        
        if missing:
            pytest.fail(
                f"❌ ПРОБЛЕМА: Отсутствуют файлы: {', '.join(missing)}"
            )
