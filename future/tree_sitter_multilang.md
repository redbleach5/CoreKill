# Tree-sitter — Мультиязычный парсинг кода

## 📋 Обзор

[Tree-sitter](https://tree-sitter.github.io/) — быстрый инкрементальный парсер, написанный на C. Позволяет парсить код на любом языке в AST.

**Статус:** 🔮 Планируется  
**Приоритет:** Низкий (после стабилизации Python-only функционала)  
**Зависит от:** `future/context_engine_ast_parsing.md`

---

## 🎯 Зачем нужен

### Текущее ограничение

```python
# Сейчас используем стандартный ast — только Python
import ast
tree = ast.parse(code)  # ❌ Только Python, падает на ошибках синтаксиса
```

### С tree-sitter

```python
# Tree-sitter — любой язык, устойчив к ошибкам
import tree_sitter_python as tspython
parser = tspython.parser()
tree = parser.parse(bytes(code, "utf8"))  # ✅ Любой язык, парсит даже битый код
```

---

## 📊 Сравнение подходов

| Аспект | `ast` (Python) | tree-sitter |
|--------|----------------|-------------|
| **Языки** | Только Python | 100+ языков |
| **Скорость** | Быстро | Очень быстро (C) |
| **Битый код** | ❌ Падает | ✅ Парсит частично |
| **Инкрементальный** | ❌ Нет | ✅ Да |
| **Установка** | Встроен | `pip install tree-sitter-python` |
| **Зависимости** | Нет | Нужны grammar пакеты |

---

## 🗺️ Когда внедрять

### Предусловия
- [ ] Core workflow стабильно работает
- [ ] AST парсинг для Python реализован (`ast` модуль)
- [ ] Context Engine работает с графом зависимостей
- [ ] Есть реальная потребность в других языках

### Триггеры для внедрения
- Пользователи хотят генерировать JS/TS/Go/Rust код
- Нужен парсинг смешанных проектов (Python + JS)
- Нужен real-time анализ во время редактирования
- `ast.parse()` падает на частичном/битом коде

---

## 📦 Установка

```bash
# Базовый пакет
pip install tree-sitter

# Grammar для нужных языков
pip install tree-sitter-python
pip install tree-sitter-javascript
pip install tree-sitter-typescript
pip install tree-sitter-go
pip install tree-sitter-rust
```

---

## 🔧 Реализация

### 1. Абстракция парсера

**Файл:** `infrastructure/code_parser.py`

```python
"""Унифицированный парсер кода с поддержкой нескольких языков."""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path
from abc import ABC, abstractmethod


@dataclass
class ParsedNode:
    """Узел распарсенного AST."""
    type: str  # function_definition, class_definition, import_statement, etc.
    name: str
    start_line: int
    end_line: int
    signature: str
    children: List['ParsedNode']
    

@dataclass  
class ParseResult:
    """Результат парсинга файла."""
    language: str
    imports: List[str]
    functions: List[ParsedNode]
    classes: List[ParsedNode]
    calls: List[str]  # Вызовы функций
    success: bool
    error: Optional[str] = None


class CodeParser(ABC):
    """Абстрактный парсер кода."""
    
    @abstractmethod
    def parse(self, code: str, filename: str = "") -> ParseResult:
        """Парсит код и возвращает структуру."""
        pass
    
    @abstractmethod
    def supports_language(self, language: str) -> bool:
        """Проверяет поддержку языка."""
        pass


class PythonAstParser(CodeParser):
    """Парсер Python через стандартный ast (текущая реализация)."""
    
    def parse(self, code: str, filename: str = "") -> ParseResult:
        import ast
        try:
            tree = ast.parse(code)
            # ... извлечение imports, functions, classes ...
            return ParseResult(
                language="python",
                imports=[],  # TODO: извлечь
                functions=[],
                classes=[],
                calls=[],
                success=True
            )
        except SyntaxError as e:
            return ParseResult(
                language="python",
                imports=[],
                functions=[],
                classes=[],
                calls=[],
                success=False,
                error=str(e)
            )
    
    def supports_language(self, language: str) -> bool:
        return language.lower() in ("python", "py")


class TreeSitterParser(CodeParser):
    """Парсер через tree-sitter (мультиязычный)."""
    
    # Ленивая загрузка парсеров
    _parsers: Dict[str, Any] = {}
    
    # Маппинг расширений на языки
    EXTENSION_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
    }
    
    def _get_parser(self, language: str):
        """Ленивая загрузка парсера для языка."""
        if language in self._parsers:
            return self._parsers[language]
        
        try:
            if language == "python":
                import tree_sitter_python as ts_lang
            elif language == "javascript":
                import tree_sitter_javascript as ts_lang
            elif language == "typescript":
                import tree_sitter_typescript as ts_lang
            elif language == "go":
                import tree_sitter_go as ts_lang
            elif language == "rust":
                import tree_sitter_rust as ts_lang
            else:
                return None
            
            parser = ts_lang.parser()
            self._parsers[language] = parser
            return parser
            
        except ImportError:
            return None
    
    def parse(self, code: str, filename: str = "") -> ParseResult:
        # Определяем язык по расширению
        ext = Path(filename).suffix.lower() if filename else ".py"
        language = self.EXTENSION_MAP.get(ext, "python")
        
        parser = self._get_parser(language)
        if not parser:
            # Fallback на Python ast если tree-sitter недоступен
            return PythonAstParser().parse(code, filename)
        
        try:
            tree = parser.parse(bytes(code, "utf8"))
            
            # Извлекаем структуру из tree-sitter AST
            imports = self._extract_imports(tree, language)
            functions = self._extract_functions(tree, language)
            classes = self._extract_classes(tree, language)
            calls = self._extract_calls(tree, language)
            
            return ParseResult(
                language=language,
                imports=imports,
                functions=functions,
                classes=classes,
                calls=calls,
                success=True
            )
            
        except Exception as e:
            return ParseResult(
                language=language,
                imports=[],
                functions=[],
                classes=[],
                calls=[],
                success=False,
                error=str(e)
            )
    
    def _extract_imports(self, tree, language: str) -> List[str]:
        """Извлекает импорты из AST."""
        imports = []
        # Используем tree-sitter queries для извлечения
        # Пример для Python: (import_statement) @import
        # TODO: реализовать для каждого языка
        return imports
    
    def _extract_functions(self, tree, language: str) -> List[ParsedNode]:
        """Извлекает функции из AST."""
        # TODO: реализовать
        return []
    
    def _extract_classes(self, tree, language: str) -> List[ParsedNode]:
        """Извлекает классы из AST."""
        # TODO: реализовать
        return []
    
    def _extract_calls(self, tree, language: str) -> List[str]:
        """Извлекает вызовы функций из AST."""
        # TODO: реализовать
        return []
    
    def supports_language(self, language: str) -> bool:
        return language.lower() in self.EXTENSION_MAP.values()


def get_parser(prefer_tree_sitter: bool = False) -> CodeParser:
    """Возвращает подходящий парсер.
    
    Args:
        prefer_tree_sitter: Предпочитать tree-sitter даже для Python
        
    Returns:
        CodeParser
    """
    if prefer_tree_sitter:
        try:
            import tree_sitter_python
            return TreeSitterParser()
        except ImportError:
            pass
    
    return PythonAstParser()
```

### 2. Интеграция в Context Engine

**Файл:** `infrastructure/context_engine.py`

```python
from infrastructure.code_parser import get_parser, ParseResult

class CodeChunker:
    def __init__(self, max_chunk_tokens: int = 500, use_tree_sitter: bool = False):
        self.max_chunk_tokens = max_chunk_tokens
        self.parser = get_parser(prefer_tree_sitter=use_tree_sitter)
    
    def chunk_file(self, file_path: str, content: str) -> List[CodeChunk]:
        # Парсим файл
        parse_result = self.parser.parse(content, file_path)
        
        if parse_result.success:
            # Используем структуру AST для умного разбиения
            return self._chunk_by_ast(content, parse_result)
        else:
            # Fallback на regex-based chunking
            return self._chunk_by_regex(content, file_path)
```

### 3. Конфигурация

**Файл:** `config.toml`

```toml
[context_engine]
# Использовать tree-sitter для парсинга (требует установки пакетов)
use_tree_sitter = false

# Поддерживаемые языки (если tree-sitter включён)
supported_languages = ["python", "javascript", "typescript"]
```

---

## 🚀 Порядок внедрения

### Фаза 1: Абстракция (1 день)
1. Создать `infrastructure/code_parser.py`
2. Реализовать `PythonAstParser` (обёртка над текущим кодом)
3. Добавить интерфейс `CodeParser`

### Фаза 2: Tree-sitter для Python (2 дня)
1. Добавить `tree-sitter-python` как опциональную зависимость
2. Реализовать `TreeSitterParser` для Python
3. Сравнить производительность с `ast`

### Фаза 3: Мультиязычность (3-5 дней)
1. Добавить поддержку JavaScript/TypeScript
2. Добавить поддержку Go/Rust (по запросу)
3. Обновить Context Engine для мультиязычных проектов

### Фаза 4: Инкрементальный парсинг (опционально)
1. Использовать tree-sitter edit API
2. Кэшировать AST между изменениями
3. Интеграция с file watcher

---

## 📊 Языки и их поддержка

| Язык | Grammar пакет | Приоритет |
|------|--------------|-----------|
| Python | `tree-sitter-python` | ✅ Высокий (уже есть `ast`) |
| JavaScript | `tree-sitter-javascript` | 🟡 Средний |
| TypeScript | `tree-sitter-typescript` | 🟡 Средний |
| Go | `tree-sitter-go` | 🔵 Низкий |
| Rust | `tree-sitter-rust` | 🔵 Низкий |
| Java | `tree-sitter-java` | 🔵 Низкий |
| C/C++ | `tree-sitter-c`, `tree-sitter-cpp` | 🔵 Низкий |

---

## ⚠️ Ограничения

1. **Размер зависимостей** — каждый grammar ~1-5 MB
2. **Сложность queries** — у каждого языка свои паттерны AST
3. **Поддержка** — не все языки одинаково хорошо поддержаны
4. **Компиляция** — некоторые grammar требуют C compiler

---

## 🔗 Ссылки

- [Tree-sitter Documentation](https://tree-sitter.github.io/)
- [py-tree-sitter](https://github.com/tree-sitter/py-tree-sitter)
- [Tree-sitter Playground](https://tree-sitter.github.io/tree-sitter/playground)
- [Available Grammars](https://github.com/tree-sitter)

---

## 📝 Связанные документы

- `future/context_engine_ast_parsing.md` — базовый AST парсинг (Python only)
- `infrastructure/context_engine.py` — текущая реализация
- `.cursor/rules/legacy_architecture_contract.md` — описание Context Engine
