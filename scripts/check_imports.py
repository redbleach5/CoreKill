#!/usr/bin/env python3
"""
Скрипт для проверки импортов в frontend компонентах.

Проверяет:
- Использование api без импорта
- Использование useLocalStorage без импорта
- Использование useModels без импорта
- Использование useApi без импорта

Запуск: python scripts/check_imports.py
"""
import os
import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "src"
COMPONENTS_DIR = FRONTEND_DIR / "components"
HOOKS_DIR = FRONTEND_DIR / "hooks"
UTILS_DIR = FRONTEND_DIR / "utils"

ISSUES = []

# Паттерны для поиска использования без импорта
PATTERNS = [
    {
        "name": "api",
        "pattern": r"\bapi\.(models|conversations|projects|metrics|code|settings|tasks|databases|stream)\s*\(",
        "import_pattern": r"import\s+.*\bapi\b.*from\s+['\"][\.\/]*services\/apiClient['\"]",
    },
    {
        "name": "useLocalStorage",
        "pattern": r"\buseLocalStorage\s*\(",
        "import_pattern": r"import\s+.*\buseLocalStorage\b.*from\s+['\"][\.\/]*hooks\/useLocalStorage['\"]",
    },
    {
        "name": "useLocalStorageString",
        "pattern": r"\buseLocalStorageString\s*\(",
        "import_pattern": r"import\s+.*\buseLocalStorageString\b.*from\s+['\"][\.\/]*hooks\/useLocalStorage['\"]",
    },
    {
        "name": "useModels",
        "pattern": r"\buseModels\s*\(",
        "import_pattern": r"import\s+.*\buseModels\b.*from\s+['\"][\.\/]*hooks\/useModels['\"]",
    },
    {
        "name": "useApi",
        "pattern": r"\buseApi\s*\(",
        "import_pattern": r"import\s+.*\buseApi\b.*from\s+['\"][\.\/]*hooks\/useApi['\"]",
    },
]


def check_file(file_path: Path) -> None:
    """Проверяет файл на наличие использования без импорта."""
    content = file_path.read_text(encoding="utf-8")
    relative_path = file_path.relative_to(FRONTEND_DIR)
    
    # Пропускаем файлы, которые определяют эти функции
    if any(
        name in str(file_path)
        for name in ["apiClient.ts", "useLocalStorage.ts", "useModels.ts", "useApi.ts"]
    ):
        return
    
    for pattern_info in PATTERNS:
        name = pattern_info["name"]
        pattern = re.compile(pattern_info["pattern"])
        import_pattern = re.compile(pattern_info["import_pattern"])
        
        if pattern.search(content):
            # Проверяем наличие импорта
            if not import_pattern.search(content):
                # Находим строку с использованием
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if pattern.search(line):
                        ISSUES.append(
                            {
                                "file": str(relative_path),
                                "issue": f"Используется {name} без импорта",
                                "line": i,
                            }
                        )
                        break


def walk_dir(directory: Path, callback) -> None:
    """Рекурсивно обходит директорию и вызывает callback для каждого .ts/.tsx файла."""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith((".ts", ".tsx")):
                file_path = Path(root) / file
                callback(file_path)


# Проверяем компоненты
if COMPONENTS_DIR.exists():
    walk_dir(COMPONENTS_DIR, check_file)

# Проверяем хуки
if HOOKS_DIR.exists():
    walk_dir(HOOKS_DIR, check_file)

# Проверяем утилиты
if UTILS_DIR.exists():
    walk_dir(UTILS_DIR, check_file)

# Проверяем App.tsx
app_path = FRONTEND_DIR / "App.tsx"
if app_path.exists():
    check_file(app_path)

# Выводим результаты
if not ISSUES:
    print("✅ Все импорты корректны!")
    exit(0)
else:
    print("❌ Найдены проблемы с импортами:\n")
    for issue in ISSUES:
        print(f"  {issue['file']}:{issue['line']} - {issue['issue']}")
    exit(1)
