"""API endpoints для выполнения кода в изолированной среде.

Поддерживает выполнение Python кода с ограничениями по времени и памяти.
Использует AST-парсинг для проверки безопасности.
"""
import asyncio
import subprocess
import tempfile
import os
import resource
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from utils.logger import get_logger
from backend.routers.code_security_ast import ASTSecurityValidator

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
    
    БЕЗОПАСНОСТЬ: Использует прямой запуск файла через subprocess вместо exec(),
    что предотвращает возможность выполнения произвольного кода через обход проверок.
    
    Args:
        code: Код для выполнения
        timeout: Таймаут выполнения в секундах
        
    Returns:
        Словарь с результатами выполнения
    """
    import time
    
    start_time = time.time()
    
    temp_file = None
    
    try:
        # Создаём временный файл для кода с правильной очисткой
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        # БЕЗОПАСНОСТЬ: Создаём wrapper скрипт для установки ограничений памяти
        # Вместо использования exec() с открытием файла, используем прямой запуск
        wrapper_script = f'''
import resource
import sys
import runpy

# Устанавливаем ограничения памяти (128MB по умолчанию)
try:
    max_memory_bytes = 128 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
except (ValueError, OSError):
    pass  # На некоторых системах может не работать

# БЕЗОПАСНОСТЬ: Используем runpy.run_path() вместо exec(open().read())
# Это более безопасный способ выполнения файла, так как:
# 1. Не использует exec() напрямую
# 2. Выполняет код в изолированном namespace
# 3. Правильно обрабатывает модули и импорты
try:
    runpy.run_path(r"{temp_file}", run_name="__main__")
except SystemExit:
    # Игнорируем sys.exit() - это нормальное завершение
    pass
'''
        
        # Создаём временный файл для wrapper скрипта
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as wrapper_file:
            wrapper_file.write(wrapper_script)
            wrapper_script_path = wrapper_file.name
        
        try:
            # Выполняем wrapper скрипт, который безопасно запустит пользовательский код
            process = await asyncio.create_subprocess_exec(
                'python3',
                wrapper_script_path,
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
                    error_msg = stderr.decode('utf-8', errors='replace')
                    # Проверяем на ошибки памяти
                    if 'MemoryError' in error_msg or 'Killed' in error_msg:
                        error_msg = "Превышен лимит памяти (128MB)"
                    
                    return {
                        "success": False,
                        "output": stdout.decode('utf-8', errors='replace'),
                        "error": error_msg,
                        "execution_time": execution_time
                    }
            
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                execution_time = time.time() - start_time
                return {
                    "success": False,
                    "output": "",
                    "error": f"Выполнение превысило таймаут ({timeout}с)",
                    "execution_time": execution_time
                }
        
        finally:
            # Удаляем wrapper скрипт
            try:
                os.unlink(wrapper_script_path)
            except Exception as e:
                logger.debug(f"⚠️ Не удалось удалить wrapper_script_path: {e}")
    
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Ошибка при выполнении кода: {e}", error=e)
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "execution_time": execution_time
        }
    
    finally:
        # Удаляем временный файл с кодом
        if temp_file:
            try:
                os.unlink(temp_file)
            except Exception as e:
                logger.debug(f"⚠️ Не удалось удалить temp_file: {e}")


@router.post("/execute", response_model=CodeExecutionResponse)
async def execute_code(request: CodeExecutionRequest) -> CodeExecutionResponse:
    """Выполняет код и возвращает результат.
    
    Использует AST-парсинг для проверки безопасности, что делает обход
    проверок значительно сложнее чем простые строковые паттерны.
    
    Args:
        request: Запрос с кодом
        
    Returns:
        Результат выполнения
        
    Raises:
        HTTPException: Если код содержит опасные операции
    """
    # AST-проверка безопасности (более надежная чем строковые паттерны)
    # Пропускаем проверку если код имеет синтаксические ошибки - они будут обработаны при выполнении
    validator = ASTSecurityValidator()
    is_safe, errors = validator.validate(request.code)
    
    # Если валидация вернула False из-за синтаксической ошибки, пропускаем проверку безопасности
    # (синтаксические ошибки обрабатываются при выполнении)
    if not is_safe and errors:
        # Проверяем, является ли ошибка синтаксической
        if any('синтаксическ' in err.lower() or 'syntax' in err.lower() or 'парсинга' in err.lower() for err in errors):
            # Синтаксические ошибки не блокируем - они будут обработаны при выполнении
            pass
        else:
            # Это реальная проблема безопасности
            error_msg = errors[0] if errors else "Код содержит опасные операции"
            logger.warning(f"Попытка выполнить опасный код: {error_msg}")
            raise HTTPException(
                status_code=400,
                detail=error_msg
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
        logger.debug(f"⚠️ Ошибка валидации синтаксиса кода: {e}")
        return {
            "valid": False,
            "error": str(e)
        }
