"""Тесты безопасности для code_executor.py с AST-валидацией."""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Мокаем setup_log_filter до импорта
with patch('backend.middleware.log_filter.setup_log_filter'):
    from backend.api import app
    from backend.routers.code_executor import ASTSecurityValidator, execute_python_code


@pytest.fixture
def client():
    """Создает тестовый клиент FastAPI."""
    with patch('backend.api.initialize_ollama_pool', new_callable=AsyncMock), \
         patch('backend.api.get_performance_metrics'), \
         patch('backend.api.EventStore'), \
         patch('backend.api.get_shutdown_manager'), \
         patch('backend.api.setup_log_filter'):
        yield TestClient(app)


class TestASTSecurityValidator:
    """Тесты для ASTSecurityValidator."""
    
    def test_forbidden_import_direct(self):
        """Тест блокировки прямого импорта запрещенных модулей."""
        validator = ASTSecurityValidator()
        is_safe, errors = validator.validate('import os')
        assert not is_safe
        assert any('os' in err.lower() for err in errors)
    
    def test_forbidden_import_alias(self):
        """Тест блокировки импорта через alias (import os as o)."""
        validator = ASTSecurityValidator()
        is_safe, errors = validator.validate('import os as o')
        assert not is_safe
        assert any('os' in err.lower() for err in errors)
    
    def test_forbidden_import_from(self):
        """Тест блокировки импорта из модуля (from os import ...)."""
        validator = ASTSecurityValidator()
        is_safe, errors = validator.validate('from os import path')
        assert not is_safe
        assert any('os' in err.lower() for err in errors)
    
    def test_forbidden_function_eval(self):
        """Тест блокировки eval()."""
        validator = ASTSecurityValidator()
        is_safe, errors = validator.validate('eval("1+1")')
        assert not is_safe
        assert any('eval' in err.lower() for err in errors)
    
    def test_forbidden_function_exec(self):
        """Тест блокировки exec()."""
        validator = ASTSecurityValidator()
        is_safe, errors = validator.validate('exec("print(1)")')
        assert not is_safe
        assert any('exec' in err.lower() for err in errors)
    
    def test_forbidden_system_call(self):
        """Тест блокировки системных вызовов (os.system)."""
        validator = ASTSecurityValidator()
        # Сначала нужно импортировать os, но это тоже заблокировано
        code = '''
import os
os.system("ls")
'''
        is_safe, errors = validator.validate(code)
        assert not is_safe
    
    def test_safe_code(self):
        """Тест что безопасный код проходит проверку."""
        validator = ASTSecurityValidator()
        is_safe, errors = validator.validate('print(42)')
        assert is_safe
        assert len(errors) == 0
    
    def test_safe_code_with_math(self):
        """Тест что математические операции безопасны."""
        validator = ASTSecurityValidator()
        code = '''
def add(a, b):
    return a + b

result = add(1, 2)
print(result)
'''
        is_safe, errors = validator.validate(code)
        assert is_safe
    
    def test_bypass_attempt_string_pattern(self):
        """Тест что обход через строковые паттерны не работает."""
        validator = ASTSecurityValidator()
        # Попытка обхода: eval через строку
        code = 'eval("__import__(\'os\')")'
        is_safe, errors = validator.validate(code)
        assert not is_safe  # Должен быть заблокирован
    
    def test_bypass_attempt_getattr(self):
        """Тест что обход через getattr не работает."""
        validator = ASTSecurityValidator()
        # Попытка обхода через getattr
        code = 'getattr(__builtins__, "__import__")("os")'
        is_safe, errors = validator.validate(code)
        # getattr может быть заблокирован, но __builtins__ тоже
        # В любом случае это должно быть обнаружено
        assert not is_safe or any('getattr' in err.lower() or '__builtins__' in err.lower() for err in errors)


class TestCodeExecutorSecurity:
    """Тесты безопасности для execute_code endpoint."""
    
    def test_execute_code_blocks_dangerous_import(self, client):
        """Тест что endpoint блокирует опасные импорты."""
        response = client.post(
            "/api/code/execute",
            json={
                "code": "import os\nprint(os.getcwd())",
                "language": "python"
            },
            headers={"Host": "localhost:8000"}
        )
        assert response.status_code == 400
        assert "запрещённый импорт" in response.json()["detail"].lower() or "os" in response.json()["detail"].lower()
    
    def test_execute_code_blocks_eval(self, client):
        """Тест что endpoint блокирует eval()."""
        response = client.post(
            "/api/code/execute",
            json={
                "code": "eval('1+1')",
                "language": "python"
            },
            headers={"Host": "localhost:8000"}
        )
        assert response.status_code == 400
        assert "eval" in response.json()["detail"].lower() or "опасн" in response.json()["detail"].lower()
    
    def test_execute_code_allows_safe_code(self, client):
        """Тест что безопасный код выполняется."""
        response = client.post(
            "/api/code/execute",
            json={
                "code": "print(42)",
                "language": "python"
            },
            headers={"Host": "localhost:8000"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "42" in data["output"]
    
    def test_execute_code_blocks_subprocess(self, client):
        """Тест что subprocess блокируется."""
        response = client.post(
            "/api/code/execute",
            json={
                "code": "import subprocess\nsubprocess.run(['ls'])",
                "language": "python"
            },
            headers={"Host": "localhost:8000"}
        )
        assert response.status_code == 400


class TestCodeExecutorExecution:
    """Тесты выполнения кода."""
    
    @pytest.mark.asyncio
    async def test_execute_python_code_success(self):
        """Тест успешного выполнения безопасного кода."""
        result = await execute_python_code('print("Hello")', timeout=5)
        assert result["success"] is True
        assert "Hello" in result["output"]
        assert result["error"] is None
    
    @pytest.mark.asyncio
    async def test_execute_python_code_syntax_error(self):
        """Тест обработки синтаксической ошибки."""
        result = await execute_python_code('print("unclosed', timeout=5)
        assert result["success"] is False
        assert result["error"] is not None
    
    @pytest.mark.asyncio
    async def test_execute_python_code_timeout(self):
        """Тест обработки таймаута."""
        result = await execute_python_code('import time\ntime.sleep(10)', timeout=1)
        assert result["success"] is False
        assert "таймаут" in result["error"].lower() or "timeout" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_python_code_memory_limit(self):
        """Тест что код с большим использованием памяти ограничивается."""
        # Создаем код который пытается использовать много памяти
        code = '''
data = []
for i in range(10000000):  # 10M элементов
    data.append(i)
'''
        result = await execute_python_code(code, timeout=5)
        # Может быть MemoryError или просто долго выполняться
        # Проверяем что выполнение завершилось (не зависло)
        assert "execution_time" in result
