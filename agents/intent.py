"""Агент для определения намерения пользователя."""
from dataclasses import dataclass
from typing import Optional
from infrastructure.local_llm import LocalLLM
from utils.logger import get_logger
from utils.model_checker import (
    get_available_model,
    get_light_model,
    get_any_available_model,
    check_model_available
)
from utils.config import get_config
from infrastructure.model_router import get_model_router


logger = get_logger()


@dataclass
class IntentResult:
    """Результат определения намерения пользователя."""
    type: str  # create | modify | debug | optimize | explain | test | refactor | greeting
    confidence: float  # 0.0 - 1.0
    description: str  # Описание намерения на русском


class IntentAgent:
    """Агент для классификации намерения пользователя."""
    
    # Доступные типы намерений
    INTENT_TYPES = [
        "create",  # Создать новый код/функцию/файл
        "modify",  # Изменить существующий код
        "debug",   # Найти и исправить ошибки
        "optimize", # Оптимизировать код (производительность/качество)
        "explain", # Объяснить как работает код
        "test",    # Написать/запустить тесты
        "refactor" # Рефакторинг (улучшение структуры без изменения функциональности)
    ]
    
    @staticmethod
    def is_greeting_fast(query: str) -> bool:
        """Статический метод для быстрой проверки на приветствие БЕЗ инициализации агента.
        
        Используется для раннего выхода из workflow без инициализации тяжелых компонентов.
        Вся логика проверки находится в IntentAgent, а не в роутере.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            True если это приветствие, False иначе
        """
        if not query:
            return False
        
        query_lower = query.strip().lower()
        
        greetings = [
            "привет", "здравствуй", "здравствуйте", "добрый день",
            "добрый вечер", "доброе утро", "доброй ночи", "хай", "хей", "салют",
            "hello", "hi", "hey", "greetings", "good morning", "good afternoon",
            "good evening", "good night", "howdy", "sup"
        ]
        
        # Проверяем точное совпадение или начало фразы
        for greeting in greetings:
            if query_lower == greeting or query_lower.startswith(greeting + " "):
                return True
        
        # Проверяем короткие запросы (1-2 слова), которые могут быть приветствиями
        words = query_lower.split()
        if len(words) <= 2:
            for greeting in greetings:
                if greeting in words:
                    return True
        
        return False
    
    def __init__(self, model: Optional[str] = None, temperature: float = 0.2, lazy_llm: bool = False) -> None:
        """Инициализация агента определения намерения.
        
        Args:
            model: Модель для классификации (если None, выбирается из config)
            temperature: Температура генерации (ниже для более точной классификации)
            lazy_llm: Если True, LLM не инициализируется сразу (для быстрых проверок типа greeting)
        """
        self.model = model
        self.temperature = temperature
        self.lazy_llm = lazy_llm
        self._llm: Optional[LocalLLM] = None
    
    @property
    def llm(self) -> LocalLLM:
        """Ленивая инициализация LLM - создаётся только когда нужна.
        
        Returns:
            Инициализированный LocalLLM
        """
        if self._llm is None:
            model = self.model
            if model is None:
                # Используем ModelRouter для выбора модели (поддерживает будущее расширение роя моделей)
                router = get_model_router()
                model_selection = router.select_model(
                    task_type="intent",
                    preferred_model=None,
                    context={"agent": "intent"}
                )
                model = model_selection.model
            
            self._llm = LocalLLM(
                model=model,
                temperature=self.temperature,
                top_p=0.9
            )
        return self._llm
    
    def determine_intent(self, user_query: str) -> IntentResult:
        """Определяет намерение пользователя из запроса.
        
        Args:
            user_query: Текст запроса пользователя
            
        Returns:
            IntentResult с типом намерения, уверенностью и описанием
        """
        if not user_query.strip():
            return IntentResult(
                type="explain",
                confidence=0.5,
                description="Пустой запрос, по умолчанию: объяснение"
            )
        
        # Проверяем на приветствие перед классификацией
        if self._is_greeting(user_query):
            return IntentResult(
                type="greeting",
                confidence=0.95,
                description="Приветствие пользователя"
            )
        
        # Формируем промпт для классификации
        prompt = self._build_classification_prompt(user_query)
        
        logger.info(f"🔍 Определяю намерение для запроса: {user_query[:60]}...")
        
        # Получаем ответ от модели (короткий ответ для быстрой классификации)
        response = self.llm.generate(prompt, num_predict=64)
        
        # Парсим ответ
        intent_result = self._parse_response(response, user_query)
        
        logger.info(
            f"✅ Намерение определено: {intent_result.type} "
            f"(уверенность: {intent_result.confidence:.2f})"
        )
        
        return intent_result
    
    def _build_classification_prompt(self, query: str) -> str:
        """Строит промпт для классификации намерения."""
        intents_str = " | ".join(self.INTENT_TYPES)
        
        prompt = f"""Определи тип намерения пользователя из следующего списка: {intents_str}

Запрос пользователя: "{query}"

Ответь ТОЛЬКО одним словом из списка (без дополнительных объяснений):
"""
        return prompt
    
    def _parse_response(self, response: str, original_query: str) -> IntentResult:
        """Парсит ответ модели и извлекает тип намерения.
        
        Args:
            response: Ответ модели
            original_query: Оригинальный запрос пользователя
            
        Returns:
            IntentResult
        """
        response_clean = response.strip().lower()
        
        # Ищем одно из ключевых слов в ответе
        found_intent: Optional[str] = None
        for intent_type in self.INTENT_TYPES:
            if intent_type in response_clean:
                found_intent = intent_type
                break
        
        # Если не нашли точное совпадение, пытаемся определить по ключевым словам запроса
        if not found_intent:
            found_intent = self._guess_intent_from_query(original_query)
        
        # Описания намерений на русском
        descriptions = {
            "create": "Создание нового кода, функции или файла",
            "modify": "Изменение существующего кода",
            "debug": "Поиск и исправление ошибок в коде",
            "optimize": "Оптимизация производительности или качества кода",
            "explain": "Объяснение как работает код",
            "test": "Написание или запуск тестов",
            "refactor": "Рефакторинг кода без изменения функциональности",
            "greeting": "Приветствие пользователя"
        }
        
        # Если всё ещё не определили, используем explain по умолчанию
        if not found_intent:
            found_intent = "explain"
            confidence = 0.5
        else:
            # Высокая уверенность если модель явно указала тип
            confidence = 0.85 if response_clean in self.INTENT_TYPES else 0.75
        
        return IntentResult(
            type=found_intent,
            confidence=confidence,
            description=descriptions.get(found_intent, "Объяснение кода")
        )
    
    def _guess_intent_from_query(self, query: str) -> Optional[str]:
        """Пытается определить намерение по ключевым словам в запросе.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Тип намерения или None
        """
        query_lower = query.lower()
        
        # Ключевые слова для каждого типа
        keywords = {
            "create": ["создать", "сделай", "напиши", "добавь новый", "create", "make", "write", "add new"],
            "modify": ["изменить", "измени", "обнови", "modify", "change", "update", "edit"],
            "debug": ["ошибка", "не работает", "исправь", "debug", "fix", "error", "broken", "баг"],
            "optimize": ["оптимизируй", "ускорь", "улучши производительность", "optimize", "speed up", "performance"],
            "explain": ["объясни", "как работает", "что делает", "explain", "how does", "what does"],
            "test": ["тест", "проверь", "test", "check", "verify"],
            "refactor": ["рефакторинг", "улучши структуру", "refactor", "restructure"]
        }
        
        for intent_type, words in keywords.items():
            if any(word in query_lower for word in words):
                return intent_type
        
        return None
    
    def _is_greeting(self, query: str) -> bool:
        """Проверяет, является ли запрос приветствием.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            True если это приветствие, False иначе
        """
        query_lower = query.strip().lower()
        
        # Список приветствий на русском и английском
        greetings = [
            "привет", "здравствуй", "здравствуйте", "добрый день", "добрый вечер",
            "доброе утро", "доброй ночи", "хай", "хей", "салют",
            "hello", "hi", "hey", "greetings", "good morning", "good afternoon",
            "good evening", "good night", "howdy", "sup"
        ]
        
        # Проверяем точное совпадение или начало фразы
        for greeting in greetings:
            if query_lower == greeting or query_lower.startswith(greeting + " "):
                return True
        
        # Проверяем короткие запросы (1-2 слова), которые могут быть приветствиями
        words = query_lower.split()
        if len(words) <= 2:
            for greeting in greetings:
                if greeting in words:
                    return True
        
        return False
