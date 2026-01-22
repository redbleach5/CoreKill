"""Конфигурация стиля кода для генерации.

Поддерживает разные стили docstrings (Google, NumPy, Sphinx) и правила форматирования.
"""
from enum import Enum
from typing import Optional
from utils.config import get_config
from utils.logger import get_logger

logger = get_logger()


class DocstringStyle(Enum):
    """Стили docstrings."""
    GOOGLE = "google"  # Google style docstrings
    NUMPY = "numpy"  # NumPy style docstrings
    SPHINX = "sphinx"  # Sphinx style docstrings
    RUSSIAN = "russian"  # Русские docstrings (по умолчанию)


class CodeStyleConfig:
    """Конфигурация стиля кода для генерации.
    
    Читает настройки из config.toml и предоставляет типизированный доступ.
    """
    
    _instance: Optional['CodeStyleConfig'] = None
    
    def __new__(cls) -> 'CodeStyleConfig':
        """Singleton паттерн."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = get_config()
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self) -> None:
        """Загружает конфигурацию из config.toml."""
        try:
            style_config = self._config._config_data.get("code_style", {})
            
            # Стиль docstrings
            docstring_style_str = style_config.get("docstring_style", "russian")
            try:
                self.docstring_style = DocstringStyle(docstring_style_str.lower())
            except ValueError:
                logger.warning(f"Неизвестный стиль docstrings: {docstring_style_str}, используем russian")
                self.docstring_style = DocstringStyle.RUSSIAN
            
            # Язык docstrings
            self.docstring_language = style_config.get("docstring_language", "ru")
            
            # Именование
            self.naming_style = style_config.get("naming_style", "snake_case")  # snake_case, camelCase, PascalCase
            
            # Дополнительные правила
            self.require_type_hints = style_config.get("require_type_hints", True)
            self.require_docstrings = style_config.get("require_docstrings", True)
            self.follow_pep8 = style_config.get("follow_pep8", True)
            self.max_line_length = style_config.get("max_line_length", 88)  # Black default
            
        except Exception as e:
            logger.warning(f"Ошибка загрузки code_style конфигурации: {e}, используем значения по умолчанию")
            self.docstring_style = DocstringStyle.RUSSIAN
            self.docstring_language = "ru"
            self.naming_style = "snake_case"
            self.require_type_hints = True
            self.require_docstrings = True
            self.follow_pep8 = True
            self.max_line_length = 88
    
    def get_docstring_template(self) -> str:
        """Возвращает шаблон docstring для промпта.
        
        Returns:
            Строка с примером docstring в выбранном стиле
        """
        if self.docstring_style == DocstringStyle.GOOGLE:
            if self.docstring_language == "ru":
                return '''"""Краткое описание функции.

Args:
    param: Описание параметра.

Returns:
    Описание возвращаемого значения.

Raises:
    ValueError: Когда возникает ошибка.
"""'''
            else:
                return '''"""Brief description of function.

Args:
    param: Parameter description.

Returns:
    Return value description.

Raises:
    ValueError: When error occurs.
"""'''
        
        elif self.docstring_style == DocstringStyle.NUMPY:
            if self.docstring_language == "ru":
                return '''"""Краткое описание функции.

Parameters
----------
param : type
    Описание параметра.

Returns
-------
type
    Описание возвращаемого значения.

Raises
------
ValueError
    Когда возникает ошибка.
"""'''
            else:
                return '''"""Brief description of function.

Parameters
----------
param : type
    Parameter description.

Returns
-------
type
    Return value description.

Raises
------
ValueError
    When error occurs.
"""'''
        
        elif self.docstring_style == DocstringStyle.SPHINX:
            if self.docstring_language == "ru":
                return '''"""Краткое описание функции.

:param param: Описание параметра.
:type param: type
:returns: Описание возвращаемого значения.
:rtype: type
:raises ValueError: Когда возникает ошибка.
"""'''
            else:
                return '''"""Brief description of function.

:param param: Parameter description.
:type param: type
:returns: Return value description.
:rtype: type
:raises ValueError: When error occurs.
"""'''
        
        else:  # RUSSIAN (default)
            return '''"""Описание функции.

Args:
    param: Описание параметра.

Returns:
    Описание возвращаемого значения.
"""'''
    
    def get_style_requirements(self) -> str:
        """Возвращает требования к стилю для промпта.
        
        Returns:
            Строка с требованиями к стилю кода
        """
        requirements = []
        
        # Type hints
        if self.require_type_hints:
            requirements.append("Используй type hints для всех функций и методов")
        
        # Docstrings
        if self.require_docstrings:
            docstring_instruction = f"Добавь docstrings ({self.docstring_style.value} style)"
            if self.docstring_language == "ru":
                docstring_instruction += " на русском языке"
            else:
                docstring_instruction += " in English"
            docstring_instruction += f" для всех публичных функций/классов/методов"
            requirements.append(docstring_instruction)
            requirements.append(f"Формат docstring:\n{self.get_docstring_template()}")
        
        # PEP8
        if self.follow_pep8:
            requirements.append("Следуй PEP8 и лучшим практикам Python")
            requirements.append(f"Максимальная длина строки: {self.max_line_length} символов")
        
        # Naming
        if self.naming_style == "snake_case":
            requirements.append("Используй понятные имена переменных (snake_case)")
        elif self.naming_style == "camelCase":
            requirements.append("Используй camelCase для переменных и функций")
        elif self.naming_style == "PascalCase":
            requirements.append("Используй PascalCase для классов, camelCase для функций")
        
        return "\n".join(f"{i+1}. {req}" for i, req in enumerate(requirements))
    
    def reload(self) -> None:
        """Перезагружает конфигурацию."""
        self._config.reload()
        self._load_config()


# === Удобная функция для импорта ===

def get_code_style_config() -> CodeStyleConfig:
    """Возвращает экземпляр CodeStyleConfig.
    
    Returns:
        Singleton экземпляр CodeStyleConfig
    """
    return CodeStyleConfig()
