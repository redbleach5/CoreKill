#!/usr/bin/env python3
"""
Анализ проблем, которые могут мешать разработке и отладке.

Проверяет:
- Слишком общие except блоки
- Отсутствие логирования ошибок
- print/console.log в production коде
- type: ignore без комментариев
- Незавершенный код (pass, ...)
- TODO/FIXME без контекста
- Слишком сложные функции
"""
import ast
import re
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
EXCLUDE_DIRS = {'.git', 'venv', 'node_modules', '.chroma', '__pycache__', '.pytest_cache', 'dist', 'build', 'tests'}

def get_python_files(root: Path) -> List[Path]:
    """Получает все Python файлы в проекте."""
    files = []
    target_dirs = ['agents', 'backend', 'infrastructure', 'utils', 'scripts']
    
    for target_dir in target_dirs:
        target_path = root / target_dir
        if target_path.exists():
            for path in target_path.rglob('*.py'):
                if not any(exclude in path.parts for exclude in EXCLUDE_DIRS):
                    files.append(path)
    
    return files

def analyze_file(file_path: Path) -> Dict:
    """Анализирует файл на проблемы."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        return {'error': str(e), 'file': str(file_path)}
    
    result = {
        'file': str(file_path.relative_to(PROJECT_ROOT)),
        'broad_exceptions': [],
        'missing_error_logging': [],
        'print_statements': [],
        'type_ignores': [],
        'unfinished_code': [],
        'complex_functions': [],
        'todos_without_context': []
    }
    
    # Поиск проблем
    for node in ast.walk(tree):
        # Слишком общие except
        if isinstance(node, ast.ExceptHandler):
            if node.type is None or (isinstance(node.type, ast.Name) and node.type.id == 'Exception'):
                line_num = node.lineno
                # Проверяем есть ли логирование в блоке (включая вложенные if/else)
                has_logging = False
                
                def check_for_logger(stmts):
                    """Рекурсивно проверяет наличие logger в блоках."""
                    for stmt in stmts:
                        # Прямой вызов logger
                        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                            if isinstance(stmt.value.func, ast.Attribute):
                                if isinstance(stmt.value.func.value, ast.Name) and stmt.value.func.value.id == 'logger':
                                    return True
                        # Проверяем if блоки
                        if isinstance(stmt, ast.If):
                            if check_for_logger(stmt.body):
                                return True
                            if stmt.orelse and check_for_logger(stmt.orelse):
                                return True
                        # Проверяем try блоки
                        if isinstance(stmt, ast.Try):
                            if check_for_logger(stmt.body):
                                return True
                            if stmt.orelse and check_for_logger(stmt.orelse):
                                return True
                            if stmt.finalbody and check_for_logger(stmt.finalbody):
                                return True
                    return False
                
                has_logging = check_for_logger(node.body)
                
                result['broad_exceptions'].append({
                    'line': line_num,
                    'has_logging': has_logging
                })
        
        # Незавершенный код
        if isinstance(node, ast.FunctionDef):
            if node.body and isinstance(node.body[0], ast.Pass):
                result['unfinished_code'].append({
                    'type': 'pass',
                    'name': node.name,
                    'line': node.lineno
                })
            
            # Сложные функции (> 50 строк)
            if len(node.body) > 50:
                result['complex_functions'].append({
                    'name': node.name,
                    'line': node.lineno,
                    'lines': len(node.body)
                })
    
    # Поиск print
    for line_num, line in enumerate(content.split('\n'), 1):
        if re.search(r'\bprint\s*\(', line) and not line.strip().startswith('#'):
            result['print_statements'].append(line_num)
        
        # type: ignore без комментария
        if '# type: ignore' in line and not re.search(r'# type: ignore.*#', line):
            result['type_ignores'].append(line_num)
        
        # TODO/FIXME без контекста
        if re.search(r'TODO|FIXME', line, re.IGNORECASE):
            if not re.search(r'TODO.*:|FIXME.*:', line):
                result['todos_without_context'].append(line_num)
    
    return result

def main():
    """Основная функция анализа."""
    print("🔍 Анализ проблем, мешающих разработке и отладке...\n")
    
    python_files = get_python_files(PROJECT_ROOT)
    print(f"📁 Найдено Python файлов: {len(python_files)}\n")
    
    all_results = []
    stats = {
        'broad_exceptions': 0,
        'broad_exceptions_no_logging': 0,
        'print_statements': 0,
        'type_ignores': 0,
        'unfinished_code': 0,
        'complex_functions': 0,
        'todos_without_context': 0
    }
    
    for file_path in python_files:
        result = analyze_file(file_path)
        if 'error' not in result:
            all_results.append(result)
            
            stats['broad_exceptions'] += len(result['broad_exceptions'])
            stats['broad_exceptions_no_logging'] += sum(1 for e in result['broad_exceptions'] if not e['has_logging'])
            stats['print_statements'] += len(result['print_statements'])
            stats['type_ignores'] += len(result['type_ignores'])
            stats['unfinished_code'] += len(result['unfinished_code'])
            stats['complex_functions'] += len(result['complex_functions'])
            stats['todos_without_context'] += len(result['todos_without_context'])
    
    print("📊 Статистика проблем:\n")
    print(f"  🔴 Слишком общие except (Exception): {stats['broad_exceptions']}")
    print(f"     - Без логирования: {stats['broad_exceptions_no_logging']}")
    print(f"  🟡 print() в коде: {stats['print_statements']}")
    print(f"  🟡 type: ignore без комментариев: {stats['type_ignores']}")
    print(f"  🟡 Незавершенный код (pass): {stats['unfinished_code']}")
    print(f"  🟡 Сложные функции (>50 строк): {stats['complex_functions']}")
    print(f"  🟢 TODO/FIXME без контекста: {stats['todos_without_context']}\n")
    
    # Показываем примеры проблемных файлов
    print("🔴 Критичные проблемы:\n")
    
    # Файлы с except Exception без логирования
    problematic_files = [
        r for r in all_results 
        if any(not e['has_logging'] for e in r['broad_exceptions'])
    ]
    if problematic_files:
        print(f"  Файлы с except Exception без логирования ({len(problematic_files)}):")
        for result in problematic_files[:10]:
            count = sum(1 for e in result['broad_exceptions'] if not e['has_logging'])
            print(f"    • {result['file']}: {count} проблем")
        if len(problematic_files) > 10:
            print(f"    ... и еще {len(problematic_files) - 10} файлов")
        print()
    
    # Файлы с print
    files_with_print = [r for r in all_results if r['print_statements']]
    if files_with_print:
        print(f"  Файлы с print() ({len(files_with_print)}):")
        for result in files_with_print[:10]:
            print(f"    • {result['file']}: {len(result['print_statements'])} print()")
        if len(files_with_print) > 10:
            print(f"    ... и еще {len(files_with_print) - 10} файлов")
        print()
    
    # Сложные функции
    files_with_complex = [r for r in all_results if r['complex_functions']]
    if files_with_complex:
        print(f"  Файлы со сложными функциями ({len(files_with_complex)}):")
        for result in files_with_complex[:5]:
            for func in result['complex_functions'][:2]:
                print(f"    • {result['file']}:{func['line']} - {func['name']} ({func['lines']} строк)")
        print()
    
    print("✅ Анализ завершен!")

if __name__ == '__main__':
    main()
