#!/usr/bin/env python3
"""Скрипт для автоматического добавления маркеров в тесты.

Добавляет маркеры @pytest.mark.* в тесты на основе их расположения.
"""
import re
from pathlib import Path

def add_markers_to_file(file_path: Path):
    """Добавляет маркеры в файл тестов."""
    content = file_path.read_text(encoding='utf-8')
    original_content = content
    
    # Определяем маркеры на основе пути
    markers = []
    
    if "test_smoke" in str(file_path):
        markers.append("@pytest.mark.smoke")
    elif "test_critical_failures" in str(file_path):
        markers.append("@pytest.mark.critical")
    
    if "test_backend" in str(file_path):
        markers.append("@pytest.mark.backend")
    elif "test_infrastructure" in str(file_path):
        markers.append("@pytest.mark.infrastructure")
    elif any(x in str(file_path) for x in ["test_coder", "test_planner", "test_reflection", "test_debugger", "test_agent"]):
        markers.append("@pytest.mark.agents")
    elif "test_utils" in str(file_path):
        markers.append("@pytest.mark.utils")
    
    if not markers:
        return False  # Не нужно добавлять маркеры
    
    # Находим все функции test_* (включая async)
    pattern = r'(\s+)(@pytest\.mark\.\w+\s+)?(@pytest\.mark\.asyncio\s+)?(async\s+)?(def test_\w+\([^)]*\):)'
    
    def add_markers_to_test(match):
        indent = match.group(1)
        existing_marker = match.group(2) or ""
        asyncio_marker = match.group(3) or ""
        async_keyword = match.group(4) or ""
        test_def = match.group(5)
        
        # Проверяем есть ли уже нужные маркеры
        if any(marker in existing_marker for marker in markers):
            return match.group(0)  # Уже есть нужные маркеры
        
        # Добавляем маркеры (перед async если есть)
        markers_str = '\n'.join(f"{indent}{marker}" for marker in markers)
        
        if asyncio_marker:
            # Если есть @pytest.mark.asyncio, добавляем перед ним
            return f"{markers_str}\n{indent}{asyncio_marker}{indent}{async_keyword}{test_def}"
        else:
            # Иначе просто перед функцией
            return f"{markers_str}\n{indent}{async_keyword}{test_def}"
    
    new_content = re.sub(pattern, add_markers_to_test, content)
    
    if new_content != original_content:
        file_path.write_text(new_content, encoding='utf-8')
        return True
    return False

def main():
    """Главная функция."""
    tests_dir = Path("tests")
    
    if not tests_dir.exists():
        print("❌ Директория tests/ не найдена")
        return
    
    modified = []
    for test_file in tests_dir.glob("test_*.py"):
        if add_markers_to_file(test_file):
            modified.append(test_file.name)
    
    if modified:
        print(f"✅ Обновлено {len(modified)} файлов:")
        for name in modified:
            print(f"  - {name}")
    else:
        print("ℹ️  Файлы не требуют обновления")

if __name__ == "__main__":
    main()
