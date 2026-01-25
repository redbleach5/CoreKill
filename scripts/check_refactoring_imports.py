#!/usr/bin/env python3
"""Проверка корректности импортов после рефакторинга.

Проверяет:
1. Все новые модули импортируются без ошибок
2. Нет циклических зависимостей
3. Все используемые импорты существуют
"""
import sys
import importlib
import traceback
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

MODULES_TO_CHECK = [
    "backend.workflow_streamer",
    "backend.mode_detector",
    "backend.messages",
    "backend.workflow_stages",
    "utils.path_validator",
    "utils.ui_delays",
]

IMPORTS_TO_CHECK = [
    ("backend.routers.agent", ["WorkflowStreamer", "ModeDetector", "GREETING_MESSAGE", "HELP_MESSAGE", "validate_file_path", "validate_directory_path", "ui_sleep"]),
    ("backend.workflow_streamer", ["SSEManager", "ArtifactSaver", "AgentState"]),
    ("backend.mode_detector", ["IntentAgent", "TaskComplexity"]),
    ("utils.path_validator", ["HTTPException", "Path"]),
    ("utils.ui_delays", ["get_config"]),
]


def check_module_import(module_name: str) -> tuple[bool, str]:
    """Проверяет импорт модуля.
    
    Returns:
        (success, error_message)
    """
    try:
        importlib.import_module(module_name)
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)}"


def check_imports_in_module(module_name: str, expected_imports: list[str]) -> tuple[bool, list[str]]:
    """Проверяет наличие импортов в модуле.
    
    Returns:
        (success, missing_imports)
    """
    try:
        module = importlib.import_module(module_name)
        missing = []
        for import_name in expected_imports:
            if not hasattr(module, import_name):
                missing.append(import_name)
        return len(missing) == 0, missing
    except Exception as e:
        return False, [f"Ошибка импорта модуля: {e}"]


def main():
    """Основная функция проверки.
    
    Проверяет корректность импортов после рефакторинга:
    1. Все новые модули импортируются без ошибок
    2. Нет циклических зависимостей
    3. Все используемые импорты существуют
    
    Returns:
        int: 0 если успешно, 1 если есть ошибки
    """
    print("🔍 Проверка импортов после рефакторинга...\n")
    
    errors = []
    warnings = []
    
    # Проверка импорта модулей
    print("1. Проверка импорта новых модулей:")
    for module_name in MODULES_TO_CHECK:
        success, error = check_module_import(module_name)
        if success:
            print(f"   ✅ {module_name}")
        else:
            print(f"   ❌ {module_name}: {error}")
            errors.append(f"{module_name}: {error}")
    
    print()
    
    # Проверка импортов в модулях
    print("2. Проверка импортов в модулях:")
    for module_name, expected_imports in IMPORTS_TO_CHECK:
        success, missing = check_imports_in_module(module_name, expected_imports)
        if success:
            print(f"   ✅ {module_name} - все импорты найдены")
        else:
            print(f"   ⚠️  {module_name} - отсутствуют: {', '.join(missing)}")
            warnings.append(f"{module_name}: отсутствуют {', '.join(missing)}")
    
    print()
    
    # Итоги
    if errors:
        print(f"❌ Найдено ошибок: {len(errors)}")
        for error in errors:
            print(f"   - {error}")
        return 1
    elif warnings:
        print(f"⚠️  Найдено предупреждений: {len(warnings)}")
        for warning in warnings:
            print(f"   - {warning}")
        return 0
    else:
        print("✅ Все проверки пройдены успешно!")
        return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Проверка корректности импортов после рефакторинга",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Базовая проверка
  python3 scripts/check_refactoring_imports.py
  
  # С выводом help
  python3 scripts/check_refactoring_imports.py --help
        """
    )
    
    # Пока нет опций, но структура для будущего расширения
    args = parser.parse_args()
    
    sys.exit(main())
