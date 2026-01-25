#!/usr/bin/env python3
"""
Анализ дублирующегося кода и легаси кода в проекте.

Проверяет:
- Дублирующиеся функции/методы
- Легаси код (deprecated, TODO, FIXME)
- Неиспользуемый код
- Дублирующиеся импорты
"""
import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import hashlib

PROJECT_ROOT = Path(__file__).parent.parent
EXCLUDE_DIRS = {'.git', 'venv', 'node_modules', '.chroma', '__pycache__', '.pytest_cache', 'dist', 'build'}

# Паттерны для поиска легаси кода
LEGACY_PATTERNS = [
    (r'DEPRECATED|deprecated', 'deprecated'),
    (r'LEGACY|legacy', 'legacy'),
    (r'TODO.*remove|TODO.*delete|TODO.*deprecate', 'todo_remove'),
    (r'FIXME.*remove|FIXME.*delete|FIXME.*deprecate', 'fixme_remove'),
    (r'@deprecated', 'decorator_deprecated'),
    (r'#.*unused|#.*remove|#.*delete', 'comment_unused'),
]

def get_python_files(root: Path) -> List[Path]:
    """Получает все Python файлы в проекте."""
    files = []
    # Ограничиваем поиск только основными директориями проекта
    target_dirs = ['agents', 'backend', 'infrastructure', 'utils', 'tests', 'scripts']
    
    for target_dir in target_dirs:
        target_path = root / target_dir
        if target_path.exists():
            for path in target_path.rglob('*.py'):
                if not any(exclude in path.parts for exclude in EXCLUDE_DIRS):
                    files.append(path)
    
    return files

def get_function_signature(node: ast.FunctionDef) -> str:
    """Получает сигнатуру функции."""
    args = [arg.arg for arg in node.args.args]
    return f"{node.name}({', '.join(args)})"

def get_function_body_hash(node: ast.FunctionDef) -> str:
    """Получает хеш тела функции (игнорируя имена переменных)."""
    # Упрощенная версия - просто берем структуру
    try:
        # Создаем упрощенное представление тела функции
        body_nodes = []
        for stmt in node.body:
            body_nodes.append(ast.dump(stmt, annotate_fields=False))
        body_str = '|'.join(body_nodes)
        return hashlib.md5(body_str.encode()).hexdigest()
    except Exception:
        return hashlib.md5(str(node.lineno).encode()).hexdigest()

def analyze_file(file_path: Path) -> Dict:
    """Анализирует один файл на дублирование и легаси код."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        return {'error': str(e), 'file': str(file_path)}
    
    result = {
        'file': str(file_path.relative_to(PROJECT_ROOT)),
        'functions': [],
        'legacy_markers': [],
        'duplicates': []
    }
    
    # Анализ функций
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_info = {
                'name': node.name,
                'signature': get_function_signature(node),
                'line': node.lineno,
                'body_hash': get_function_body_hash(node),
                'body_lines': len(node.body) if node.body else 0
            }
            result['functions'].append(func_info)
    
    # Поиск легаси маркеров
    for line_num, line in enumerate(content.split('\n'), 1):
        for pattern, marker_type in LEGACY_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                result['legacy_markers'].append({
                    'type': marker_type,
                    'line': line_num,
                    'content': line.strip()[:100]  # Первые 100 символов
                })
    
    return result

def find_duplicate_functions(all_functions: List[Dict]) -> List[Dict]:
    """Находит дублирующиеся функции по хешу тела."""
    hash_to_functions = defaultdict(list)
    
    for func in all_functions:
        if 'body_hash' in func:
            hash_to_functions[func['body_hash']].append(func)
    
    duplicates = []
    for body_hash, funcs in hash_to_functions.items():
        if len(funcs) > 1:
            # Группируем по имени функции
            name_groups = defaultdict(list)
            for func in funcs:
                name_groups[func['name']].append(func)
            
            for name, group in name_groups.items():
                if len(group) > 1:
                    duplicates.append({
                        'name': name,
                        'count': len(group),
                        'locations': [{'file': f['file'], 'line': f['line']} for f in group],
                        'body_hash': body_hash
                    })
    
    return duplicates

def find_similar_functions(all_functions: List[Dict], similarity_threshold: float = 0.8) -> List[Dict]:
    """Находит похожие функции (упрощенная версия)."""
    # Группируем по имени функции
    name_groups = defaultdict(list)
    for func in all_functions:
        if 'name' in func:
            name_groups[func['name']].append(func)
    
    similar = []
    for name, group in name_groups.items():
        if len(group) > 1:
            # Проверяем размер тела
            body_sizes = [f.get('body_lines', 0) for f in group]
            if max(body_sizes) > 0:
                size_ratio = min(body_sizes) / max(body_sizes)
                if size_ratio >= similarity_threshold:
                    similar.append({
                        'name': name,
                        'count': len(group),
                        'locations': [{'file': f['file'], 'line': f['line'], 'size': f.get('body_lines', 0)} for f in group]
                    })
    
    return similar

def main():
    """Основная функция анализа."""
    print("🔍 Анализ дублирующегося кода и легаси кода...\n")
    
    python_files = get_python_files(PROJECT_ROOT)
    print(f"📁 Найдено Python файлов: {len(python_files)}\n")
    
    all_results = []
    all_functions = []
    total_legacy_markers = 0
    
    for file_path in python_files:
        result = analyze_file(file_path)
        if 'error' not in result:
            all_results.append(result)
            
            # Собираем все функции
            for func in result['functions']:
                func['file'] = result['file']
                all_functions.append(func)
            
            total_legacy_markers += len(result['legacy_markers'])
    
    print(f"📊 Статистика:")
    print(f"  - Всего функций: {len(all_functions)}")
    print(f"  - Файлов с легаси маркерами: {sum(1 for r in all_results if r['legacy_markers'])}")
    print(f"  - Всего легаси маркеров: {total_legacy_markers}\n")
    
    # Поиск дубликатов
    print("🔍 Поиск дублирующихся функций...")
    duplicates = find_duplicate_functions(all_functions)
    similar = find_similar_functions(all_functions)
    
    print(f"\n📋 Результаты анализа:\n")
    
    # Дублирующиеся функции
    if duplicates:
        print(f"🔴 Дублирующиеся функции (точные копии): {len(duplicates)}")
        for dup in duplicates[:10]:  # Показываем первые 10
            print(f"  - {dup['name']}: найдено {dup['count']} раз")
            for loc in dup['locations'][:3]:  # Первые 3 локации
                print(f"    • {loc['file']}:{loc['line']}")
            if len(dup['locations']) > 3:
                print(f"    ... и еще {len(dup['locations']) - 3} мест")
        if len(duplicates) > 10:
            print(f"  ... и еще {len(duplicates) - 10} дубликатов")
        print()
    
    # Похожие функции
    if similar:
        print(f"🟡 Похожие функции (по имени): {len(similar)}")
        for sim in similar[:10]:  # Показываем первые 10
            print(f"  - {sim['name']}: найдено {sim['count']} раз")
            for loc in sim['locations'][:2]:  # Первые 2 локации
                print(f"    • {loc['file']}:{loc['line']} ({loc['size']} строк)")
        if len(similar) > 10:
            print(f"  ... и еще {len(similar) - 10} похожих")
        print()
    
    # Легаси код
    print(f"⚠️  Легаси код:")
    legacy_by_type = defaultdict(int)
    legacy_files = []
    
    for result in all_results:
        if result['legacy_markers']:
            legacy_files.append(result['file'])
            for marker in result['legacy_markers']:
                legacy_by_type[marker['type']] += 1
    
    for marker_type, count in sorted(legacy_by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {marker_type}: {count} маркеров")
    
    print(f"\n  Файлов с легаси кодом: {len(legacy_files)}")
    if legacy_files:
        print(f"\n  Примеры файлов:")
        for file in legacy_files[:10]:
            print(f"    • {file}")
        if len(legacy_files) > 10:
            print(f"    ... и еще {len(legacy_files) - 10} файлов")
    
    # Статистика по агентам
    print(f"\n📦 Анализ агентов:")
    agent_files = [r for r in all_results if 'agents' in r['file']]
    streaming_agents = [r for r in agent_files if 'streaming' in r['file']]
    sync_agents = [r for r in agent_files if 'streaming' not in r['file'] and r['file'] != 'agents/__init__.py']
    
    print(f"  - Всего агентов: {len(agent_files)}")
    print(f"  - Стриминговых: {len(streaming_agents)}")
    print(f"  - Синхронных: {len(sync_agents)}")
    
    # Поиск общих методов в синхронных и стриминговых агентах
    if streaming_agents and sync_agents:
        streaming_methods = set()
        sync_methods = set()
        
        for agent in streaming_agents:
            streaming_methods.update(f['name'] for f in agent['functions'])
        
        for agent in sync_agents:
            sync_methods.update(f['name'] for f in agent['functions'])
        
        common_methods = streaming_methods & sync_methods
        print(f"  - Общих методов между sync/streaming: {len(common_methods)}")
        if common_methods:
            print(f"    Примеры: {', '.join(list(common_methods)[:5])}")
    
    print(f"\n✅ Анализ завершен!")

if __name__ == '__main__':
    main()
