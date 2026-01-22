"""Агент для определения намерения пользователя.

Поддерживает два режима работы:
- Structured Output (Pydantic): generate_structured() с гарантированным форматом
- Legacy: ручной парсинг JSON (fallback)

Режим выбирается через config.toml:
    [structured_output]
    enabled_agents = ["intent"]
"""
from dataclasses import dataclass, field
from typing import Optional, Union
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
from utils.structured_helpers import generate_with_fallback, is_structured_output_enabled
from models.agent_responses import IntentResponse, IntentType


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
        """Автоматически определяет рекомендуемый режим.
        
        Логика выбора режима:
        - chat: диалог, объяснения, помощь (без генерации кода)
        - code: создание/изменение кода через TDD workflow
        - analyze: анализ проекта (workflow без генерации кода)
        
        Важно: debug и optimize могут быть как chat (обсуждение), так и code (исправление).
        По умолчанию для них выбираем code, но эвристика в API может переопределить.
        """
        # Типы, ОДНОЗНАЧНО требующие генерации кода
        code_generation_types = {"create", "modify", "test", "refactor"}
        
        # Типы для режима chat (диалог без генерации кода)
        chat_types = {"greeting", "help", "explain"}
        
        # Типы, которые МОГУТ требовать код (зависит от контекста)
        # По умолчанию отправляем в code, но API может переопределить на chat
        ambiguous_types = {"debug", "optimize"}
        
        # Типы для анализа (workflow без генерации кода, но с индексацией проекта)
        analyze_types = {"analyze"}
        
        # Определяем режим на основе типа намерения
        if self.type in chat_types:
            self.recommended_mode = "chat"
            self.requires_code_generation = False
        elif self.type in analyze_types:
            # Анализ проекта — запускаем workflow для сбора контекста, но без генерации кода
            self.recommended_mode = "analyze"
            self.requires_code_generation = False
        elif self.type in code_generation_types:
            self.recommended_mode = "code"
            self.requires_code_generation = True
        elif self.type in ambiguous_types:
            # Для debug/optimize — по умолчанию code, но с флагом что это неоднозначно
            self.recommended_mode = "code"
            self.requires_code_generation = True
        else:
            # Неизвестный тип — лучше chat чтобы не запускать тяжёлый workflow
            self.recommended_mode = "chat"
            self.requires_code_generation = False


class IntentAgent:
    """Агент для классификации намерения пользователя."""
    
    # Минимальные и максимальные пороги confidence
    MIN_CONFIDENCE = 0.3
    MAX_CONFIDENCE = 0.95
    
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
        "refactor": "Рефакторинг, улучшение структуры без изменения функциональности",
        "analyze": "Анализ проекта, кодовой базы, структуры, архитектуры, обзор кода"
    }
    
    # Единый список приветствий
    GREETINGS = frozenset([
        # Русские
        "привет", "здравствуй", "здравствуйте", "добрый день", "добрый вечер",
        "доброе утро", "доброй ночи", "хай", "хей", "салют",
        # Английские
        "hello", "hi", "hey", "greetings", "good morning", "good afternoon",
        "good evening", "good night", "howdy", "sup"
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
        
        # Только для очень коротких запросов (1-3 слова)
        if len(words) > 3:
            return False
        
        # Проверяем точное совпадение или начало фразы
        if query_lower in IntentAgent.GREETINGS:
            return True
        
        # Проверяем первое слово
        if words and words[0] in IntentAgent.GREETINGS:
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
        self._cache: dict[str, IntentResult] = {}  # Простой кэш для повторяющихся запросов
    
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
            
            from infrastructure.local_llm import create_llm_for_stage
            self._llm = create_llm_for_stage(
                stage="intent",
                model=model,
                temperature=self.temperature,
                top_p=0.9
            )
        return self._llm
    
    def _calibrate_confidence(self, raw_confidence: float, query_length: int) -> float:
        """Калибрует уверенность на основе длины запроса.
        
        Короткие запросы обычно имеют более низкую уверенность,
        длинные запросы — более высокую.
        
        Args:
            raw_confidence: Исходная уверенность от LLM
            query_length: Длина запроса в символах
            
        Returns:
            Откалиброванная уверенность в диапазоне [MIN_CONFIDENCE, MAX_CONFIDENCE]
        """
        # Нормализуем confidence в допустимый диапазон
        confidence = max(self.MIN_CONFIDENCE, min(self.MAX_CONFIDENCE, raw_confidence))
        
        # Короткие запросы (< 20 символов) — немного снижаем уверенность
        if query_length < 20:
            confidence = max(self.MIN_CONFIDENCE, confidence - 0.1)
        # Длинные запросы (> 100 символов) — немного повышаем уверенность
        elif query_length > 100:
            confidence = min(self.MAX_CONFIDENCE, confidence + 0.05)
        
        return confidence
    
    def _detect_language(self, query: str) -> str:
        """Определяет язык запроса.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Код языка ('ru' или 'en')
        """
        # Проверяем наличие кириллических символов
        has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in query)
        
        # Если есть кириллица - русский, иначе английский
        return "ru" if has_cyrillic else "en"
    
    def _get_prompt(self, query: str, is_structured: bool = True) -> str:
        """Создаёт промпт для классификации намерения.
        
        Унифицированный метод для structured и legacy режимов,
        с адаптацией под язык запроса.
        
        Args:
            query: Запрос пользователя
            is_structured: Использовать ли structured output формат
            
        Returns:
            Промпт для LLM
        """
        language = self._detect_language(query)
        
        # Формируем описание типов
        types_description = "\n".join(
            f"  - {intent}: {desc}" 
            for intent, desc in self.INTENT_TYPES.items()
        )
        
        # Базовый промпт (английский для structured, адаптируется для legacy)
        if is_structured:
            # Structured промпт всегда на английском (для лучшей совместимости с моделями)
            base_prompt = f"""Classify this user request for a CODE GENERATION system.

REQUEST: "{query}"

INTENT TYPES:
{types_description}

COMPLEXITY:
- simple: single function, <100 lines
- medium: class/module, 100-500 lines
- complex: multi-file project, 500+ lines

RULES:
- "greeting" = ONLY if request is JUST a greeting with NO task
- "help" = meta-questions about system, NOT code tasks
- "create" = ANY code generation task: "print X", "def X", "напиши X", "создай Y"

EXAMPLES:
- "print hello" -> create (code task to print something)
- "print hi" -> create (code task)
- "def add(a,b)" -> create (function definition)
- "привет" -> greeting (just greeting)
- "hello world program" -> create (code task)

Respond with intent, confidence (0-1), complexity, and brief reasoning."""
        else:
            # Legacy промпт адаптируется под язык
            if language == "ru":
                base_prompt = f"""Классифицируй этот запрос пользователя для системы ГЕНЕРАЦИИ КОДА.

ЗАПРОС: "{query}"

ТИПЫ:
{types_description}

УРОВНИ СЛОЖНОСТИ:
- "simple" = одна функция, утилита, небольшой скрипт (1 файл, <100 строк)
- "medium" = класс, модуль с несколькими функциями, API endpoint (1-2 файла, 100-500 строк)
- "complex" = игра, система, многофайловый проект, архитектура (3+ файла, 500+ строк)

ПРАВИЛА:
- "help" = мета-вопросы: "что умеешь", "can you help", вопросы БЕЗ конкретной задачи
- "greeting" = только простые приветствия типа "привет", "hello"
- "create" = конкретная задача на генерацию кода: "напиши X", "создай Y", "make Z"
- "debug" = исправить КОНКРЕТНЫЙ код с ошибками
- "analyze" = обзор/анализ проекта, кодовой базы, архитектуры

ПРИМЕРЫ:
- "напиши функцию сортировки" -> intent: create, complexity: simple
- "создай класс для работы с БД" -> intent: create, complexity: medium
- "напиши игру змейка" -> intent: create, complexity: complex
- "проанализируй мой проект" -> intent: analyze, complexity: complex

JSON ответ: {{"intent": "type", "confidence": 0.0-1.0, "complexity": "simple|medium|complex"}}
JSON:"""
            else:
                base_prompt = f"""Classify this user request for a CODE GENERATION system.

REQUEST: "{query}"

TYPES:
{types_description}

COMPLEXITY LEVELS:
- "simple" = single function, utility, small script (1 file, <100 lines)
- "medium" = class, module with multiple functions, API endpoint (1-2 files, 100-500 lines)
- "complex" = game, system, multi-file project, architecture (3+ files, 500+ lines)

RULES:
- "help" = meta-questions: "what can you do", "can you help", questions WITHOUT specific task
- "greeting" = only simple greetings like "hello", "hi"
- "create" = specific task to generate code: "write X", "create Y", "make Z"
- "debug" = fix SPECIFIC code with errors
- "analyze" = review/analyze project, codebase, architecture

EXAMPLES:
- "write a sorting function" -> intent: create, complexity: simple
- "create a database class" -> intent: create, complexity: medium
- "make a snake game" -> intent: create, complexity: complex
- "analyze my project" -> intent: analyze, complexity: complex

JSON response: {{"intent": "type", "confidence": 0.0-1.0, "complexity": "simple|medium|complex"}}
JSON:"""
        
        return base_prompt
    
    def determine_intent(self, user_query: str) -> IntentResult:
        """Определяет намерение пользователя через LLM.
        
        Использует лёгкую модель для умной классификации вместо хардкода паттернов.
        Поддерживает кэширование для повторяющихся запросов.
        
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
        
        # Проверяем кэш
        query_key = user_query.strip().lower()
        if query_key in self._cache:
            logger.debug(f"♻️ Использую кэшированный результат для: {user_query[:60]}...")
            return self._cache[query_key]
        
        # Только для очень простых приветствий (1-3 слова) пропускаем LLM
        if self._is_greeting(user_query) and len(user_query.split()) <= 3:
            result = IntentResult(
                type="greeting",
                confidence=0.95,
                description="Приветствие пользователя"
            )
            # Кэшируем результат
            self._cache[query_key] = result
            return result
        
        logger.info(f"🔍 Определяю намерение для запроса: {user_query[:60]}...")
        
        # Полноценная LLM классификация
        intent_result = self._classify_with_llm(user_query)
        
        # Калибруем confidence
        intent_result.confidence = self._calibrate_confidence(
            intent_result.confidence,
            len(user_query)
        )
        
        # Кэшируем результат (ограничиваем размер кэша)
        if len(self._cache) < 1000:
            self._cache[query_key] = intent_result
        
        logger.info(
            f"✅ Намерение определено: {intent_result.type} "
            f"(уверенность: {intent_result.confidence:.2f})"
        )
        
        return intent_result
    
    def _classify_with_llm(self, query: str) -> IntentResult:
        """Классифицирует намерение и сложность через LLM.
        
        Использует structured output если включён в config.toml,
        иначе fallback на legacy парсинг.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            IntentResult с типом, уверенностью и сложностью
        """
        # Проверяем, включён ли structured output для intent
        if is_structured_output_enabled("intent"):
            return self._classify_structured(query)
        else:
            return self._classify_legacy(query)
    
    def _classify_structured(self, query: str) -> IntentResult:
        """Классифицирует намерение через structured output (Pydantic).
        
        Гарантирует формат ответа через JSON Schema валидацию.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            IntentResult с типом, уверенностью и сложностью
        """
        prompt = self._get_prompt(query, is_structured=True)
        config = get_config()
        
        # Используем generate_with_fallback для автоматического fallback
        response = generate_with_fallback(
            llm=self.llm,
            prompt=prompt,
            response_model=IntentResponse,
            fallback_fn=lambda: self._response_to_result(self._classify_legacy(query)),
            agent_name="intent",
            num_predict=config.llm_tokens_intent
        )
        
        # Конвертируем IntentResponse -> IntentResult
        return self._response_to_result(response)
    
    def _response_to_result(self, response: Union[IntentResponse, IntentResult]) -> IntentResult:
        """Конвертирует IntentResponse или IntentResult в IntentResult.
        
        Унифицированный метод для преобразования ответов.
        
        Args:
            response: IntentResponse или IntentResult
            
        Returns:
            IntentResult
        """
        if isinstance(response, IntentResult):
            return response
        
        # Маппинг строковых значений complexity в enum
        complexity_map = {
            "simple": TaskComplexity.SIMPLE,
            "medium": TaskComplexity.MEDIUM,
            "complex": TaskComplexity.COMPLEX
        }
        
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
            "refactor": "Рефакторинг кода",
            "analyze": "Анализ проекта/кодовой базы"
        }
        
        # Конвертируем IntentResponse -> IntentResult
        intent_type = response.intent if isinstance(response.intent, str) else response.intent.value
        complexity = complexity_map.get(response.complexity, TaskComplexity.SIMPLE)
        
        return IntentResult(
            type=intent_type,
            confidence=max(self.MIN_CONFIDENCE, min(self.MAX_CONFIDENCE, response.confidence)),
            description=response.reasoning or descriptions.get(intent_type, "Выполнение задачи"),
            complexity=complexity
        )
    
    def _classify_legacy(self, query: str) -> IntentResult:
        """Legacy классификация через ручной парсинг JSON.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            IntentResult с типом, уверенностью и сложностью
        """
        prompt = self._get_prompt(query, is_structured=False)
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
            "refactor": "Рефакторинг кода",
            "analyze": "Анализ проекта/кодовой базы"
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
                    confidence=max(self.MIN_CONFIDENCE, min(self.MAX_CONFIDENCE, confidence)),
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
        
        # Ключевые слова для medium задач (включая технические объяснения)
        medium_keywords = [
            # Код и структуры
            'класс', 'class', 'модуль', 'module', 'api', 'endpoint',
            'crud', 'база данных', 'database', 'db', 'orm', 'auth',
            'парсер', 'parser', 'конвертер', 'converter', 'валидатор',
            'сервер', 'server', 'клиент', 'client', 'обработчик', 'handler',
            # Технические концепции для объяснений
            'async', 'await', 'asyncio', 'coroutine', 'thread', 'поток',
            'decorator', 'декоратор', 'generator', 'генератор', 'iterator',
            'metaclass', 'метакласс', 'descriptor', 'дескриптор',
            'context manager', 'менеджер контекста', 'with',
            'inheritance', 'наследован', 'polymorphism', 'полиморфизм',
            'solid', 'паттерн', 'pattern', 'design', 'дизайн',
            'memory', 'память', 'gc', 'garbage', 'сборщик мусора',
            'multiprocessing', 'многопоточн', 'concurrent', 'parallel'
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
    
    
    # Ключевые слова кода — если присутствуют, это НЕ приветствие
    CODE_KEYWORDS = frozenset([
        # Python
        "print", "def", "class", "import", "from", "return", "if", "else",
        "for", "while", "try", "except", "with", "async", "await", "lambda",
        # Общие
        "function", "const", "let", "var", "console", "log", "create", "add",
        "make", "build", "write", "code", "script", "program", "algorithm",
        # Русские команды
        "создай", "напиши", "сделай", "добавь", "выведи", "покажи"
    ])
    
    def _is_greeting(self, query: str) -> bool:
        """Проверяет, является ли запрос приветствием.
        
        Использует единую логику с is_greeting_fast, но с дополнительной проверкой
        на ключевые слова кода для более длинных запросов.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            True если это приветствие, False иначе
        """
        if not query:
            return False
        
        query_lower = query.strip().lower()
        words = query_lower.split()
        
        # Если есть ключевые слова кода — это НЕ приветствие
        for word in words:
            if word in self.CODE_KEYWORDS:
                return False
        
        # Для коротких запросов используем быструю проверку
        if len(words) <= 3:
            return self.is_greeting_fast(query)
        
        # Для длинных запросов проверяем начало фразы
        for greeting in self.GREETINGS:
            if query_lower.startswith(greeting + " "):
                return True
        
        return False
