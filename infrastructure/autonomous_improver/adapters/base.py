"""Базовый интерфейс для Language Adapters.

Адаптеры определяют, как анализировать код конкретного языка.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Any, Optional
import logging

logger = logging.getLogger("autonomous_improver")


class LanguageAdapter(ABC):
    """Базовый класс для адаптеров языков программирования.
    
    Каждый адаптер знает:
    - Какие файлы анализировать (расширения)
    - Как анализировать структуру кода
    - Как строить контекст для LLM
    - Как извлекать релевантные участки кода
    - Как формировать поисковые запросы
    - Как валидировать предложения
    """
    
    def _validate_file_path(self, file_path: Path) -> bool:
        """Валидирует путь к файлу перед анализом.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если файл валиден, False иначе
        """
        if not isinstance(file_path, Path):
            logger.warning(f"⚠️ Некорректный тип пути: {type(file_path)}")
            return False
        
        if not file_path.exists():
            logger.debug(f"⚠️ Файл не существует: {file_path}")
            return False
        
        if not file_path.is_file():
            logger.debug(f"⚠️ Путь не является файлом: {file_path}")
            return False
        
        # Проверяем права доступа (чтение)
        try:
            file_path.open('r').close()
        except PermissionError:
            logger.warning(f"⚠️ Нет прав на чтение файла: {file_path}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки доступа к файлу {file_path}: {e}")
            return False
        
        return True
    
    @property
    @abstractmethod
    def language(self) -> str:
        """Название языка (например, 'python', 'typescript')."""
        pass
    
    @property
    @abstractmethod
    def file_extensions(self) -> List[str]:
        """Список расширений файлов для анализа (например, ['.py'], ['.ts', '.tsx'])."""
        pass
    
    @abstractmethod
    def discover_files(self, project_path: Path) -> List[Path]:
        """Находит все файлы для анализа в проекте.
        
        Args:
            project_path: Путь к корню проекта
            
        Returns:
            Список путей к файлам для анализа
        """
        pass
    
    @abstractmethod
    def analyze_structure(self, file_path: Path) -> Optional[Any]:
        """Анализирует структуру файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Структурный анализ (зависит от языка) или None
        """
        # Валидация выполняется в конкретных реализациях
        pass
    
    @abstractmethod
    def build_context(self, file_path: Path, structure: Optional[Any]) -> str:
        """Строит контекст для LLM на основе структуры файла.
        
        Args:
            file_path: Путь к файлу
            structure: Результат analyze_structure()
            
        Returns:
            Текстовый контекст для LLM
        """
        pass
    
    @abstractmethod
    def extract_code_sample(
        self,
        file_path: Path,
        structure: Optional[Any],
        max_chars: int = 5000
    ) -> str:
        """Извлекает релевантный участок кода для анализа.
        
        Args:
            file_path: Путь к файлу
            structure: Результат analyze_structure()
            max_chars: Максимальное количество символов
            
        Returns:
            Участок кода для анализа
        """
        pass
    
    @abstractmethod
    def build_search_query(
        self,
        file_path: Path,
        structure: Optional[Any]
    ) -> str:
        """Формирует поисковый запрос для веб-поиска.
        
        Args:
            file_path: Путь к файлу
            structure: Результат analyze_structure()
            
        Returns:
            Поисковый запрос
        """
        pass
    
    @abstractmethod
    def validate_suggestion(self, suggestion: Any) -> bool:
        """Валидирует предложение по улучшению.
        
        Args:
            suggestion: Предложение для валидации
            
        Returns:
            True если предложение валидно
        """
        pass
