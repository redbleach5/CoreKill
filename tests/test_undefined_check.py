"""
Тест для проверки неопределенных переменных и констант.

Проверяет, что в проекте нет использования неопределенных переменных/констант,
которые могут привести к ошибкам "is not defined" в runtime.
"""
import subprocess
import sys
from pathlib import Path

def test_undefined_check():
    """Проверяет, что скрипт check_undefined.py не находит реальных проблем."""
    script_path = Path(__file__).parent.parent / "scripts" / "check_undefined.py"
    
    if not script_path.exists():
        print(f"⚠️  Скрипт {script_path} не найден")
        return False
    
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        cwd=script_path.parent.parent
    )
    
    output = result.stdout + result.stderr
    
    # Критические проблемы, которые не должны встречаться
    critical_issues = [
        "DEFAULT_SIDEBAR_WIDTH",
        "DEFAULT_SETTINGS",
        "DEFAULT_STAGE_DURATIONS",
        "WORKFLOW_NODES",
    ]
    
    # Проверяем критические проблемы
    for issue in critical_issues:
        if issue in output and "без определения" in output:
            print(f"❌ Найдена критическая проблема с {issue}!")
            print(output)
            assert False, f"Критическая проблема с {issue}"
    
    # Если скрипт завершился с кодом 0, все хорошо
    if result.returncode == 0:
        print("✅ Проверка неопределенных переменных пройдена")
        return
    
    # Если есть проблемы, но не критические - предупреждение
    print(f"⚠️  Найдено {output.count('без определения')} потенциальных проблем")
    print("Проверьте вывод скрипта для деталей")
    print("\nВывод скрипта:")
    print(output)
    
    assert False, f"Проверка неопределенных переменных не пройдена (код возврата: {result.returncode})"

if __name__ == "__main__":
    success = test_undefined_check()
    sys.exit(0 if success else 1)
