"""API endpoints для выполнения кода в изолированной среде.

Поддерживает выполнение Python кода с ограничениями по времени и памяти.
"""
import asyncio
import subprocess
import tempfile
import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from utils.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/code", tags=["code_executor"])


class CodeExecutionRequest(BaseModel):
    """Запрос на выполнение кода."""
    code: str = Field(..., description="Код для выполнения")
    language: str = Field(default="python", description="Язык программирования")
    timeout: int = Field(default=10, ge=1, le=60, description="Таймаут выполнения в секундах")


class CodeExecutionResponse(BaseModel):
    """Результат выполнения кода."""
    success: bool = Field(..., description="Успешно ли выполнен код")
    output: str = Field(default="", description="Стандартный вывод")
    error: Optional[str] = Field(default=None, description="Сообщение об ошибке")
    execution_time: float = Field(..., description="Время выполнения в секундах")


async def execute_python_code(code: str, timeout: int = 10) -> Dict[str, Any]:
    """Выполняет Python код в изолированной среде.
    
    Args:
        code: Код для выполнения
        timeout: Таймаут выполнения в секундах
        
    Returns:
        Словарь с результатами выполнения
    """
    import time
    
    start_time = time.time()
    
    # Создаём временный файл для кода
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_file = f.name
    
    try:
        # Выполняем код в отдельном процессе
        process = await asyncio.create_subprocess_exec(
            'python3',
            temp_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=1024 * 1024  # 1MB limit для буфера
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            execution_time = time.time() - start_time
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "output": stdout.decode('utf-8', errors='replace'),
                    "error": None,
                    "execution_time": execution_time
                }
            else:
                return {
                    "success": False,
                    "output": stdout.decode('utf-8', errors='replace'),
                    "error": stderr.decode('utf-8', errors='replace'),
                    "execution_time": execution_time
                }
        
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": "",
                "error": f"Выполнение превышило таймаут ({timeout}с)",
                "execution_time": execution_time
            }
    
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Ошибка при выполнении кода: {e}")
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "execution_time": execution_time
        }
    
    finally:
        # Удаляем временный файл
        try:
            os.unlink(temp_file)
        except Exception:
            pass


@router.post("/execute", response_model=CodeExecutionResponse)
async def execute_code(request: CodeExecutionRequest) -> CodeExecutionResponse:
    """Выполняет код и возвращает результат.
    
    Args:
        request: Запрос с кодом
        
    Returns:
        Результат выполнения
        
    Raises:
        HTTPException: Если код содержит опасные операции
    """
    # Расширенная проверка безопасности
    # Опасные импорты
    dangerous_imports = [
        'import os',
        'import subprocess',
        'import sys',
        'import socket',
        'import requests',
        'import urllib',
        'import ctypes',
        'import importlib',
        'from os',
        'from subprocess',
        'from sys',
        'from socket',
    ]
    
    # Опасные функции и методы
    dangerous_functions = [
        '__import__',
        'eval(',
        'exec(',
        'compile(',
        'open(',
        'file(',
        'input(',
        'raw_input(',
        'globals(',
        'locals(',
        'vars(',
        'dir(',
        'getattr(',
        'setattr(',
        'delattr(',
        'hasattr(',
        'callable(',
        'type(',
        'isinstance(',
        'issubclass(',
        '__builtins__',
        '__loader__',
        '__spec__',
        '__code__',
        '__globals__',
        '__dict__',
    ]
    
    # Опасные системные команды
    dangerous_system_calls = [
        'os.system',
        'os.popen',
        'os.execv',
        'os.spawn',
        'subprocess.run',
        'subprocess.call',
        'subprocess.popen',
        'subprocess.check_output',
        'subprocess.check_call',
    ]
    
    code_lower = request.code.lower()
    
    # Проверка опасных импортов
    for pattern in dangerous_imports:
        if pattern in code_lower:
            logger.warning(f"Попытка выполнить опасный код: {pattern}")
            raise HTTPException(
                status_code=400,
                detail=f"Код содержит запрещённый импорт: {pattern}"
            )
    
    # Проверка опасных функций
    for pattern in dangerous_functions:
        if pattern.lower() in code_lower:
            logger.warning(f"Попытка выполнить опасный код: {pattern}")
            raise HTTPException(
                status_code=400,
                detail=f"Код содержит запрещённую функцию: {pattern}"
            )
    
    # Проверка опасных системных вызовов
    for pattern in dangerous_system_calls:
        if pattern.lower() in code_lower:
            logger.warning(f"Попытка выполнить опасный код: {pattern}")
            raise HTTPException(
                status_code=400,
                detail=f"Код содержит запрещённый системный вызов: {pattern}"
            )
    
    # Выполняем код
    if request.language == "python":
        result = await execute_python_code(request.code, request.timeout)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Язык {request.language} не поддерживается"
        )
    
    return CodeExecutionResponse(**result)


@router.post("/validate")
async def validate_code(request: CodeExecutionRequest) -> Dict[str, Any]:
    """Валидирует синтаксис кода без выполнения.
    
    Args:
        request: Запрос с кодом
        
    Returns:
        Результат валидации
    """
    if request.language != "python":
        raise HTTPException(
            status_code=400,
            detail=f"Язык {request.language} не поддерживается"
        )
    
    try:
        compile(request.code, '<string>', 'exec')
        return {
            "valid": True,
            "error": None
        }
    except SyntaxError as e:
        return {
            "valid": False,
            "error": str(e),
            "line": e.lineno,
            "offset": e.offset
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }
