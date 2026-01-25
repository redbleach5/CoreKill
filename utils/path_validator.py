"""Утилиты для валидации и ограничения путей к файлам.

Предотвращает доступ к файлам вне проекта (path traversal атаки).

Примеры использования:
    ```python
    from utils.path_validator import validate_file_path, validate_directory_path
    
    # Валидация пути к файлу (выбросит HTTPException если путь вне проекта)
    try:
        safe_path = validate_file_path(
            "path/to/file.py",
            project_path="/project/root"
        )
        # Используем безопасный путь
        with open(safe_path) as f:
            content = f.read()
    except HTTPException as e:
        # Обработка ошибки доступа
        # Доступ запрещён: {e.detail}
    
    # Валидация пути к директории
    safe_dir = validate_directory_path(
        "path/to/directory",
        project_path="/project/root"
    )
    ```

Зависимости:
    - pathlib: для работы с путями
    - fastapi: для HTTPException
    - utils.logger: для логирования предупреждений

Связанные утилиты:
    - backend.routers: используется для защиты API endpoints

Примечания:
    - Критично для безопасности: предотвращает path traversal атаки
    - Всегда используйте перед доступом к файлам из пользовательского ввода
    - Разрешает пути (убирает .. и симлинки) перед проверкой
    - Использует is_relative_to() для Python 3.9+, fallback для старых версий
"""
from pathlib import Path
from typing import Optional
from fastapi import HTTPException
from utils.logger import get_logger

logger = get_logger()


def get_project_root(project_path: Optional[str] = None) -> Path:
    """Получает корень проекта для ограничения доступа к файлам.
    
    Args:
        project_path: Путь к проекту (если указан)
        
    Returns:
        Path к корню проекта
    """
    if project_path:
        return Path(project_path).resolve()
    
    # Fallback: используем текущую рабочую директорию
    # В продакшене рекомендуется явно указывать project_path
    return Path.cwd().resolve()


def validate_file_path(
    file_path: str,
    project_root: Optional[Path] = None,
    project_path: Optional[str] = None
) -> Path:
    """Валидирует путь к файлу и проверяет, что он находится в пределах проекта.
    
    Args:
        file_path: Путь к файлу для проверки
        project_root: Корень проекта (если уже вычислен)
        project_path: Путь к проекту (если нужно вычислить project_root)
        
    Returns:
        Resolved Path к файлу
        
    Raises:
        HTTPException: Если путь находится вне проекта или некорректен
    """
    if not file_path:
        raise HTTPException(status_code=400, detail="Путь к файлу не указан")
    
    try:
        # Разрешаем путь (убираем .. и симлинки)
        resolved_path = Path(file_path).resolve()
    except (ValueError, OSError) as e:
        logger.warning(f"⚠️ Некорректный путь: {file_path}, ошибка: {e}")
        raise HTTPException(status_code=400, detail=f"Некорректный путь: {str(e)}")
    
    # Получаем корень проекта
    if project_root is None:
        project_root = get_project_root(project_path)
    
    # Проверяем, что путь находится в пределах проекта
    try:
        # is_relative_to доступен в Python 3.9+
        if not resolved_path.is_relative_to(project_root):
            logger.warning(
                f"⚠️ Попытка доступа к файлу вне проекта: {file_path} "
                f"(проект: {project_root})"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Доступ запрещён: файл находится вне проекта"
            )
    except AttributeError:
        # Fallback для Python < 3.9
        try:
            resolved_path.relative_to(project_root)
        except ValueError:
            logger.warning(
                f"⚠️ Попытка доступа к файлу вне проекта: {file_path} "
                f"(проект: {project_root})"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Доступ запрещён: файл находится вне проекта"
            )
    
    return resolved_path


def validate_directory_path(
    dir_path: str,
    project_root: Optional[Path] = None,
    project_path: Optional[str] = None
) -> Path:
    """Валидирует путь к директории и проверяет, что она находится в пределах проекта.
    
    Args:
        dir_path: Путь к директории для проверки
        project_root: Корень проекта (если уже вычислен)
        project_path: Путь к проекту (если нужно вычислить project_root)
        
    Returns:
        Resolved Path к директории
        
    Raises:
        HTTPException: Если путь находится вне проекта или некорректен
    """
    if not dir_path:
        raise HTTPException(status_code=400, detail="Путь к директории не указан")
    
    try:
        # Разрешаем путь (убираем .. и симлинки)
        resolved_path = Path(dir_path).resolve()
    except (ValueError, OSError) as e:
        logger.warning(f"⚠️ Некорректный путь: {dir_path}, ошибка: {e}")
        raise HTTPException(status_code=400, detail=f"Некорректный путь: {str(e)}")
    
    # Проверяем, что это директория
    if not resolved_path.is_dir():
        raise HTTPException(status_code=400, detail="Указанный путь не является директорией")
    
    # Получаем корень проекта
    if project_root is None:
        project_root = get_project_root(project_path)
    
    # Проверяем, что путь находится в пределах проекта
    try:
        # is_relative_to доступен в Python 3.9+
        if not resolved_path.is_relative_to(project_root):
            logger.warning(
                f"⚠️ Попытка доступа к директории вне проекта: {dir_path} "
                f"(проект: {project_root})"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Доступ запрещён: директория находится вне проекта"
            )
    except AttributeError:
        # Fallback для Python < 3.9
        try:
            resolved_path.relative_to(project_root)
        except ValueError:
            logger.warning(
                f"⚠️ Попытка доступа к директории вне проекта: {dir_path} "
                f"(проект: {project_root})"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Доступ запрещён: директория находится вне проекта"
            )
    
    return resolved_path
