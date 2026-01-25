"""Language Adapters для анализа разных языков программирования."""

from .base import LanguageAdapter
from .python_adapter import PythonAdapter
from .frontend_adapter import FrontendAdapter
from .multi_adapter import MultiAdapter

__all__ = [
    'LanguageAdapter',
    'PythonAdapter',
    'FrontendAdapter',
    'MultiAdapter'
]
