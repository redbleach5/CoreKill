"""Multi Adapter - поддержка нескольких языков одновременно.

Для mixed проектов (Python + TypeScript).
"""
from pathlib import Path
from typing import List, Optional, Any

from .base import LanguageAdapter
from .python_adapter import PythonAdapter
from .frontend_adapter import FrontendAdapter


class MultiAdapter(LanguageAdapter):
    """Адаптер для анализа нескольких языков одновременно.
    
    Используется для mixed проектов (например, Python + TypeScript).
    """
    
    @property
    def language(self) -> str:
        return "mixed"
    
    @property
    def file_extensions(self) -> List[str]:
        """Все расширения из всех адаптеров."""
        extensions = []
        for adapter in self.adapters:
            extensions.extend(adapter.file_extensions)
        return list(set(extensions))  # Убираем дубликаты
    
    def __init__(self, adapters: List[LanguageAdapter]):
        """Инициализирует MultiAdapter.
        
        Args:
            adapters: Список адаптеров для использования
        """
        self.adapters = adapters
    
    def discover_files(self, project_path: Path) -> List[Path]:
        """Находит файлы всех поддерживаемых языков."""
        all_files = []
        for adapter in self.adapters:
            all_files.extend(adapter.discover_files(project_path))
        # Убираем дубликаты
        return list(set(all_files))
    
    def analyze_structure(self, file_path: Path) -> Optional[Any]:
        """Анализирует структуру файла через подходящий адаптер."""
        # Валидация файла
        if not self._validate_file_path(file_path):
            return None
        
        # Определяем, какой адаптер использовать по расширению
        adapter = self._get_adapter_for_file(file_path)
        if adapter:
            return adapter.analyze_structure(file_path)
        return None
    
    def build_context(self, file_path: Path, structure: Optional[Any]) -> str:
        """Строит контекст через подходящий адаптер."""
        adapter = self._get_adapter_for_file(file_path)
        if adapter:
            return adapter.build_context(file_path, structure)
        return f"Файл: {file_path.name}\n"
    
    def extract_code_sample(
        self,
        file_path: Path,
        structure: Optional[Any],
        max_chars: int = 5000
    ) -> str:
        """Извлекает код через подходящий адаптер."""
        adapter = self._get_adapter_for_file(file_path)
        if adapter:
            return adapter.extract_code_sample(file_path, structure, max_chars)
        return ""
    
    def build_search_query(
        self,
        file_path: Path,
        structure: Optional[Any]
    ) -> str:
        """Формирует запрос через подходящий адаптер."""
        adapter = self._get_adapter_for_file(file_path)
        if adapter:
            return adapter.build_search_query(file_path, structure)
        return f"{file_path.suffix} best practices"
    
    def validate_suggestion(self, suggestion: Any) -> bool:
        """Валидирует через подходящий адаптер."""
        # Используем первый адаптер для валидации (базовая валидация)
        if self.adapters:
            return self.adapters[0].validate_suggestion(suggestion)
        return True
    
    def _get_adapter_for_file(self, file_path: Path) -> Optional[LanguageAdapter]:
        """Определяет подходящий адаптер для файла."""
        ext = file_path.suffix.lower()
        for adapter in self.adapters:
            if ext in adapter.file_extensions:
                return adapter
        return None
