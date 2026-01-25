"""Project Profile - конфигурация проекта для анализа.

Убирает хардкод из кода, делая модуль конфигурируемым под разные типы проектов.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class ProjectDomain(str, Enum):
    """Домен проекта."""
    BACKEND = "backend"
    FRONTEND = "frontend"
    FULLSTACK = "fullstack"
    LIBRARY = "library"
    SCRIPT = "script"
    UNKNOWN = "unknown"


class ProjectFramework(str, Enum):
    """Фреймворк проекта."""
    FASTAPI = "fastapi"
    REACT = "react"
    VUE = "vue"
    DJANGO = "django"
    FLASK = "flask"
    NONE = "none"
    UNKNOWN = "unknown"


@dataclass
class QualityRules:
    """Правила качества кода для проекта."""
    # Python-специфичные
    max_function_complexity: int = 10
    max_function_length: int = 50
    require_docstrings: bool = True
    enforce_pep8: bool = True
    
    # Общие
    max_file_length: int = 500
    max_nesting_depth: int = 4
    allow_magic_numbers: bool = False
    
    # Дополнительные правила
    custom_rules: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Priorities:
    """Приоритеты типов улучшений."""
    security: int = 10  # Максимальный приоритет
    performance: int = 8
    architecture: int = 7
    code_quality: int = 6
    documentation: int = 5
    refactoring: int = 4


@dataclass
class ConfidencePolicy:
    """Политика уверенности."""
    min_confidence: float = 0.9  # Минимальная уверенность для предложений
    accumulation_enabled: bool = True  # Включить накопление уверенности
    min_observations: int = 3  # Минимум наблюдений для накопления
    stability_window_hours: int = 24  # Окно стабильности кода


@dataclass
class ProjectProfile:
    """Профиль проекта для анализа.
    
    Определяет:
    - Язык и фреймворк
    - Домен проекта
    - Правила качества
    - Приоритеты улучшений
    - Политику уверенности
    """
    language: str = "python"  # "python" | "typescript" | "javascript" | "mixed"
    framework: Optional[ProjectFramework] = None
    domain: ProjectDomain = ProjectDomain.UNKNOWN
    
    # Конфигурация
    quality_rules: QualityRules = field(default_factory=QualityRules)
    priorities: Priorities = field(default_factory=Priorities)
    confidence_policy: ConfidencePolicy = field(default_factory=ConfidencePolicy)
    
    # Дополнительные настройки
    excluded_directories: List[str] = field(default_factory=lambda: [
        ".venv", "__pycache__", ".git", "node_modules",
        ".mypy_cache", ".pytest_cache", ".cache",  # Кэш-директории
        "dist", "build", ".next", ".nuxt"  # Сборки
    ])
    excluded_file_patterns: List[str] = field(default_factory=lambda: ["test_", "_test.py"])
    
    # Доменные знания (для убирания хардкода)
    domain_keywords: Dict[str, List[str]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Инициализация после создания."""
        # Автоматически определяем доменные ключевые слова на основе framework и domain
        if not self.domain_keywords:
            self.domain_keywords = self._detect_domain_keywords()
    
    def _detect_domain_keywords(self) -> Dict[str, List[str]]:
        """Определяет ключевые слова на основе framework и domain."""
        keywords = {}
        
        if self.framework == ProjectFramework.FASTAPI:
            keywords["backend"] = ["api", "router", "endpoint", "fastapi"]
            keywords["agent"] = ["agent", "workflow", "task"]
        
        if self.domain == ProjectDomain.FRONTEND:
            keywords["frontend"] = ["component", "hook", "state", "props"]
        
        if self.domain == ProjectDomain.FULLSTACK:
            keywords["backend"] = ["api", "router", "endpoint"]
            keywords["frontend"] = ["component", "hook", "state"]
        
        return keywords
    
    def should_analyze_file(self, file_path: str) -> bool:
        """Определяет, нужно ли анализировать файл.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если файл нужно анализировать
        """
        # Проверяем исключённые директории
        for excluded_dir in self.excluded_directories:
            if excluded_dir in file_path:
                return False
        
        # Проверяем исключённые паттерны
        import os
        file_name = os.path.basename(file_path)
        for pattern in self.excluded_file_patterns:
            if pattern in file_name.lower():
                return False
        
        return True
    
    def get_file_priority(self, file_path: str) -> int:
        """Определяет приоритет файла для анализа.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Приоритет (1-10, 10 = максимальный)
        """
        priority = 5  # Базовый приоритет
        
        # Повышаем приоритет для важных файлов
        file_lower = file_path.lower()
        
        # Критичные файлы
        if any(keyword in file_lower for keyword in ["api", "router", "agent", "core"]):
            priority += 2
        
        # Важные файлы
        if any(keyword in file_lower for keyword in ["service", "handler", "manager"]):
            priority += 1
        
        return min(10, priority)
    
    @classmethod
    def detect_from_project(cls, project_path: str) -> "ProjectProfile":
        """Автоматически определяет профиль проекта.
        
        Args:
            project_path: Путь к корню проекта
            
        Returns:
            ProjectProfile с автоматически определёнными настройками
        """
        from pathlib import Path
        
        path = Path(project_path)
        profile = cls()
        
        # Определяем язык по файлам и конфигурационным файлам
        python_files = list(path.rglob("*.py"))
        ts_files = list(path.rglob("*.ts")) + list(path.rglob("*.tsx"))
        js_files = list(path.rglob("*.js")) + list(path.rglob("*.jsx"))
        
        # Проверяем конфигурационные файлы
        has_requirements = (path / "requirements.txt").exists()
        has_package_json = (path / "package.json").exists()
        has_tsconfig = (path / "tsconfig.json").exists()
        
        # Определяем язык
        if (python_files or has_requirements) and (ts_files or js_files or has_package_json or has_tsconfig):
            profile.language = "mixed"
        elif ts_files or js_files or has_tsconfig or (has_package_json and not has_requirements):
            profile.language = "typescript" if (ts_files or has_tsconfig) else "javascript"
        else:
            profile.language = "python"
        
        # Определяем domain
        # Если язык mixed, то domain должен быть FULLSTACK
        if profile.language == "mixed":
            profile.domain = ProjectDomain.FULLSTACK
        elif (path / "frontend").exists() or (path / "src" / "components").exists():
            if python_files or has_requirements:
                profile.domain = ProjectDomain.FULLSTACK
            else:
                profile.domain = ProjectDomain.FRONTEND
        elif python_files or has_requirements:
            profile.domain = ProjectDomain.BACKEND
        elif ts_files or js_files or has_package_json or has_tsconfig:
            profile.domain = ProjectDomain.FRONTEND
        else:
            profile.domain = ProjectDomain.UNKNOWN
        
        # Определяем framework
        if (path / "requirements.txt").exists():
            req_content = (path / "requirements.txt").read_text()
            if "fastapi" in req_content.lower():
                profile.framework = ProjectFramework.FASTAPI
            elif "django" in req_content.lower():
                profile.framework = ProjectFramework.DJANGO
            elif "flask" in req_content.lower():
                profile.framework = ProjectFramework.FLASK
        
        if (path / "package.json").exists():
            pkg_content = (path / "package.json").read_text()
            if "react" in pkg_content.lower():
                profile.framework = ProjectFramework.REACT
            elif "vue" in pkg_content.lower():
                profile.framework = ProjectFramework.VUE
        
        return profile
    
    @classmethod
    def default_python(cls) -> "ProjectProfile":
        """Создаёт профиль по умолчанию для Python-проекта."""
        return cls(
            language="python",
            domain=ProjectDomain.BACKEND,
            framework=ProjectFramework.NONE
        )
