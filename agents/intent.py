"""Агент для определения намерения пользователя."""
from dataclasses import dataclass, field
from typing import Optional
from infrastructure.local_llm import LocalLLM
from utils.logger import get_logger
from utils.model_checker import (
    get_available_model,
    get_light_model,
    get_any_available_model,
    check_model_available,
    TaskComplexity
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
    complexity: TaskComplexity = field(default=TaskComplexity.SIMPLE)  # Сложность задачи
    recommended_mode: str = field(default="auto")  # Рекомендуемый режим: chat, plan, analyze, code
    requires_code_generation: bool = field(default=False)  # Нужна ли генерация кода
    
    def __post_init__(self) -> None:
        """Автоматически определяет рекомендуемый режим."""
        # Типы, требующие полного workflow с генерацией кода
        code_generation_types = {"create", "modify", "debug", "optimize", "test", "refactor"}
        
        # Типы для режима chat (простой диалог)
        chat_types = {"greeting", "help", "explain"}
        
        # Определяем режим на основе типа намерения
        if self.type in chat_types:
            self.recommended_mode = "chat"
            self.requires_code_generation = False
        elif self.type in code_generation_types:
            self.recommended_mode = "code"
            self.requires_code_generation = True
        else:
            self.recommended_mode = "chat"
            self.requires_code_generation = False


class IntentAgent:
    """Агент для классификации намерения пользователя."""
    
    # Доступные типы намерений с описаниями для LLM
    INTENT_TYPES = {
        "greeting": "Приветствие, знакомство (привет, здравствуйте, hello)",
        "help": "Вопрос о возможностях системы, что умеет, как использовать",
        "create": "Создать новый код, функцию, класс, модуль, скрипт",
        "modify": "Изменить, обновить, добавить в существующий код",
        "debug": "Найти и исправить ошибку, баг, проблему в КОНКРЕТНОМ коде",
        "optimize": "Оптимизировать производительность, ускорить код",
        "explain": "Объяснить как работает код, документация",
        "test": "Написать тесты, проверить код",
        "refactor": "Рефакторинг, улучшение структуры без изменения функциональности"
    }
    
    # Единый список приветствий (используется в is_greeting_fast и _is_greeting)
    GREETINGS = frozenset([
        # Русские
        "привет", "здравствуй", "здравствуйте", "добрый день", "добрый вечер",
        "доброе утро", "доброй ночи", "хай", "хей", "салют",
        # Английские
        "hello", "hi", "hey", "greetings", "good morning", "good afternoon",
        "good evening", "good night", "howdy", "sup"
    ])
    
    # Короткие приветствия для быстрой проверки без LLM
    SIMPLE_GREETINGS = frozenset([
        "привет", "здравствуй", "здравствуйте", "хай", "хей", "салют",
        "hello", "hi", "hey", "howdy", "sup"
    ])
    
    @staticmethod
    def is_greeting_fast(query: str) -> bool:
        """Быстрая проверка на простое приветствие (без LLM).
        
        Используется ТОЛЬКО для очень коротких однозначных приветствий,
        чтобы не тратить время на LLM для "привет" или "hello".
        
        Args:
            query: Запрос пользователя
            
        Returns:
            True если это однозначное короткое приветствие
        """
        if not query:
            return False
        
        query_lower = query.strip().lower()
        words = query_lower.split()
        
        # Только для очень коротких запросов (1-2 слова)
        if len(words) > 3:
            return False
        
        return query_lower in IntentAgent.SIMPLE_GREETINGS or words[0] in IntentAgent.SIMPLE_GREETINGS
    
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
        """Определяет намерение пользователя через LLM.
        
        Использует лёгкую модель для умной классификации вместо хардкода паттернов.
        
        Args:
            user_query: Текст запроса пользователя
            
        Returns:
            IntentResult с типом намерения, уверенностью и описанием
        """
        if not user_query.strip():
            return IntentResult(
                type="help",
                confidence=0.5,
                description="Пустой запрос"
            )
        
        # Только для очень простых приветствий (1-2 слова) пропускаем LLM
        if self._is_greeting(user_query) and len(user_query.split()) <= 2:
            return IntentResult(
                type="greeting",
                confidence=0.95,
                description="Приветствие пользователя"
            )
        
        logger.info(f"🔍 Определяю намерение для запроса: {user_query[:60]}...")
        
        # Полноценная LLM классификация
        intent_result = self._classify_with_llm(user_query)
        
        logger.info(
            f"✅ Намерение определено: {intent_result.type} "
            f"(уверенность: {intent_result.confidence:.2f})"
        )
        
        return intent_result
    
    def _classify_with_llm(self, query: str) -> IntentResult:
        """Классифицирует намерение и сложность через LLM.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            IntentResult с типом, уверенностью и сложностью
        """
        # Формируем описание типов для промпта
        types_description = "\n".join(
            f"  - {intent}: {desc}" 
            for intent, desc in self.INTENT_TYPES.items()
        )
        
        prompt = f"""Classify this user request for a CODE GENERATION system.

REQUEST: "{query}"

TYPES:
{types_description}

COMPLEXITY LEVELS:
- "simple" = single function, utility, small script (1 file, <100 lines)
- "medium" = class, module with multiple functions, API endpoint (1-2 files, 100-500 lines)
- "complex" = game, system, multi-file project, architecture (3+ files, 500+ lines)

RULES:
- "help" = meta-questions: "что умеешь", "can you help", questions WITHOUT specific task
- "greeting" = only simple greetings like "привет", "hello"  
- "create" = specific task to generate code: "напиши X", "создай Y", "make Z"
- "debug" = fix SPECIFIC code with errors

EXAMPLES:
- "напиши функцию сортировки" -> intent: create, complexity: simple
- "создай класс для работы с БД" -> intent: create, complexity: medium  
- "напиши игру змейка" -> intent: create, complexity: complex
- "напиши игру тетрис" -> intent: create, complexity: complex
- "создай веб-сервер" -> intent: create, complexity: medium
- "сделай парсер JSON" -> intent: create, complexity: simple

JSON response: {{"intent": "type", "confidence": 0.0-1.0, "complexity": "simple|medium|complex"}}
JSON:"""

        from utils.config import get_config
        config = get_config()
        response = self.llm.generate(prompt, num_predict=config.llm_tokens_intent)
        
        return self._parse_llm_classification(response, query)
    
    def _parse_llm_classification(self, response: str, original_query: str) -> IntentResult:
        """Парсит JSON ответ от LLM классификации.
        
        Args:
            response: Ответ модели
            original_query: Оригинальный запрос
            
        Returns:
            IntentResult с типом, уверенностью и сложностью
        """
        import json
        
        # Описания для результата
        descriptions = {
            "greeting": "Приветствие пользователя",
            "help": "Вопрос о возможностях системы",
            "create": "Создание нового кода",
            "modify": "Изменение существующего кода",
            "debug": "Поиск и исправление ошибок",
            "optimize": "Оптимизация производительности",
            "explain": "Объяснение работы кода",
            "test": "Написание тестов",
            "refactor": "Рефакторинг кода"
        }
        
        # Маппинг строковых значений complexity в enum
        complexity_map = {
            "simple": TaskComplexity.SIMPLE,
            "medium": TaskComplexity.MEDIUM,
            "complex": TaskComplexity.COMPLEX
        }
        
        try:
            # Ищем JSON в ответе
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                intent = data.get("intent", "create").lower()
                confidence = float(data.get("confidence", 0.75))
                reason = data.get("reason", "")
                complexity_str = data.get("complexity", "simple").lower()
                
                # Валидируем тип
                if intent not in self.INTENT_TYPES:
                    # Пытаемся найти похожий
                    for valid_type in self.INTENT_TYPES:
                        if valid_type in intent:
                            intent = valid_type
                            break
                    else:
                        intent = "create"  # default
                
                # Валидируем complexity
                complexity = complexity_map.get(complexity_str, TaskComplexity.SIMPLE)
                
                # Эвристика: greeting и help всегда simple
                if intent in ("greeting", "help"):
                    complexity = TaskComplexity.SIMPLE
                
                return IntentResult(
                    type=intent,
                    confidence=min(max(confidence, 0.0), 1.0),
                    description=descriptions.get(intent, reason or "Выполнение задачи"),
                    complexity=complexity
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        
        # Fallback: ищем ключевые слова в ответе
        response_lower = response.lower()
        for intent_type in self.INTENT_TYPES:
            if intent_type in response_lower:
                # Определяем complexity эвристически по запросу
                complexity = self._estimate_complexity_heuristic(original_query)
                return IntentResult(
                    type=intent_type,
                    confidence=0.7,
                    description=descriptions.get(intent_type, "Выполнение задачи"),
                    complexity=complexity
                )
        
        # Default
        return IntentResult(
            type="create",
            confidence=0.5,
            description="Создание кода (по умолчанию)",
            complexity=self._estimate_complexity_heuristic(original_query)
        )
    
    def _estimate_complexity_heuristic(self, query: str) -> TaskComplexity:
        """Эвристическое определение сложности по ключевым словам.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Оценка сложности
        """
        query_lower = query.lower()
        
        # Ключевые слова для complex задач
        complex_keywords = [
            'игр', 'game', 'систем', 'system', 'приложен', 'application', 'app',
            'проект', 'project', 'архитектур', 'веб-сайт', 'website', 'платформ',
            'сервис', 'service', 'бот', 'bot', 'парсер сайт', 'scraper',
            'змейк', 'snake', 'тетрис', 'tetris', 'шахмат', 'chess',
            'магазин', 'shop', 'store', 'crm', 'cms', 'api сервер'
        ]
        
        # Ключевые слова для medium задач
        medium_keywords = [
            'класс', 'class', 'модуль', 'module', 'api', 'endpoint',
            'crud', 'база данных', 'database', 'db', 'orm', 'auth',
            'парсер', 'parser', 'конвертер', 'converter', 'валидатор',
            'сервер', 'server', 'клиент', 'client', 'обработчик', 'handler'
        ]
        
        # Проверяем complex
        for keyword in complex_keywords:
            if keyword in query_lower:
                return TaskComplexity.COMPLEX
        
        # Проверяем medium
        for keyword in medium_keywords:
            if keyword in query_lower:
                return TaskComplexity.MEDIUM
        
        # По умолчанию simple
        return TaskComplexity.SIMPLE
    
    
    def _is_greeting(self, query: str) -> bool:
        """Проверяет, является ли запрос приветствием.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            True если это приветствие, False иначе
        """
        query_lower = query.strip().lower()
        
        # Проверяем точное совпадение или начало фразы
        for greeting in self.GREETINGS:
            if query_lower == greeting or query_lower.startswith(greeting + " "):
                return True
        
        # Проверяем короткие запросы (1-2 слова), которые могут быть приветствиями
        words = query_lower.split()
        if len(words) <= 2:
            for greeting in self.GREETINGS:
                if greeting in words:
                    return True
        
        return False
