"""Утилита для работы с файлами при режимах modify/debug."""
from pathlib import Path
from typing import Optional, Tuple


def extract_file_path_from_task(task: str) -> Optional[str]:
    """Извлекает путь к файлу из задачи (если указан).
    
    Ищет паттерны типа "файл: path/to/file.py" или "file: path/to/file.py"
    или просто упоминание пути к файлу в формате .py/.ts/.js
    
    Args:
        task: Текст задачи
        
    Returns:
        Путь к файлу или None если не найден
    """
    task_lower = task.lower()
    
    # Ищем явные указания файла
    patterns = [
        "файл:",
        "file:",
        "в файле",
        "in file"
    ]
    
    for pattern in patterns:
        if pattern in task_lower:
            idx = task_lower.find(pattern)
            # Берём текст после паттерна до конца строки или до пробела/новой строки
            after_pattern = task[idx + len(pattern):].strip()
            # Ищем путь к файлу (с расширением)
            parts = after_pattern.split()
            for part in parts:
                if any(part.endswith(ext) for ext in ['.py', '.ts', '.js', '.tsx', '.jsx']):
                    file_path = part.strip(',:;"\'')
                    if Path(file_path).exists():
                        return file_path
    
    # Ищем упоминания путей к Python файлам в тексте
    words = task.split()
    for word in words:
        word_clean = word.strip(',:;"\'')
        if word_clean.endswith('.py') and Path(word_clean).exists():
            return word_clean
    
    return None


def read_file_context(file_path: str, max_lines: int = 1000) -> Optional[str]:
    """Читает содержимое файла для использования как контекст.
    
    Args:
        file_path: Путь к файлу
        max_lines: Максимальное количество строк для чтения (избегаем огромных файлов)
        
    Returns:
        Содержимое файла или None если файл не существует или слишком большой
    """
    path = Path(file_path)
    
    if not path.exists():
        return None
    
    if not path.is_file():
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    return '\n'.join(lines) + f"\n\n... (файл обрезан, всего {max_lines} строк) ...\n"
                lines.append(line.rstrip())
            return '\n'.join(lines)
    except Exception:
        return None


def prepare_modify_context(task: str, existing_file_content: str) -> str:
    """Подготавливает контекст для режима modify/debug.
    
    Args:
        task: Текст задачи
        existing_file_content: Содержимое существующего файла
        
    Returns:
        Отформатированный контекст для использования в workflow
    """
    context = f"""[Существующий код для модификации/отладки]

{existing_file_content}

---
[Задача пользователя]
{task}

Внимание: Нужно изменить/исправить существующий код выше, а не создавать новый с нуля.
"""
    return context
