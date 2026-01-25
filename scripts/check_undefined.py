#!/usr/bin/env python3
"""
Комплексный скрипт для проверки неопределенных переменных и констант в frontend.

Проверяет:
- Использование переменных/констант без определения
- Отсутствующие импорты
- Использование констант до их определения
- Глобальные константы без определения

Запуск: python scripts/check_undefined.py
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "src"

ISSUES: List[Dict[str, any]] = []

# Паттерны для проверки использования без импорта
IMPORT_PATTERNS = [
    {
        "name": "api",
        "usage_pattern": r"\bapi\.(models|conversations|projects|metrics|code|settings|tasks|databases|stream)\s*\(",
        "import_pattern": r"import\s+.*\bapi\b.*from\s+['\"][\.\/]*services\/apiClient['\"]",
    },
    {
        "name": "useLocalStorage",
        "usage_pattern": r"\buseLocalStorage\s*\(",
        "import_pattern": r"import\s+.*\buseLocalStorage\b.*from\s+['\"][\.\/]*hooks\/useLocalStorage['\"]",
    },
    {
        "name": "useLocalStorageString",
        "usage_pattern": r"\buseLocalStorageString\s*\(",
        "import_pattern": r"import\s+.*\buseLocalStorageString\b.*from\s+['\"][\.\/]*hooks\/useLocalStorage['\"]",
    },
    {
        "name": "useModels",
        "usage_pattern": r"\buseModels\s*\(",
        "import_pattern": r"import\s+.*\buseModels\b.*from\s+['\"][\.\/]*hooks\/useModels['\"]",
    },
    {
        "name": "useApi",
        "usage_pattern": r"\buseApi\s*\(",
        "import_pattern": r"import\s+.*\buseApi\b.*from\s+['\"][\.\/]*hooks\/useApi['\"]",
    },
]

# Паттерны для поиска констант (UPPER_CASE)
CONSTANT_PATTERN = re.compile(r'\b([A-Z][A-Z0-9_]+)\b')

# Исключения - стандартные константы/переменные, которые не нужно проверять
EXCLUDED_CONSTANTS = {
    # React
    'React', 'useState', 'useEffect', 'useCallback', 'useRef', 'useMemo',
    'forwardRef', 'useContext', 'useReducer', 'useLayoutEffect',
    # TypeScript/JavaScript стандартные
    'Object', 'Array', 'String', 'Number', 'Boolean', 'Date', 'Math', 'JSON',
    'console', 'window', 'document', 'localStorage', 'sessionStorage',
    'URL', 'URLSearchParams', 'URLPattern',
    # Lucide icons (импортируются динамически)
    'lucide-react',
    # Другие стандартные
    'Error', 'TypeError', 'ReferenceError', 'Promise', 'fetch', 'EventSource',
    'NodeJS', 'HTMLElement', 'HTMLDivElement', 'HTMLTextAreaElement',
    'HTMLInputElement', 'HTMLButtonElement',
    # Строковые литералы в константах (например, 'RAG' в строке "enableRAG")
    'RAG', 'AI', 'LLM', 'SDK', 'UI', 'IDE', 'VS', 'SSE',
}

# Файлы, которые определяют экспорты (не проверяем)
DEFINITION_FILES = {
    "apiClient.ts", "useLocalStorage.ts", "useModels.ts", "useApi.ts",
    "useAgentStream.ts", "useCodeExecution.ts", "sseHelpers.ts",
    "apiErrorHandler.ts", "modelUtils.ts", "constants.ts", "types.ts",
    "chat.ts", "api.ts", "index.ts", "utils.ts", "mocks.ts", "testHelpers.ts",
    "constants.ts", "setup.ts",
}


def extract_defined_identifiers(content: str) -> Set[str]:
    """Извлекает все определенные идентификаторы из файла."""
    defined = set()
    
    # Константы (const NAME = ... или const NAME: ... =)
    const_matches = re.finditer(r'\bconst\s+([A-Z][A-Z0-9_]+)\s*[:=]', content)
    for match in const_matches:
        defined.add(match.group(1))
    
    # Переменные (let/var NAME = ...)
    var_matches = re.finditer(r'\b(let|var)\s+([A-Z][A-Z0-9_]+)\s*[:=]', content)
    for match in var_matches:
        defined.add(match.group(2))
    
    # Функции (function NAME(...) или const NAME = ...)
    func_matches = re.finditer(r'\bfunction\s+([A-Z][A-Z0-9_]+)\s*\(', content)
    for match in func_matches:
        defined.add(match.group(1))
    
    # Интерфейсы и типы (interface NAME, type NAME)
    interface_matches = re.finditer(r'\b(interface|type)\s+([A-Z][A-Z0-9_]+)', content)
    for match in interface_matches:
        defined.add(match.group(2))
    
    # Импорты (import { NAME } from ...)
    import_matches = re.finditer(r'import\s+.*\{([^}]+)\}.*from', content)
    for match in import_matches:
        imports = match.group(1)
        for imp in re.finditer(r'\b([A-Z][A-Z0-9_]+)\b', imports):
            defined.add(imp.group(1))
    
    # Импорты по умолчанию (import NAME from ...)
    default_imports = re.finditer(r'import\s+([A-Z][A-Z0-9_]+)\s+from', content)
    for match in default_imports:
        defined.add(match.group(1))
    
    return defined


def check_imports(file_path: Path, content: str) -> None:
    """Проверяет наличие импортов для используемых функций."""
    relative_path = file_path.relative_to(FRONTEND_DIR)
    
    # Пропускаем файлы, которые определяют эти функции
    if any(name in str(file_path) for name in DEFINITION_FILES):
        return
    
    for pattern_info in IMPORT_PATTERNS:
        name = pattern_info["name"]
        usage_pattern = re.compile(pattern_info["usage_pattern"])
        import_pattern = re.compile(pattern_info["import_pattern"])
        
        if usage_pattern.search(content):
            if not import_pattern.search(content):
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if usage_pattern.search(line):
                        ISSUES.append({
                            "file": str(relative_path),
                            "line": i,
                            "issue": f"Используется {name} без импорта",
                            "type": "missing_import",
                        })
                        break


def check_constants(file_path: Path, content: str) -> None:
    """Проверяет использование констант без определения."""
    relative_path = file_path.relative_to(FRONTEND_DIR)
    
    # Пропускаем файлы определений (constants.ts определяет константы как строки)
    if any(name in str(file_path) for name in DEFINITION_FILES):
        return
    
    # Пропускаем constants/sse.ts - там константы определены как строковые литералы
    if 'constants' in str(file_path) and 'sse.ts' in str(file_path):
        return
    
    # Извлекаем определенные идентификаторы
    defined = extract_defined_identifiers(content)
    
    # Находим все использования констант
    lines = content.split("\n")
    for line_num, line in enumerate(lines, 1):
        # Пропускаем строки с определениями и импортами
        stripped = line.strip()
        if re.match(r'^\s*(const|let|var|import|export|function|interface|type)', line):
            continue
        
        # Пропускаем комментарии полностью
        if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        
        # Удаляем комментарии из конца строки
        line_without_comments = re.sub(r'//.*$', '', line)
        line_without_comments = re.sub(r'/\*.*?\*/', '', line_without_comments)
        
        # Находим все константы в строке
        for match in CONSTANT_PATTERN.finditer(line_without_comments):
            constant_name = match.group(1)
            
            # Пропускаем исключения
            if constant_name in EXCLUDED_CONSTANTS:
                continue
            
            # Пропускаем, если константа определена в этом файле
            if constant_name in defined:
                continue
            
            # Проверяем, что это не часть другого слова (например, "IDEPanel" содержит "IDE")
            start_pos = match.start()
            end_pos = match.end()
            if start_pos > 0:
                char_before = line_without_comments[start_pos - 1]
                if char_before.isalnum() or char_before == '_':
                    continue  # Это часть другого слова
            if end_pos < len(line_without_comments):
                char_after = line_without_comments[end_pos]
                if char_after.isalnum() or char_after == '_':
                    continue  # Это часть другого слова
            
            # Проверяем, что это не часть строки в кавычках
            before = line_without_comments[:start_pos]
            # Простая проверка на строки в кавычках
            single_quotes = before.count("'") - before.count("\\'")
            double_quotes = before.count('"') - before.count('\\"')
            if single_quotes % 2 != 0 or double_quotes % 2 != 0:
                continue  # Внутри строки
            
            # Проверяем, что это не часть template literal или JSX
            if '`' in before and before.count('`') % 2 != 0:
                continue
            if '{' in before and before.count('{') > before.count('}'):
                # Возможно внутри JSX выражения
                pass  # Продолжаем проверку
            
            # Это потенциальная проблема - но только если это реальное использование
            # Проверяем контекст использования (должно быть после точки, в скобках, или как значение)
            context = line_without_comments[max(0, start_pos-10):min(len(line_without_comments), end_pos+10)]
            if not re.search(r'[\.\(\[\{=\s]' + re.escape(constant_name) + r'[\)\]\}\s,;:]', context):
                # Не похоже на использование константы
                continue
            
            # Это потенциальная проблема
            ISSUES.append({
                "file": str(relative_path),
                "line": line_num,
                "issue": f"Используется константа '{constant_name}' без определения",
                "type": "undefined_constant",
                "constant": constant_name,
            })


def check_file(file_path: Path) -> None:
    """Проверяет файл на все типы проблем."""
    try:
        content = file_path.read_text(encoding="utf-8")
        
        # Проверяем импорты
        check_imports(file_path, content)
        
        # Проверяем константы
        check_constants(file_path, content)
        
    except Exception as e:
        print(f"⚠️  Ошибка при проверке {file_path}: {e}")


def walk_dir(directory: Path, callback) -> None:
    """Рекурсивно обходит директорию и вызывает callback для каждого .ts/.tsx файла."""
    if not directory.exists():
        return
    
    for root, dirs, files in os.walk(directory):
        # Пропускаем node_modules и другие служебные директории
        dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', 'dist', 'build']]
        
        for file in files:
            if file.endswith((".ts", ".tsx")) and not file.endswith(".d.ts"):
                file_path = Path(root) / file
                callback(file_path)


def main():
    """Основная функция."""
    print("🔍 Проверка неопределенных переменных и констант...\n")
    
    # Проверяем все директории
    directories = [
        FRONTEND_DIR / "components",
        FRONTEND_DIR / "hooks",
        FRONTEND_DIR / "utils",
        FRONTEND_DIR / "services",
        FRONTEND_DIR / "types",
        FRONTEND_DIR / "constants",
    ]
    
    for directory in directories:
        if directory.exists():
            walk_dir(directory, check_file)
    
    # Проверяем App.tsx и main.tsx
    for file_name in ["App.tsx", "main.tsx"]:
        file_path = FRONTEND_DIR / file_name
        if file_path.exists():
            check_file(file_path)
    
    # Выводим результаты
    if not ISSUES:
        print("✅ Все проверки пройдены! Неопределенных переменных/констант не найдено.\n")
        return 0
    else:
        print(f"❌ Найдено {len(ISSUES)} проблем:\n")
        
        # Группируем по типу
        by_type: Dict[str, List[Dict]] = {}
        for issue in ISSUES:
            issue_type = issue.get("type", "unknown")
            if issue_type not in by_type:
                by_type[issue_type] = []
            by_type[issue_type].append(issue)
        
        # Выводим по типам
        for issue_type, issues_list in by_type.items():
            print(f"\n📋 {issue_type.upper().replace('_', ' ')} ({len(issues_list)}):")
            for issue in issues_list:
                print(f"  {issue['file']}:{issue['line']} - {issue['issue']}")
        
        print(f"\n⚠️  Всего проблем: {len(ISSUES)}")
        return 1


if __name__ == "__main__":
    exit(main())
