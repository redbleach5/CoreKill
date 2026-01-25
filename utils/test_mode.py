"""Утилита для определения тестового режима.

Помогает production коду определить, запущен ли он в тестах,
чтобы избежать проблем с Mock объектами и тестовыми данными.
"""
import sys
import os


def is_test_mode() -> bool:
    """Проверяет, запущен ли код в тестовом режиме.
    
    Определяет тестовый режим по:
    1. Наличию pytest или unittest в sys.modules
    2. Переменной окружения TESTING
    3. Наличию pytest в sys.argv
    
    Returns:
        True если код запущен в тестах, False иначе
    """
    # Проверяем наличие pytest/unittest в модулях
    if 'pytest' in sys.modules or 'unittest' in sys.modules:
        return True
    
    # Проверяем переменную окружения
    if os.getenv('TESTING', '').lower() in ('true', '1', 'yes'):
        return True
    
    # Проверяем sys.argv на наличие pytest
    if any('pytest' in arg or 'test' in arg.lower() for arg in sys.argv):
        # Но только если это не просто импорт модуля
        if len(sys.argv) > 0 and 'pytest' in sys.argv[0]:
            return True
    
    return False


def is_production_mode() -> bool:
    """Проверяет, запущен ли код в production режиме.
    
    Returns:
        True если production, False иначе
    """
    return not is_test_mode()
