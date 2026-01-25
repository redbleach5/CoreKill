"""Frontend Language Adapter - анализ JS/TS/TSX/HTML/MD/JSON кода."""
from pathlib import Path
from typing import List, Optional, Any, Dict
import re
import json
import logging

from .base import LanguageAdapter

logger = logging.getLogger("autonomous_improver")


class FrontendStructure:
    """Структурный анализ фронтенд-файла."""
    def __init__(self):
        self.file_type: str = ""  # "typescript", "javascript", "html", "markdown", "json"
        self.components: List[str] = []  # Имена компонентов
        self.hooks: List[str] = []  # React hooks
        self.imports: List[str] = []  # Импорты
        self.exports: List[str] = []  # Экспорты
        self.functions: List[Dict[str, Any]] = []  # Функции с метаданными
        self.lines_of_code: int = 0
        self.has_types: bool = False  # TypeScript типы
        self.accessibility_issues: List[str] = []  # Проблемы доступности
        self.metadata: Dict[str, Any] = {}  # Дополнительные метаданные


class FrontendAdapter:
    """Адаптер для анализа фронтенд-кода (JS/TS/TSX/HTML/MD/JSON).
    
    Поддерживает:
    - TypeScript/JavaScript (.ts, .tsx, .js, .jsx)
    - HTML (.html)
    - Markdown (.md)
    - JSON (.json)
    """
    
    @property
    def language(self) -> str:
        return "frontend"
    
    @property
    def file_extensions(self) -> List[str]:
        return [".ts", ".tsx", ".js", ".jsx", ".html", ".md", ".json"]
    
    def discover_files(self, project_path: Path) -> List[Path]:
        """Находит все фронтенд-файлы в проекте."""
        frontend_files = []
        
        for ext in self.file_extensions:
            frontend_files.extend(project_path.rglob(f"*{ext}"))
        
        return frontend_files
    
    def analyze_structure(self, file_path: Path) -> Optional[FrontendStructure]:
        """Анализирует структуру фронтенд-файла."""
        structure = FrontendStructure()
        
        try:
            content = file_path.read_text(encoding="utf-8")
            structure.lines_of_code = len(content.splitlines())
        except Exception:
            return None
        
        # Определяем тип файла
        ext = file_path.suffix.lower()
        if ext in [".ts", ".tsx"]:
            structure.file_type = "typescript"
            structure.has_types = True
            self._analyze_typescript(content, structure)
        elif ext in [".js", ".jsx"]:
            structure.file_type = "javascript"
            self._analyze_javascript(content, structure)
        elif ext == ".html":
            structure.file_type = "html"
            self._analyze_html(content, structure)
        elif ext == ".md":
            structure.file_type = "markdown"
            self._analyze_markdown(content, structure)
        elif ext == ".json":
            structure.file_type = "json"
            self._analyze_json(content, structure)
        
        return structure
    
    def _analyze_typescript(self, content: str, structure: FrontendStructure):
        """Анализирует TypeScript/TSX код."""
        # Ищем компоненты React
        component_pattern = r'(?:export\s+)?(?:default\s+)?(?:function|const)\s+(\w+)\s*[:=]\s*(?:React\.)?(?:FC|FunctionComponent|Component)'
        components = re.findall(component_pattern, content, re.IGNORECASE)
        structure.components.extend(components)
        
        # Ищем хуки
        hook_pattern = r'use\w+\s*\('
        hooks = re.findall(hook_pattern, content)
        structure.hooks = list(set(hooks))
        
        # Ищем импорты
        import_pattern = r'import\s+(?:.*\s+from\s+)?["\']([^"\']+)["\']'
        imports = re.findall(import_pattern, content)
        structure.imports.extend(imports)
        
        # Ищем функции
        function_pattern = r'(?:export\s+)?(?:async\s+)?(?:function|const)\s+(\w+)\s*[=:]?\s*(?:\(|=>)'
        functions = re.findall(function_pattern, content)
        for func_name in functions:
            structure.functions.append({
                "name": func_name,
                "type": "function"
            })
        
        # Проверяем использование типов
        if re.search(r':\s*\w+', content):
            structure.has_types = True
        
        # Проверяем accessibility
        self._check_accessibility(content, structure)
    
    def _analyze_javascript(self, content: str, structure: FrontendStructure):
        """Анализирует JavaScript/JSX код."""
        # Аналогично TypeScript, но без проверки типов
        self._analyze_typescript(content, structure)
        structure.has_types = False
    
    def _analyze_html(self, content: str, structure: FrontendStructure):
        """Анализирует HTML код."""
        # Проверяем семантическую разметку
        semantic_tags = ['header', 'nav', 'main', 'article', 'section', 'aside', 'footer']
        found_semantic = [tag for tag in semantic_tags if f'<{tag}' in content.lower()]
        structure.metadata['semantic_tags'] = found_semantic
        
        # Проверяем accessibility
        self._check_accessibility_html(content, structure)
        
        # Проверяем наличие мета-тегов
        has_meta = '<meta' in content.lower()
        structure.metadata['has_meta_tags'] = has_meta
    
    def _analyze_markdown(self, content: str, structure: FrontendStructure):
        """Анализирует Markdown документацию."""
        # Проверяем структуру
        has_headers = bool(re.search(r'^#+\s+', content, re.MULTILINE))
        has_links = bool(re.search(r'\[.*?\]\(.*?\)', content))
        has_code_blocks = '```' in content
        
        structure.metadata = {
            'has_headers': has_headers,
            'has_links': has_links,
            'has_code_blocks': has_code_blocks,
            'header_count': len(re.findall(r'^#+\s+', content, re.MULTILINE))
        }
    
    def _analyze_json(self, content: str, structure: FrontendStructure):
        """Анализирует JSON файлы."""
        try:
            data = json.loads(content)
            structure.metadata = {
                'is_valid': True,
                'type': type(data).__name__,
                'keys': list(data.keys()) if isinstance(data, dict) else None
            }
        except json.JSONDecodeError:
            structure.metadata = {
                'is_valid': False,
                'error': 'Invalid JSON'
            }
    
    def _check_accessibility(self, content: str, structure: FrontendStructure):
        """Проверяет проблемы доступности в React/TSX коде."""
        issues = []
        
        # Проверяем наличие alt у изображений
        if re.search(r'<img[^>]*(?!alt=)', content):
            issues.append("Images without alt attribute")
        
        # Проверяем aria-* атрибуты
        if re.search(r'<button[^>]*(?!aria-)', content) and 'onClick' in content:
            # Кнопки без aria-label могут быть проблемой
            pass
        
        # Проверяем семантические теги
        if not re.search(r'<(header|nav|main|article|section|aside|footer)', content, re.IGNORECASE):
            if '<div' in content and len(re.findall(r'<div', content)) > 5:
                issues.append("Many divs without semantic tags")
        
        structure.accessibility_issues = issues
    
    def _check_accessibility_html(self, content: str, structure: FrontendStructure):
        """Проверяет проблемы доступности в HTML."""
        issues = []
        
        # Проверяем alt у изображений
        img_pattern = r'<img[^>]*>'
        for img in re.finditer(img_pattern, content, re.IGNORECASE):
            if 'alt=' not in img.group(0).lower():
                issues.append("Image without alt attribute")
        
        # Проверяем семантическую разметку
        if '<div' in content and not re.search(r'<(header|nav|main|article|section)', content, re.IGNORECASE):
            issues.append("Missing semantic HTML tags")
        
        structure.accessibility_issues = issues
    
    def build_context(self, file_path: Path, structure: Optional[FrontendStructure]) -> str:
        """Строит контекст для LLM на основе структурного анализа."""
        if not structure:
            return f"Файл: {file_path.name}\n"
        
        context_parts = [
            f"Файл: {file_path.name}",
            f"Тип: {structure.file_type}",
            f"Строк кода: {structure.lines_of_code}",
        ]
        
        if structure.file_type in ["typescript", "javascript"]:
            if structure.components:
                context_parts.append(f"Компонентов: {len(structure.components)}")
                context_parts.append(f"  {', '.join(structure.components[:5])}")
            
            if structure.hooks:
                context_parts.append(f"Hooks: {len(structure.hooks)}")
            
            if structure.functions:
                context_parts.append(f"Функций: {len(structure.functions)}")
            
            if structure.has_types:
                context_parts.append("TypeScript: используется типизация")
            else:
                context_parts.append("TypeScript: типизация отсутствует или неполная")
            
            if structure.accessibility_issues:
                context_parts.append(f"Проблемы доступности: {len(structure.accessibility_issues)}")
        
        elif structure.file_type == "html":
            if structure.metadata.get('semantic_tags'):
                context_parts.append(f"Семантические теги: {', '.join(structure.metadata['semantic_tags'])}")
            
            if structure.accessibility_issues:
                context_parts.append(f"Проблемы доступности: {len(structure.accessibility_issues)}")
        
        elif structure.file_type == "markdown":
            if structure.metadata.get('header_count', 0) > 0:
                context_parts.append(f"Заголовков: {structure.metadata['header_count']}")
            if structure.metadata.get('has_code_blocks'):
                context_parts.append("Содержит примеры кода")
        
        elif structure.file_type == "json":
            if structure.metadata.get('is_valid'):
                context_parts.append(f"Валидный JSON, тип: {structure.metadata.get('type')}")
            else:
                context_parts.append("Невалидный JSON")
        
        return "\n".join(context_parts)
    
    def extract_code_sample(
        self,
        file_path: Path,
        structure: Optional[FrontendStructure],
        max_chars: int = 5000
    ) -> str:
        """Извлекает релевантный участок кода для анализа."""
        try:
            code = file_path.read_text(encoding="utf-8")
        except Exception:
            return ""
        
        # Если файл небольшой, возвращаем весь
        if len(code) <= max_chars:
            return code
        
        # Для больших файлов берём начало и конец
        samples = []
        remaining_chars = max_chars
        
        # Начало файла (импорты, определения)
        start_sample = code[:min(2000, remaining_chars)]
        samples.append(start_sample)
        remaining_chars -= len(start_sample)
        
        # Конец файла (основная логика)
        if remaining_chars > 0:
            end_sample = code[-min(remaining_chars, 2000):]
            samples.append(f"\n// ... (конец файла)\n{end_sample}")
        
        return "\n".join(samples)
    
    def build_search_query(
        self,
        file_path: Path,
        structure: Optional[FrontendStructure]
    ) -> str:
        """Формирует поисковый запрос для веб-поиска."""
        query_parts = []
        
        # Базовый запрос на основе типа файла
        if structure:
            if structure.file_type == "typescript":
                query_parts.append("typescript best practices")
            elif structure.file_type == "javascript":
                query_parts.append("javascript best practices")
            elif structure.file_type == "html":
                query_parts.append("html accessibility")
            elif structure.file_type == "markdown":
                query_parts.append("markdown documentation")
            
            # Добавляем специфичные запросы
            if structure.components:
                query_parts.append("react component design")
            
            if structure.accessibility_issues:
                query_parts.append("web accessibility")
            
            if not structure.has_types and structure.file_type == "typescript":
                query_parts.append("typescript type safety")
        else:
            query_parts.append(f"{file_path.suffix} best practices")
        
        return " ".join(query_parts[:3])
    
    def validate_suggestion(self, suggestion: Any) -> bool:
        """Валидирует предложение по улучшению фронтенд-кода."""
        # Базовая валидация
        if not hasattr(suggestion, 'description') or not suggestion.description:
            return False
        
        if not hasattr(suggestion, 'suggestion') or not suggestion.suggestion:
            return False
        
        # Минимальная длина
        if len(suggestion.description) < 10:
            return False
        
        if len(suggestion.suggestion) < 20:
            return False
        
        return True
