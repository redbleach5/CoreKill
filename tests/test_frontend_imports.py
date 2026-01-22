"""Тесты для проверки импортов в frontend коде.

Проверяет, что все используемые функции/хуки имеют соответствующие импорты.
"""
import pytest
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CHECK_IMPORTS_SCRIPT = PROJECT_ROOT / "scripts" / "check_imports.py"


@pytest.mark.frontend
def test_frontend_imports():
    """Проверяет, что все импорты в frontend корректны."""
    if not CHECK_IMPORTS_SCRIPT.exists():
        pytest.skip(f"Скрипт проверки импортов не найден: {CHECK_IMPORTS_SCRIPT}")
    
    result = subprocess.run(
        [sys.executable, str(CHECK_IMPORTS_SCRIPT)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        pytest.fail(
            f"Обнаружены проблемы с импортами:\n{result.stdout}\n{result.stderr}"
        )
