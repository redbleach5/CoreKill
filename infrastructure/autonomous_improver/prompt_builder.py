"""Prompt Builder - универсальный построитель промптов для анализа кода.

Поддерживает разные языки и типы проектов через адаптеры и профили.
"""
from typing import Optional, Any
from pathlib import Path


class PromptBuilder:
    """Универсальный построитель промптов для анализа кода.
    
    Адаптирует промпт под:
    - Язык программирования
    - Тип файла
    - Контекст проекта
    - Приоритеты улучшений
    """
    
    BASE_PROMPT = """Ты — опытный senior разработчик, анализирующий код проекта.

Твоя задача — найти возможности для улучшения кода и оценить их уверенность.

## Правила анализа:
1. Будь КРИТИЧНЫМ — предлагай только реальные улучшения
2. Оценивай уверенность ЧЕСТНО (0.0-1.0)
3. Предлагай улучшения только если уверенность >= 0.9
4. Фокусируйся на:
   - Качестве кода (читаемость, поддерживаемость)
   - Производительности (оптимизация, неэффективные алгоритмы, лишние циклы)
   - Безопасности (инъекции, небезопасные операции)
   - Документации (отсутствующие комментарии, неясные имена)
   - Архитектуре (нарушения SOLID, DRY, магические числа, длинные функции)
   - Соответствии стандартам проекта"""
    
    LANGUAGE_SPECIFIC_RULES = {
        "python": """
## Python-специфичные критерии:
- Соответствие PEP 8: именование, отступы, длина строк
- Docstrings: отсутствующие docstrings для функций и классов
- Типизация: использование type hints
- Идиомы Python: использование list comprehensions, context managers
- Импорты: неиспользуемые импорты, неправильный порядок""",
        
        "typescript": """
## TypeScript-специфичные критерии:
- Типизация: использование `any`, отсутствие типов для пропсов
- React паттерны: правильное использование хуков, мемоизация
- Accessibility: отсутствие `alt`, `aria-*` атрибутов
- Performance: отсутствие `memo`, `useMemo`, лишние ререндеры
- Импорты: неиспользуемые импорты""",
        
        "javascript": """
## JavaScript-специфичные критерии:
- React паттерны: правильное использование хуков
- Accessibility: отсутствие `alt`, `aria-*` атрибутов
- Performance: отсутствие оптимизаций, лишние ререндеры
- Импорты: неиспользуемые импорты""",
        
        "html": """
## HTML-специфичные критерии:
- Семантическая разметка: использование правильных тегов
- Accessibility: отсутствие `alt`, `aria-*`, семантических тегов
- SEO: отсутствие мета-тегов, правильная структура
- Валидность: некорректная структура HTML""",
        
        "markdown": """
## Markdown-специфичные критерии:
- Структура: отсутствие заголовков, плохая организация
- Примеры: отсутствие примеров кода
- Ссылки: устаревшие или битые ссылки
- Форматирование: неправильное использование markdown""",
        
        "json": """
## JSON-специфичные критерии:
- Валидность: некорректный JSON
- Структура: неоптимальная организация данных
- Дублирование: повторяющиеся ключи или значения
- Неиспользуемые ключи: лишние поля в конфигурации"""
    }
    
    DOMAIN_SPECIFIC_RULES = {
        "frontend": """
## Frontend-специфичные критерии:
- UI/UX: недоступные элементы, плохая навигация
- Accessibility (a11y): отсутствие поддержки скринридеров
- Performance: неоптимальные ререндеры, большие бандлы
- TypeScript: отсутствие типов в TypeScript файлах""",
        
        "backend": """
## Backend-специфичные критерии:
- Безопасность: SQL-инъекции, XSS, небезопасные операции
- Производительность: N+1 запросы, неэффективные алгоритмы
- Обработка ошибок: отсутствие обработки исключений
- API дизайн: неправильная структура endpoints"""
    }
    
    @classmethod
    def build(
        cls,
        adapter: Any,  # LanguageAdapter
        profile: Any,  # ProjectProfile
        context: str,
        code_sample: str,
        web_context: str = "",
        file_path: Optional[Path] = None
    ) -> str:
        """Строит универсальный промпт для анализа.
        
        Args:
            adapter: LanguageAdapter для определения языка
            profile: ProjectProfile для контекста проекта
            context: Контекст файла (из adapter.build_context)
            code_sample: Выборка кода для анализа
            web_context: Контекст из веб-поиска (опционально)
            file_path: Путь к файлу (для определения языка в коде)
            
        Returns:
            Полный промпт для LLM
        """
        prompt_parts = [cls.BASE_PROMPT]
        
        # Добавляем правила для языка
        language = adapter.language
        if language in cls.LANGUAGE_SPECIFIC_RULES:
            prompt_parts.append(cls.LANGUAGE_SPECIFIC_RULES[language])
        elif language == "frontend":
            # Для фронтенда определяем конкретный язык по расширению
            if file_path:
                ext = file_path.suffix.lower()
                if ext in [".ts", ".tsx"]:
                    prompt_parts.append(cls.LANGUAGE_SPECIFIC_RULES["typescript"])
                elif ext in [".js", ".jsx"]:
                    prompt_parts.append(cls.LANGUAGE_SPECIFIC_RULES["javascript"])
                elif ext == ".html":
                    prompt_parts.append(cls.LANGUAGE_SPECIFIC_RULES["html"])
                elif ext == ".md":
                    prompt_parts.append(cls.LANGUAGE_SPECIFIC_RULES["markdown"])
                elif ext == ".json":
                    prompt_parts.append(cls.LANGUAGE_SPECIFIC_RULES["json"])
        
        # Добавляем правила для домена
        if profile.domain.value in cls.DOMAIN_SPECIFIC_RULES:
            prompt_parts.append(cls.DOMAIN_SPECIFIC_RULES[profile.domain.value])
        
        # Определяем язык для подсветки синтаксиса
        code_lang = cls._detect_code_language(file_path, adapter)
        
        # Формируем финальный промпт
        prompt_parts.append(f"""
## Формат кода примера:
Если предлагаешь исправление, покажи ДО и ПОСЛЕ:
```{code_lang}
# Было (проблема):
[проблемный код]

# Стало (решение):
[улучшенный код]
```

## Формат ответа (JSON):
{{
  "suggestions": [
    {{
      "type": "code_quality|performance|security|documentation|refactoring|architecture|accessibility|ux|types|component_design",
      "file_path": "путь/к/файлу",
      "description": "Краткое описание проблемы",
      "suggestion": "Конкретное предложение по улучшению",
      "confidence": 0.95,
      "priority": 8,
      "reasoning": "Обоснование почему это улучшение",
      "estimated_impact": "low|medium|high",
      "code_example": "Пример улучшенного кода (опционально)"
    }}
  ]
}}

Отвечай ТОЛЬКО валидным JSON, без дополнительного текста.""")
        
        # Добавляем код и контекст
        prompt_parts.append(f"\n## Код для анализа:\n\n```{code_lang}\n{code_sample}\n```\n\n## Контекст:\n{context}")
        
        if web_context:
            prompt_parts.append(web_context)
        
        return "\n".join(prompt_parts)
    
    @staticmethod
    def _detect_code_language(file_path: Optional[Path], adapter: Any) -> str:
        """Определяет язык для подсветки синтаксиса в промпте."""
        if file_path:
            ext = file_path.suffix.lower()
            lang_map = {
                ".py": "python",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".js": "javascript",
                ".jsx": "javascript",
                ".html": "html",
                ".md": "markdown",
                ".json": "json"
            }
            return lang_map.get(ext, "text")
        
        # Fallback на язык адаптера
        if adapter.language == "python":
            return "python"
        elif adapter.language == "frontend":
            return "typescript"  # По умолчанию для фронтенда
        else:
            return "text"
