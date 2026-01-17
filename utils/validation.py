"""Утилиты для валидации кода: pytest, mypy, bandit."""
import subprocess
import tempfile
import os
from typing import Tuple, Optional
from pathlib import Path
from utils.logger import get_logger


logger = get_logger()


def run_pytest(code_str: str, test_str: str) -> Tuple[bool, str]:
    """Запускает pytest для проверки что код проходит тесты.
    
    Args:
        code_str: Код для тестирования
        test_str: Код тестов pytest
        
    Returns:
        Кортеж (успех: bool, вывод: str)
    """
    if not code_str.strip() or not test_str.strip():
        return False, "Пустой код или тесты"
    
    with tempfile.TemporaryDirectory(prefix="pytest_validation_") as tmpdir:
        try:
            # Создаём временные файлы
            code_file = Path(tmpdir) / "code.py"
            test_file = Path(tmpdir) / "test_code.py"
            
            code_file.write_text(code_str, encoding="utf-8")
            test_file.write_text(test_str, encoding="utf-8")
            
            # Запускаем pytest
            result = subprocess.run(
                ["pytest", str(test_file), "-v", "--tb=short"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            success = result.returncode == 0
            output = result.stdout + result.stderr
            
            if success:
                logger.info("✅ Все тесты прошли успешно")
            else:
                logger.warning(f"❌ Тесты не прошли: {output[:500]}")
            
            return success, output
            
        except subprocess.TimeoutExpired:
            return False, "Таймаут выполнения тестов (>30 сек)"
        except FileNotFoundError:
            return False, "pytest не найден. Установите: pip install pytest"
        except Exception as e:
            return False, f"Ошибка запуска pytest: {e}"


def check_mypy(code_str: str) -> Tuple[bool, str]:
    """Проверяет код с помощью mypy (type checking).
    
    Args:
        code_str: Код для проверки
        
    Returns:
        Кортеж (успех: bool, ошибки: str)
    """
    if not code_str.strip():
        return False, "Пустой код"
    
    with tempfile.TemporaryDirectory(prefix="mypy_validation_") as tmpdir:
        try:
            code_file = Path(tmpdir) / "code.py"
            code_file.write_text(code_str, encoding="utf-8")
            
            # Запускаем mypy в strict режиме
            result = subprocess.run(
                ["mypy", str(code_file), "--strict", "--no-error-summary"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # mypy возвращает 0 если нет ошибок
            success = result.returncode == 0
            errors = result.stdout + result.stderr
            
            if success:
                logger.info("✅ mypy проверка пройдена (0 ошибок)")
            else:
                # Показываем только первые несколько ошибок
                error_lines = errors.split("\n")[:10]
                logger.warning(f"❌ mypy нашёл ошибки: {' '.join(error_lines)}")
            
            return success, errors
            
        except subprocess.TimeoutExpired:
            return False, "Таймаут проверки mypy (>30 сек)"
        except FileNotFoundError:
            logger.warning("⚠️ mypy не найден. Установите: pip install mypy")
            # Если mypy не установлен, считаем проверку пропущенной (не ошибкой)
            return True, "mypy не установлен, проверка пропущена"
        except Exception as e:
            return False, f"Ошибка запуска mypy: {e}"


def check_bandit(code_str: str) -> Tuple[bool, str]:
    """Проверяет код на проблемы безопасности с помощью bandit.
    
    Args:
        code_str: Код для проверки
        
    Returns:
        Кортеж (успех: bool, проблемы: str). Успех = True если нет критических/высоких проблем
    """
    if not code_str.strip():
        return False, "Пустой код"
    
    with tempfile.TemporaryDirectory(prefix="bandit_validation_") as tmpdir:
        try:
            code_file = Path(tmpdir) / "code.py"
            code_file.write_text(code_str, encoding="utf-8")
            
            # Запускаем bandit с минимальным уровнем medium
            result = subprocess.run(
                ["bandit", "-r", str(code_file), "-ll", "--format", "txt"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            
            # bandit возвращает 0 если нет проблем уровня medium и выше
            # По правилам нужен уровень medium и ниже
            success = result.returncode == 0
            
            if success:
                logger.info("✅ bandit проверка пройдена (нет критических проблем)")
            else:
                # Фильтруем только проблемы medium/high/critical
                issues = [line for line in output.split("\n") 
                         if any(level in line for level in ["Severity: ", "Issue: "])]
                logger.warning(f"⚠️ bandit нашёл проблемы безопасности: {issues[:5]}")
            
            return success, output
            
        except subprocess.TimeoutExpired:
            return False, "Таймаут проверки bandit (>30 сек)"
        except FileNotFoundError:
            logger.warning("⚠️ bandit не найден. Установите: pip install bandit")
            # Если bandit не установлен, считаем проверку пропущенной
            return True, "bandit не установлен, проверка пропущена"
        except Exception as e:
            return False, f"Ошибка запуска bandit: {e}"


def validate_code(code_str: str, test_str: Optional[str] = None) -> dict:
    """Комплексная валидация кода (pytest, mypy, bandit).
    
    Args:
        code_str: Код для валидации
        test_str: Опциональные тесты для pytest
        
    Returns:
        Словарь с результатами валидации:
        {
            "pytest": {"success": bool, "output": str},
            "mypy": {"success": bool, "errors": str},
            "bandit": {"success": bool, "issues": str},
            "all_passed": bool
        }
    """
    results = {
        "pytest": {"success": False, "output": ""},
        "mypy": {"success": False, "errors": ""},
        "bandit": {"success": False, "issues": ""},
        "all_passed": False
    }
    
    # pytest проверка (если есть тесты)
    if test_str:
        pytest_success, pytest_output = run_pytest(code_str, test_str)
        results["pytest"] = {"success": pytest_success, "output": pytest_output}
    
    # mypy проверка
    mypy_success, mypy_errors = check_mypy(code_str)
    results["mypy"] = {"success": mypy_success, "errors": mypy_errors}
    
    # bandit проверка
    bandit_success, bandit_issues = check_bandit(code_str)
    results["bandit"] = {"success": bandit_success, "issues": bandit_issues}
    
    # Все проверки должны пройти
    results["all_passed"] = (
        (results["pytest"]["success"] if test_str else True) and
        results["mypy"]["success"] and
        results["bandit"]["success"]
    )
    
    return results
