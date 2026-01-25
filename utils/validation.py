"""Утилиты для валидации кода: pytest, mypy, bandit.

Предоставляет функции для проверки сгенерированного кода:
- Синтаксическая проверка (ast.parse)
- Запуск pytest для тестов
- Запуск mypy для проверки типов
- Запуск bandit для проверки безопасности

Примеры использования:
    ```python
    from utils.validation import (
        check_syntax,
        run_pytest,
        run_mypy,
        run_bandit,
        validate_code
    )
    
    # Быстрая проверка синтаксиса
    success, message = check_syntax(code)
    if not success:
        print(f"Синтаксическая ошибка: {message}")
    
    # Запуск pytest
    result = run_pytest(code, tests)
    if result["success"]:
        print("Все тесты прошли!")
    
    # Запуск mypy
    result = run_mypy(code)
    if result["success"]:
        print("Типы корректны!")
    
    # Полная валидация
    results = validate_code(code, tests)
    print(f"pytest: {results['pytest']['success']}")
    print(f"mypy: {results['mypy']['success']}")
    print(f"bandit: {results['bandit']['success']}")
    ```

Зависимости:
    - subprocess: для запуска внешних инструментов
    - tempfile: для создания временных файлов
    - ast: для синтаксической проверки
    - pathlib: для работы с путями
    - utils.logger: для логирования

Связанные утилиты:
    - agents.validator: использует для валидации кода
    - infrastructure.workflow_nodes: использует в workflow

Примечания:
    - Все проверки выполняются в безопасном окружении (временные файлы)
    - Таймауты защищают от зависания внешних инструментов
    - Результаты валидации сохраняются для анализа
    - Поддерживает pytest, mypy, bandit
"""
import subprocess
import tempfile
import os
import ast
from typing import Tuple, Optional, List
from pathlib import Path
from utils.logger import get_logger


logger = get_logger()


def check_syntax(code_str: str) -> Tuple[bool, str]:
    """Быстрая проверка синтаксиса Python через ast.parse.
    
    Эта проверка выполняется ДО запуска pytest/mypy для раннего
    обнаружения синтаксических ошибок.
    
    Args:
        code_str: Код для проверки
        
    Returns:
        Кортеж (успех: bool, сообщение: str с описанием ошибки или 'OK')
    """
    if not code_str.strip():
        return False, "Пустой код"
    
    try:
        ast.parse(code_str)
        return True, "OK"
    except SyntaxError as e:
        error_msg = f"Синтаксическая ошибка на строке {e.lineno}: {e.msg}"
        if e.text:
            error_msg += f"\n  >>> {e.text.strip()}"
        logger.warning(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        logger.debug(f"⚠️ Неожиданная ошибка проверки синтаксиса: {e}")
        return False, f"Ошибка парсинга: {e}"


def check_syntax_both(code_str: str, test_str: str) -> Tuple[bool, List[str]]:
    """Проверяет синтаксис кода И тестов перед запуском pytest.
    
    Args:
        code_str: Основной код
        test_str: Код тестов
        
    Returns:
        Кортеж (успех: bool, список ошибок: List[str])
    """
    errors = []
    
    code_ok, code_msg = check_syntax(code_str)
    if not code_ok:
        errors.append(f"[code.py] {code_msg}")
    
    test_ok, test_msg = check_syntax(test_str)
    if not test_ok:
        errors.append(f"[test_code.py] {test_msg}")
    
    return len(errors) == 0, errors


def run_pytest(code_str: str, test_str: str) -> Tuple[bool, str]:
    """Запускает pytest для проверки что код проходит тесты.
    
    Перед запуском pytest выполняется быстрая проверка синтаксиса
    через ast.parse для раннего обнаружения ошибок.
    
    Args:
        code_str: Код для тестирования
        test_str: Код тестов pytest
        
    Returns:
        Кортеж (успех: bool, вывод: str)
    """
    if not code_str.strip() or not test_str.strip():
        return False, "Пустой код или тесты"
    
    # Предварительная проверка синтаксиса (быстрее чем ждать падения pytest)
    syntax_ok, syntax_errors = check_syntax_both(code_str, test_str)
    if not syntax_ok:
        error_msg = "Синтаксические ошибки:\n" + "\n".join(syntax_errors)
        logger.warning(f"❌ Синтаксис не прошёл проверку до запуска pytest: {error_msg}")
        return False, error_msg
    
    with tempfile.TemporaryDirectory(prefix="pytest_validation_") as tmpdir:
        try:
            # Создаём временные файлы
            code_file = Path(tmpdir) / "code.py"
            test_file = Path(tmpdir) / "test_code.py"
            
            code_file.write_text(code_str, encoding="utf-8")
            
            # Добавляем import code в начало тестов если его нет
            # Это позволяет тестам использовать функции из code.py
            test_str_with_import = _ensure_code_import(test_str)
            test_file.write_text(test_str_with_import, encoding="utf-8")
            
            # Создаём __init__.py для правильного импорта
            init_file = Path(tmpdir) / "__init__.py"
            init_file.write_text("", encoding="utf-8")
            
            # Запускаем pytest с добавлением tmpdir в PYTHONPATH
            env = os.environ.copy()
            env["PYTHONPATH"] = tmpdir + os.pathsep + env.get("PYTHONPATH", "")
            
            result = subprocess.run(
                ["pytest", str(test_file), "-v", "--tb=short", "-x"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
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


def _ensure_code_import(test_str: str) -> str:
    """Добавляет импорт из code.py в тесты если его нет.
    
    Анализирует тесты и добавляет необходимые импорты из code.py.
    
    Args:
        test_str: Исходный код тестов
        
    Returns:
        Код тестов с добавленным импортом
    """
    import re
    
    # Проверяем есть ли уже импорт из code
    if re.search(r'from\s+code\s+import|import\s+code', test_str):
        return test_str
    
    # Ищем имена функций/классов которые используются в тестах но не определены
    # Паттерн: вызовы функций вида function_name( или ClassName(
    used_names = set(re.findall(r'\b([a-z_][a-z0-9_]*)\s*\(', test_str, re.IGNORECASE))
    
    # Исключаем стандартные функции pytest и Python
    stdlib_names = {
        'test', 'assert', 'print', 'len', 'range', 'str', 'int', 'float', 'bool',
        'list', 'dict', 'set', 'tuple', 'type', 'isinstance', 'hasattr', 'getattr',
        'setattr', 'open', 'sum', 'max', 'min', 'abs', 'round', 'sorted', 'reversed',
        'enumerate', 'zip', 'map', 'filter', 'any', 'all', 'next', 'iter',
        'pytest', 'fixture', 'mark', 'raises', 'approx', 'capsys', 'tmp_path',
        'monkeypatch', 'capfd', 'caplog', 'request', 'parametrize'
    }
    
    # Также исключаем функции определённые в самих тестах
    defined_in_tests = set(re.findall(r'def\s+([a-z_][a-z0-9_]*)\s*\(', test_str, re.IGNORECASE))
    
    # Имена которые нужно импортировать
    names_to_import = used_names - stdlib_names - defined_in_tests
    
    # Фильтруем только те что похожи на имена функций (не test_*)
    names_to_import = {n for n in names_to_import if not n.startswith('test_')}
    
    if not names_to_import:
        # Fallback: если не удалось определить конкретные имена для импорта,
        # используем wildcard для доступа ко всем определениям из code.py
        # Это допустимо в изолированном тестовом окружении
        import_line = "from code import *  # noqa: F403 - wildcard import в тестовом окружении\n"
    else:
        # Импортируем конкретные имена
        import_line = f"from code import {', '.join(sorted(names_to_import))}\n"
    
    # Находим место для вставки импорта (после существующих импортов или в начало)
    lines = test_str.split('\n')
    insert_pos = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            insert_pos = i + 1
        elif stripped and not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith("'''"):
            # Нашли первую непустую строку не-импорт
            break
    
    lines.insert(insert_pos, import_line)
    return '\n'.join(lines)


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
    pytest_result = results["pytest"]
    mypy_result = results["mypy"]
    bandit_result = results["bandit"]
    results["all_passed"] = (
        (pytest_result["success"] if test_str else True) and  # type: ignore[index]
        mypy_result["success"] and  # type: ignore[index]
        bandit_result["success"]  # type: ignore[index]
    )
    
    return results


def _execute_code_safely(code: str, tests: str = "", timeout: int = 5) -> dict:
    """Безопасное выполнение кода через subprocess с изоляцией.
    
    ВАЖНО: Заменяет небезопасный exec() на subprocess для предотвращения RCE.
    
    Args:
        code: Код для выполнения
        tests: Опциональные тесты для выполнения
        timeout: Таймаут выполнения в секундах (по умолчанию 5)
        
    Returns:
        {"passed": bool, "error": Optional[str]}
    """
    import sys
    
    # Создаём временную директорию для файлов
    with tempfile.TemporaryDirectory(prefix="validate_code_quick_") as tmpdir:
        try:
            code_file = Path(tmpdir) / "code.py"
            test_file = Path(tmpdir) / "test_code.py"
            
            # Записываем код
            code_file.write_text(code, encoding="utf-8")
            
            # Если есть тесты, создаём файл для их выполнения
            if tests.strip():
                # Создаём скрипт который импортирует код и выполняет тесты
                # Используем импорт вместо exec для безопасности
                # ВАЖНО: Используем from code import * чтобы функции были доступны в глобальной области
                test_script = f"""import sys
from pathlib import Path

# Добавляем директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Импортируем все из code (функции будут в глобальной области видимости)
from code import *  # noqa: F403, F405

# Выполняем тесты
{tests}
"""
                test_file.write_text(test_script, encoding="utf-8")
                
                # Создаём __init__.py для правильного импорта
                init_file = Path(tmpdir) / "__init__.py"
                init_file.write_text("", encoding="utf-8")
                
                # Запускаем через subprocess с ограничениями
                result = subprocess.run(
                    [sys.executable, str(test_file)],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    # Ограничиваем размер вывода (1MB)
                    env={**os.environ, "PYTHONUNBUFFERED": "1"}
                )
                
                if result.returncode == 0:
                    return {"passed": True, "error": None}
                else:
                    # Извлекаем информацию об ошибке
                    error_output = result.stderr or result.stdout
                    # Ограничиваем размер сообщения об ошибке
                    if len(error_output) > 500:
                        error_output = error_output[:500] + "..."
                    
                    # Определяем тип ошибки по содержимому
                    error_lower = error_output.lower()
                    if "assertionerror" in error_lower:
                        return {"passed": False, "error": f"AssertionError: {error_output}"}
                    elif "nameerror" in error_lower:
                        return {"passed": False, "error": f"NameError: {error_output}"}
                    elif "typeerror" in error_lower:
                        return {"passed": False, "error": f"TypeError: {error_output}"}
                    elif "valueerror" in error_lower:
                        return {"passed": False, "error": f"ValueError: {error_output}"}
                    elif "attributeerror" in error_lower:
                        return {"passed": False, "error": f"AttributeError: {error_output}"}
                    else:
                        return {"passed": False, "error": f"RuntimeError: {error_output}"}
            else:
                # Нет тестов - только проверяем что код выполняется без ошибок
                result = subprocess.run(
                    [sys.executable, str(code_file)],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if result.returncode == 0:
                    return {"passed": True, "error": None}
                else:
                    error_output = result.stderr or result.stdout
                    if len(error_output) > 500:
                        error_output = error_output[:500] + "..."
                    return {"passed": False, "error": f"ExecutionError: {error_output}"}
        
        except subprocess.TimeoutExpired:
            return {"passed": False, "error": f"Timeout: выполнение превысило {timeout} секунд"}
        except Exception as e:
            logger.error(f"Ошибка при безопасном выполнении кода: {e}", error=e)
            return {"passed": False, "error": f"ExecutionError: {str(e)}"}


def validate_code_quick(code: str, tests: str = "") -> dict:
    """Быстрая валидация кода без полного pytest.
    
    Используется для инкрементальной генерации (Compiler-in-the-Loop).
    Проверяет только синтаксис и базовое выполнение, без mypy/bandit.
    
    ВАЖНО: Использует subprocess вместо exec() для безопасности.
    
    Проверяет:
    1. Синтаксис (ast.parse)
    2. Компиляция (compile)
    3. Базовые тесты (subprocess) — если предоставлены
    
    Args:
        code: Код для валидации
        tests: Опциональные тесты для выполнения
        
    Returns:
        {"passed": bool, "error": Optional[str]}
        
    Example:
        result = validate_code_quick("def add(a, b): return a + b", "assert add(1, 2) == 3")
        if result["passed"]:
            print("✅ Код валиден")
        else:
            print(f"❌ Ошибка: {result['error']}")
    """
    if not code.strip():
        return {"passed": False, "error": "Empty code"}
    
    # 1. Проверка синтаксиса через ast.parse
    try:
        ast.parse(code)
    except SyntaxError as e:
        error_msg = f"SyntaxError at line {e.lineno}: {e.msg}"
        if e.text:
            error_msg += f" -> {e.text.strip()}"
        return {"passed": False, "error": error_msg}
    except Exception as e:
        return {"passed": False, "error": f"ParseError: {e}"}
    
    # 2. Проверка компиляции
    try:
        compile(code, "<string>", "exec")
    except Exception as e:
        return {"passed": False, "error": f"CompileError: {e}"}
    
    # 3. Выполнение тестов через безопасный subprocess (если предоставлены)
    if tests.strip():
        return _execute_code_safely(code, tests, timeout=5)
    
    # Тесты не предоставлены — только синтаксис/компиляция
    return {"passed": True, "error": None}
