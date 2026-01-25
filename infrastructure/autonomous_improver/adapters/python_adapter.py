"""Python Language Adapter - анализ Python кода."""
from pathlib import Path
from typing import List, Optional, Any

from infrastructure.ast_analyzer import ASTAnalyzer, FileAnalysis
from utils.logger import get_logger
from .base import LanguageAdapter

logger = get_logger()


class PythonAdapter(LanguageAdapter):
    """Адаптер для анализа Python кода.
    
    Использует AST анализатор для структурного анализа.
    """
    
    @property
    def language(self) -> str:
        return "python"
    
    @property
    def file_extensions(self) -> List[str]:
        return [".py"]
    
    def __init__(self):
        """Инициализирует Python адаптер."""
        self.ast_analyzer = ASTAnalyzer()
    
    def discover_files(self, project_path: Path) -> List[Path]:
        """Находит все Python файлы в проекте."""
        python_files = list(project_path.rglob("*.py"))
        return python_files
    
    def analyze_structure(self, file_path: Path) -> Optional[FileAnalysis]:
        """Анализирует структуру Python файла через AST."""
        # Валидация файла
        if not self._validate_file_path(file_path):
            return None
        
        if file_path.suffix != ".py":
            return None
        
        try:
            return self.ast_analyzer.analyze_file(file_path)
        except Exception as e:
            logger.debug(f"⚠️ Ошибка AST анализа файла {file_path}: {e}")
            return None
    
    def build_context(self, file_path: Path, structure: Optional[FileAnalysis]) -> str:
        """Строит контекст для LLM на основе AST анализа."""
        if not structure:
            return f"Файл: {file_path.name}\n"
        
        context_parts = [
            f"Файл: {file_path.name}",
            f"Путь: {file_path}",
            f"Строк кода: {structure.metrics.lines_of_code}",
            f"Функций: {len(structure.functions)}",
            f"Классов: {len(structure.classes)}",
            f"Максимальная сложность: {structure.metrics.max_function_complexity}",
        ]
        
        # Добавляем информацию о функциях с высокой сложностью
        complex_functions = [
            f for f in structure.functions
            if f.complexity > 10
        ]
        if complex_functions:
            context_parts.append(f"\nФункции с высокой сложностью (>10):")
            for func in complex_functions[:5]:  # Максимум 5
                context_parts.append(f"  - {func.name} (сложность: {func.complexity})")
        
        # Добавляем информацию об отсутствии docstrings
        functions_without_docs = [
            f for f in structure.functions
            if not f.docstring
        ]
        if functions_without_docs:
            context_parts.append(f"\nФункций без docstrings: {len(functions_without_docs)}")
        
        return "\n".join(context_parts)
    
    def extract_code_sample(
        self,
        file_path: Path,
        structure: Optional[FileAnalysis],
        max_chars: int = 5000
    ) -> str:
        """Извлекает релевантный участок кода для анализа.
        
        Стратегия:
        1. Начало файла (импорты, константы)
        2. Конец файла (основная логика)
        3. Функции с высокой сложностью
        """
        try:
            code = file_path.read_text(encoding="utf-8")
        except Exception:
            return ""
        
        # Если файл небольшой, возвращаем весь
        if len(code) <= max_chars:
            return code
        
        # Собираем важные участки
        samples = []
        remaining_chars = max_chars
        
        # 1. Начало файла (первые 1000 символов)
        start_sample = code[:min(1000, remaining_chars)]
        samples.append(start_sample)
        remaining_chars -= len(start_sample)
        
        # 2. Функции с высокой сложностью (если есть структура)
        if structure:
            complex_functions = sorted(
                [f for f in structure.functions if f.complexity > 10],
                key=lambda x: x.complexity,
                reverse=True
            )
            
            for func in complex_functions[:3]:  # Максимум 3 функции
                if remaining_chars <= 0:
                    break
                
                # Извлекаем функцию из кода
                func_code = self._extract_function_code(code, func)
                if func_code and len(func_code) <= remaining_chars:
                    samples.append(f"\n# Функция {func.name} (сложность: {func.complexity})\n{func_code}")
                    remaining_chars -= len(func_code) + 50  # +50 за комментарий
        
        # 3. Конец файла (последние N символов)
        if remaining_chars > 0:
            end_sample = code[-min(remaining_chars, 1000):]
            samples.append(f"\n# ... (конец файла)\n{end_sample}")
        
        return "\n".join(samples)
    
    def _extract_function_code(self, code: str, func_info: Any) -> Optional[str]:
        """Извлекает код функции из файла.
        
        Args:
            code: Весь код файла
            func_info: Информация о функции из AST
            
        Returns:
            Код функции или None
        """
        # Простая реализация - ищем функцию по имени
        # В реальности можно использовать line numbers из AST
        lines = code.split('\n')
        func_name = func_info.name
        
        # Ищем определение функции
        for i, line in enumerate(lines):
            if f"def {func_name}(" in line or f"async def {func_name}(" in line:
                # Находим конец функции (следующая функция или конец файла)
                start_idx = i
                end_idx = len(lines)
                
                # Ищем следующую функцию на том же уровне вложенности
                indent_level = len(line) - len(line.lstrip())
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() and not lines[j].startswith(' ' * (indent_level + 1)):
                        # Проверяем, не начало ли это новой функции/класса
                        if lines[j].strip().startswith(('def ', 'class ', 'async def ')):
                            end_idx = j
                            break
                
                return '\n'.join(lines[start_idx:end_idx])
        
        return None
    
    def build_search_query(
        self,
        file_path: Path,
        structure: Optional[FileAnalysis]
    ) -> str:
        """Формирует поисковый запрос для веб-поиска."""
        query_parts = []
        
        # Базовый запрос на основе имени файла
        file_name = file_path.stem
        query_parts.append(f"python {file_name}")
        
        # Добавляем информацию из AST анализа
        if structure:
            if len(structure.functions) > 10:
                query_parts.append("refactoring large functions")
            if structure.metrics.max_function_complexity > 10:
                query_parts.append("reducing code complexity")
            if len(structure.classes) > 5:
                query_parts.append("python class design patterns")
        
        # Формируем финальный запрос
        query = " ".join(query_parts[:3])  # Максимум 3 части
        return query
    
    def validate_suggestion(self, suggestion: Any) -> bool:
        """Валидирует предложение по улучшению Python кода."""
        # Базовая валидация - проверяем наличие обязательных полей
        if not hasattr(suggestion, 'description') or not suggestion.description:
            return False
        
        if not hasattr(suggestion, 'suggestion') or not suggestion.suggestion:
            return False
        
        # Минимальная длина описания и предложения
        if len(suggestion.description) < 10:
            return False
        
        if len(suggestion.suggestion) < 20:
            return False
        
        return True
