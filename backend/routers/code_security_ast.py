"""AST-based security validation for code execution.

Использует AST парсинг для более надежной проверки безопасности кода.
Это улучшенная версия, которая не может быть обойдена простыми строковыми трюками.
"""
import ast
from typing import List, Tuple, Set
from utils.logger import get_logger

logger = get_logger()


class ASTSecurityValidator:
    """Валидатор безопасности кода на основе AST парсинга.
    
    Проверяет код на опасные операции через анализ AST дерева,
    что делает обход проверок значительно сложнее.
    """
    
    # Запрещенные модули для импорта
    FORBIDDEN_MODULES: Set[str] = {
        'os', 'subprocess', 'sys', 'socket', 'requests', 'urllib',
        'ctypes', 'importlib', 'pickle', 'marshal', 'shelve',
        'multiprocessing', 'threading', 'signal', 'fcntl'
    }
    
    # Запрещенные функции
    FORBIDDEN_FUNCTIONS: Set[str] = {
        '__import__', 'eval', 'exec', 'compile', 'open', 'file',
        'input', 'raw_input', 'globals', 'locals', 'vars', 'dir',
        'getattr', 'setattr', 'delattr', 'hasattr', 'callable',
        'type', 'isinstance', 'issubclass', '__builtins__'
    }
    
    # Запрещенные атрибуты
    FORBIDDEN_ATTRIBUTES: Set[str] = {
        '__loader__', '__spec__', '__code__', '__globals__',
        '__dict__', '__class__', '__bases__', '__mro__'
    }
    
    def validate(self, code: str) -> Tuple[bool, List[str]]:
        """Валидирует код на безопасность через AST парсинг.
        
        Args:
            code: Код для валидации
            
        Returns:
            Кортеж (безопасен: bool, список ошибок: List[str])
        """
        errors: List[str] = []
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, [f"Синтаксическая ошибка: {e.msg} на строке {e.lineno}"]
        except Exception as e:
            logger.debug(f"⚠️ Ошибка парсинга кода через AST: {e}")
            return False, [f"Ошибка парсинга кода: {e}"]
        
        # Обходим AST дерево и проверяем узлы
        visitor = SecurityASTVisitor(self.FORBIDDEN_MODULES, self.FORBIDDEN_FUNCTIONS, self.FORBIDDEN_ATTRIBUTES)
        visitor.visit(tree)
        
        if visitor.errors:
            return False, visitor.errors
        
        return True, []
    
    def check_imports(self, code: str) -> Tuple[bool, List[str]]:
        """Проверяет только импорты в коде.
        
        Args:
            code: Код для проверки
            
        Returns:
            Кортеж (безопасен: bool, список ошибок: List[str])
        """
        errors: List[str] = []
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Если синтаксис неверный, это не наша проблема
            return True, []
        
        visitor = ImportASTVisitor(self.FORBIDDEN_MODULES)
        visitor.visit(tree)
        
        if visitor.errors:
            return False, visitor.errors
        
        return True, []


class SecurityASTVisitor(ast.NodeVisitor):
    """AST visitor для проверки безопасности кода."""
    
    def __init__(self, forbidden_modules: Set[str], forbidden_functions: Set[str], forbidden_attributes: Set[str]):
        self.forbidden_modules = forbidden_modules
        self.forbidden_functions = forbidden_functions
        self.forbidden_attributes = forbidden_attributes
        self.errors: List[str] = []
    
    def visit_Import(self, node: ast.Import) -> None:
        """Проверяет обычные импорты (import os)."""
        for alias in node.names:
            module_name = alias.name.split('.')[0]  # Берем только корневой модуль
            if module_name in self.forbidden_modules:
                self.errors.append(f"Запрещенный импорт: {module_name}")
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Проверяет импорты из модулей (from os import ...)."""
        if node.module:
            module_name = node.module.split('.')[0]  # Берем только корневой модуль
            if module_name in self.forbidden_modules:
                self.errors.append(f"Запрещенный импорт из модуля: {module_name}")
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call) -> None:
        """Проверяет вызовы функций."""
        # Проверяем прямые вызовы функций (eval(), exec(), etc.)
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.forbidden_functions:
                self.errors.append(f"Запрещенный вызов функции: {func_name}()")
        
        # Проверяем вызовы через атрибуты (os.system(), subprocess.run(), etc.)
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                attr_name = node.func.attr
                if module_name in self.forbidden_modules:
                    self.errors.append(f"Запрещенный вызов: {module_name}.{attr_name}()")
        
        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Проверяет доступ к опасным атрибутам."""
        if node.attr in self.forbidden_attributes:
            self.errors.append(f"Запрещенный доступ к атрибуту: {node.attr}")
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name) -> None:
        """Проверяет использование опасных имен (__builtins__, etc.)."""
        if node.id in self.forbidden_functions and isinstance(node.ctx, ast.Load):
            # Проверяем контекст - только если это загрузка (не присваивание)
            # Но это может быть ложное срабатывание, поэтому проверяем осторожно
            pass  # Уже проверяем в visit_Call
        self.generic_visit(node)


class ImportASTVisitor(ast.NodeVisitor):
    """AST visitor только для проверки импортов."""
    
    def __init__(self, forbidden_modules: Set[str]):
        self.forbidden_modules = forbidden_modules
        self.errors: List[str] = []
    
    def visit_Import(self, node: ast.Import) -> None:
        """Проверяет обычные импорты."""
        for alias in node.names:
            module_name = alias.name.split('.')[0]
            if module_name in self.forbidden_modules:
                self.errors.append(f"Запрещенный импорт: {module_name}")
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Проверяет импорты из модулей."""
        if node.module:
            module_name = node.module.split('.')[0]
            if module_name in self.forbidden_modules:
                self.errors.append(f"Запрещенный импорт из модуля: {module_name}")
        self.generic_visit(node)
