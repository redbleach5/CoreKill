"""Проверка безопасности сгенерированного кода.

Проверяет код на опасные операции перед сохранением в историю или выполнением.
"""
from typing import List, Tuple, Optional
from utils.logger import get_logger
from utils.config import get_config

logger = get_logger()


class CodeSecurityChecker:
    """Проверяет код на опасные операции.
    
    Использует паттерны для обнаружения потенциально опасного кода:
    - Опасные импорты (os, subprocess, etc.)
    - Опасные функции (eval, exec, etc.)
    - Опасные системные вызовы
    """
    
    def __init__(self) -> None:
        """Инициализация проверщика."""
        self.config = get_config()
        self._load_security_config()
        self._init_dangerous_patterns()
    
    def _load_security_config(self) -> None:
        """Загружает конфигурацию безопасности из config.toml."""
        try:
            security_config = self.config._config_data.get("code_security", {})
            self.enabled = security_config.get("enabled", True)
            self.strict_mode = security_config.get("strict_mode", False)
            self.block_dangerous_imports = security_config.get("block_dangerous_imports", True)
            self.block_dangerous_functions = security_config.get("block_dangerous_functions", True)
            self.block_system_calls = security_config.get("block_system_calls", True)
        except Exception as e:
            logger.warning(f"Ошибка загрузки code_security конфигурации: {e}, используем значения по умолчанию")
            self.enabled = True
            self.strict_mode = False
            self.block_dangerous_imports = True
            self.block_dangerous_functions = True
            self.block_system_calls = True
    
    def _init_dangerous_patterns(self) -> None:
        """Инициализирует паттерны опасного кода."""
        # Опасные импорты
        self.dangerous_imports = [
            'import os',
            'import subprocess',
            'import sys',
            'import socket',
            'import requests',
            'import urllib',
            'import ctypes',
            'import importlib',
            'from os',
            'from subprocess',
            'from sys',
            'from socket',
            'from ctypes',
            'from importlib',
        ]
        
        # Опасные функции и методы
        self.dangerous_functions = [
            '__import__',
            'eval(',
            'exec(',
            'compile(',
            'open(',
            'file(',
            'input(',
            'raw_input(',
            'globals(',
            'locals(',
            'vars(',
            'dir(',
            'getattr(',
            'setattr(',
            'delattr(',
            'hasattr(',
            '__builtins__',
            '__loader__',
            '__spec__',
            '__code__',
            '__globals__',
            '__dict__',
        ]
        
        # Опасные системные команды
        self.dangerous_system_calls = [
            'os.system',
            'os.popen',
            'os.execv',
            'os.spawn',
            'subprocess.run',
            'subprocess.call',
            'subprocess.popen',
            'subprocess.check_output',
            'subprocess.check_call',
        ]
    
    def check_code(self, code: str) -> Tuple[bool, List[str]]:
        """Проверяет код на опасные операции.
        
        Args:
            code: Код для проверки
            
        Returns:
            Кортеж (безопасен: bool, список предупреждений: List[str])
        """
        if not self.enabled:
            return True, []
        
        warnings: List[str] = []
        code_lower = code.lower()
        
        # Проверка опасных импортов
        if self.block_dangerous_imports:
            for pattern in self.dangerous_imports:
                if pattern.lower() in code_lower:
                    warning = f"Обнаружен опасный импорт: {pattern}"
                    warnings.append(warning)
                    if self.strict_mode:
                        logger.warning(f"❌ {warning}")
                        return False, warnings
        
        # Проверка опасных функций
        if self.block_dangerous_functions:
            for pattern in self.dangerous_functions:
                if pattern.lower() in code_lower:
                    warning = f"Обнаружена опасная функция: {pattern}"
                    warnings.append(warning)
                    if self.strict_mode:
                        logger.warning(f"❌ {warning}")
                        return False, warnings
        
        # Проверка опасных системных вызовов
        if self.block_system_calls:
            for pattern in self.dangerous_system_calls:
                if pattern.lower() in code_lower:
                    warning = f"Обнаружен опасный системный вызов: {pattern}"
                    warnings.append(warning)
                    if self.strict_mode:
                        logger.warning(f"❌ {warning}")
                        return False, warnings
        
        if warnings:
            logger.info(f"⚠️ Обнаружено {len(warnings)} предупреждений безопасности (не строгий режим)")
        
        return True, warnings
    
    def is_safe_for_history(self, code: str) -> bool:
        """Проверяет, безопасен ли код для сохранения в историю.
        
        Args:
            code: Код для проверки
            
        Returns:
            True если код безопасен для сохранения
        """
        is_safe, warnings = self.check_code(code)
        
        if warnings and self.strict_mode:
            logger.warning(f"❌ Код не безопасен для сохранения в историю: {warnings[0]}")
            return False
        
        return is_safe


# === Удобная функция для импорта ===

def get_code_security_checker() -> CodeSecurityChecker:
    """Возвращает экземпляр CodeSecurityChecker.
    
    Returns:
        Экземпляр CodeSecurityChecker
    """
    return CodeSecurityChecker()
