"""Protocol интерфейсы для CoderAgent зависимостей.

Улучшает тестируемость через явные контракты и dependency injection.
"""
from typing import Protocol, Optional, List, Dict, Any
from infrastructure.code_retrieval import CodeExample


class ILLM(Protocol):
    """Интерфейс для LLM генерации."""
    
    def generate(self, prompt: str, num_predict: int = 2048) -> str:
        """Генерирует текст по промпту.
        
        Args:
            prompt: Промпт для генерации
            num_predict: Максимальное количество токенов
            
        Returns:
            Сгенерированный текст
        """
        ...


class IPromptEnhancer(Protocol):
    """Интерфейс для улучшения промптов."""
    
    def enhance_for_coding(
        self,
        user_query: str,
        intent_type: str,
        plan: str,
        tests: str,
        context: str
    ) -> str:
        """Улучшает промпт для генерации кода.
        
        Args:
            user_query: Запрос пользователя
            intent_type: Тип намерения
            plan: План реализации
            tests: Тесты
            context: Контекст
            
        Returns:
            Улучшенный промпт
        """
        ...


class ICodeRetriever(Protocol):
    """Интерфейс для поиска примеров кода."""
    
    def find_similar(
        self,
        query: str,
        n: int = 3
    ) -> List[CodeExample]:
        """Ищет похожие примеры кода.
        
        Args:
            query: Запрос для поиска
            n: Количество примеров
            
        Returns:
            Список примеров кода
        """
        ...
    
    def add_from_history(
        self,
        query: str,
        code: str,
        success: bool = True
    ) -> None:
        """Добавляет код в историю для будущего использования.
        
        Args:
            query: Запрос пользователя
            code: Сгенерированный код
            success: Успешность генерации
        """
        ...


class IPromptBuilder(Protocol):
    """Интерфейс для построения промптов."""
    
    def build_generation_prompt(
        self,
        plan: str,
        tests: str,
        context: str,
        intent_type: str,
        user_query: Optional[str] = None,
        examples: Optional[List[CodeExample]] = None
    ) -> str:
        """Строит промпт для генерации кода.
        
        Args:
            plan: План реализации
            tests: Тесты
            context: Контекст
            intent_type: Тип намерения
            user_query: Запрос пользователя
            examples: Примеры кода
            
        Returns:
            Промпт для генерации
        """
        ...
    
    def build_fix_prompt(
        self,
        code: str,
        instructions: str,
        tests: str,
        validation_results: Dict[str, Any]
    ) -> str:
        """Строит промпт для исправления кода.
        
        Args:
            code: Исходный код
            instructions: Инструкции для исправления
            tests: Тесты
            validation_results: Результаты валидации
            
        Returns:
            Промпт для исправления
        """
        ...
