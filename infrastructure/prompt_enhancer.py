"""Сервис для динамического улучшения промптов через LLM.

Многоуровневый анализ запроса пользователя с несколькими проходами LLM:
1. Понимание намерения и контекста
2. Уточнение и расширение требований  
3. Генерация детального технического задания
4. Создание оптимизированного промпта

При наличии локальных LLM можем позволить себе несколько вызовов
для достижения качественного результата.
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from infrastructure.local_llm import LocalLLM
from infrastructure.model_router import get_model_router
from utils.logger import get_logger


logger = get_logger()


@dataclass
class TaskUnderstanding:
    """Глубокое понимание задачи после многоуровневого анализа."""
    original_query: str
    interpreted_query: str  # Как система поняла запрос
    task_type: str  # function/class/module/script/api/cli/etc
    domain: str  # web/data/ml/automation/game/etc
    requirements: List[str] = field(default_factory=list)
    inputs: List[Dict[str, str]] = field(default_factory=list)  # name, type, description
    outputs: Dict[str, str] = field(default_factory=dict)  # type, description
    constraints: List[str] = field(default_factory=list)
    edge_cases: List[str] = field(default_factory=list)
    examples: List[Dict[str, Any]] = field(default_factory=list)  # input, expected_output
    suggested_name: str = ""
    complexity: str = "medium"
    language: str = "ru"


@dataclass
class EnhancedPrompt:
    """Результат улучшения промпта."""
    original_query: str
    enhanced_prompt: str
    extracted_requirements: List[str]
    suggested_approach: str
    language: str  # ru/en
    complexity: str  # simple/medium/complex


class PromptEnhancer:
    """Сервис многоуровневого анализа и улучшения промптов.
    
    Использует несколько проходов LLM для глубокого понимания задачи:
    
    Уровень 1: Интерпретация
    - Понять что пользователь имел в виду
    - Исправить опечатки, транслитерацию, сленг
    - Определить домен и тип задачи
    
    Уровень 2: Расширение
    - Извлечь явные и неявные требования
    - Определить входы/выходы
    - Предложить edge cases
    
    Уровень 3: Спецификация
    - Создать детальное техническое задание
    - Предложить примеры использования
    - Определить ограничения
    
    Уровень 4: Промпт
    - Сгенерировать оптимальный промпт для кодогенерации
    """
    
    def __init__(self, model: Optional[str] = None, temperature: float = 0.3) -> None:
        """Инициализация улучшителя промптов.
        
        Args:
            model: Модель для анализа (если None, выбирается автоматически)
            temperature: Температура генерации
        """
        if model is None:
            router = get_model_router()
            model_selection = router.select_model(
                task_type="intent",  # Используем быструю модель для анализа
                preferred_model=None,
                context={"agent": "prompt_enhancer"}
            )
            model = model_selection.model
        
        self.llm = LocalLLM(
            model=model,
            temperature=temperature,
            top_p=0.9
        )
        
        # Кэш для понимания задач
        self._understanding_cache: Dict[str, TaskUnderstanding] = {}
        
        # Кэш для похожих запросов
        self._cache: Dict[str, EnhancedPrompt] = {}
    
    def deep_understand(self, user_query: str, intent_type: str) -> TaskUnderstanding:
        """Многоуровневый анализ запроса для глубокого понимания задачи.
        
        Выполняет 3 прохода LLM:
        1. Интерпретация - понять что пользователь имел в виду
        2. Расширение - извлечь все требования
        3. Спецификация - создать детальное ТЗ
        
        Args:
            user_query: Оригинальный запрос пользователя
            intent_type: Тип намерения
            
        Returns:
            TaskUnderstanding с полным пониманием задачи
        """
        cache_key = f"{intent_type}:{user_query}"
        if cache_key in self._understanding_cache:
            logger.info("📋 Используем кэшированное понимание задачи")
            return self._understanding_cache[cache_key]
        
        logger.info(f"🧠 Многоуровневый анализ запроса: {user_query[:50]}...")
        
        # === УРОВЕНЬ 1: Интерпретация ===
        interpreted = self._level1_interpret(user_query)
        logger.info(f"  L1 Интерпретация: {interpreted[:80]}...")
        
        # === УРОВЕНЬ 2: Расширение требований ===
        requirements = self._level2_expand(user_query, interpreted, intent_type)
        logger.info(f"  L2 Требований: {len(requirements.get('requirements', []))}")
        
        # === УРОВЕНЬ 3: Спецификация ===
        spec = self._level3_specify(user_query, interpreted, requirements)
        logger.info(f"  L3 Примеров: {len(spec.get('examples', []))}")
        
        # Собираем результат
        understanding = TaskUnderstanding(
            original_query=user_query,
            interpreted_query=interpreted,
            task_type=requirements.get("task_type", "function"),
            domain=requirements.get("domain", "general"),
            requirements=requirements.get("requirements", []),
            inputs=spec.get("inputs", []),
            outputs=spec.get("outputs", {}),
            constraints=requirements.get("constraints", []),
            edge_cases=spec.get("edge_cases", []),
            examples=spec.get("examples", []),
            suggested_name=spec.get("function_name", "main_function"),
            complexity=requirements.get("complexity", "medium"),
            language=self._detect_language(user_query)
        )
        
        self._understanding_cache[cache_key] = understanding
        return understanding
    
    def _level1_interpret(self, query: str) -> str:
        """Уровень 1: Интерпретация запроса.
        
        Понимает что пользователь имел в виду, исправляет:
        - Опечатки
        - Транслитерацию (ghbdtn -> привет)
        - Сленг и сокращения
        - Неоднозначности
        """
        # Сначала пробуем автоматическую конвертацию раскладки
        converted = self._try_keyboard_layout_fix(query)
        
        layout_hint = ""
        if converted != query:
            layout_hint = f"""
IMPORTANT: The text "{query}" appears to be typed in wrong keyboard layout.
When converted from English to Russian keyboard layout: "{converted}"
"""
        
        prompt = f"""You are an expert at understanding user intent for a CODE GENERATION system. 
The user is asking you to GENERATE CODE, not just interpret text.

User request: "{query}"
{layout_hint}
KEYBOARD LAYOUT REFERENCE (English -> Russian):
q=й w=ц e=у r=к t=е y=н u=г i=ш o=щ p=з
a=ф s=ы d=в f=а g=п h=р j=о k=л l=д
z=я x=ч c=с v=м b=и n=т m=ь

Common patterns:
- "ghbdtn" = "привет" (hello)  
- "cjplf" = "создай" (create)
- "yfgbib" = "напиши" (write)
- "ntcn" = "тест" (test)
- "aeyrwbz" = "функция" (function)

TASK: Determine what CODE the user wants you to generate.
If the input seems like random letters, it's probably wrong keyboard layout - convert it.
If it's a greeting like "привет/hello", the user wants to see a demo or greeting response.
If it's a command like "создай/напиши X", they want code that does X.

Answer in 1-2 sentences. Be SPECIFIC about what code to generate:"""

        response = self.llm.generate(prompt, num_predict=256)
        return response.strip()
    
    def _try_keyboard_layout_fix(self, text: str) -> str:
        """Пытается исправить текст, набранный в неправильной раскладке.
        
        Args:
            text: Текст для проверки
            
        Returns:
            Исправленный текст или оригинал
        """
        # Таблица соответствия EN -> RU
        en_to_ru = {
            'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 
            'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з', '[': 'х', ']': 'ъ',
            'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 
            'j': 'о', 'k': 'л', 'l': 'д', ';': 'ж', "'": 'э',
            'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 
            'm': 'ь', ',': 'б', '.': 'ю', '/': '.',
            '`': 'ё', '~': 'Ё'
        }
        
        # Добавляем заглавные
        en_to_ru_upper = {k.upper(): v.upper() for k, v in en_to_ru.items() if k.isalpha()}
        en_to_ru.update(en_to_ru_upper)
        
        # Проверяем: если текст содержит только английские буквы, пробуем конвертировать
        if text and all(c in en_to_ru or c.isspace() or c.isdigit() for c in text):
            converted = ''.join(en_to_ru.get(c, c) for c in text)
            return converted
        
        return text
    
    def _level2_expand(self, original: str, interpreted: str, intent_type: str) -> Dict[str, Any]:
        """Уровень 2: Расширение требований.
        
        Извлекает явные и неявные требования из интерпретированного запроса.
        """
        prompt = f"""Based on this user request and its interpretation, extract detailed requirements.

Original request: "{original}"
Interpreted as: "{interpreted}"
Task type: {intent_type}

Respond in JSON:
{{
    "task_type": "function|class|module|script|api|cli",
    "domain": "web|data|ml|automation|game|utility|text|math",
    "requirements": [
        "Specific requirement 1",
        "Specific requirement 2",
        "..."
    ],
    "constraints": [
        "Performance constraint",
        "Memory constraint",
        "..."
    ],
    "complexity": "simple|medium|complex"
}}

Be specific and practical. Extract ALL implicit requirements.
JSON:"""

        response = self.llm.generate(prompt, num_predict=512)
        return self._parse_json_response(response, {
            "task_type": "function",
            "domain": "utility",
            "requirements": [interpreted],
            "constraints": [],
            "complexity": "medium"
        })
    
    def _level3_specify(self, original: str, interpreted: str, requirements: Dict) -> Dict[str, Any]:
        """Уровень 3: Детальная спецификация.
        
        Создаёт полное техническое задание с примерами.
        """
        reqs_str = "\n".join(f"- {r}" for r in requirements.get("requirements", []))
        
        prompt = f"""Create a detailed technical specification for this task.

Original request: "{original}"
Interpreted as: "{interpreted}"
Task type: {requirements.get('task_type', 'function')}
Domain: {requirements.get('domain', 'utility')}
Requirements:
{reqs_str}

Respond in JSON:
{{
    "function_name": "snake_case_name",
    "inputs": [
        {{"name": "param1", "type": "str", "description": "..."}}
    ],
    "outputs": {{"type": "str", "description": "..."}},
    "edge_cases": [
        "Empty input",
        "Invalid input type",
        "..."
    ],
    "examples": [
        {{"input": "example_value", "output": "expected_result", "description": "..."}},
        {{"input": "", "output": "...", "description": "Edge case: empty"}}
    ]
}}

Be practical and realistic. Include 2-4 examples.
JSON:"""

        response = self.llm.generate(prompt, num_predict=768)
        return self._parse_json_response(response, {
            "function_name": "process_data",
            "inputs": [{"name": "data", "type": "Any", "description": "Input data"}],
            "outputs": {"type": "Any", "description": "Processed result"},
            "edge_cases": ["empty input", "invalid type"],
            "examples": []
        })
    
    def _parse_json_response(self, response: str, fallback: Dict) -> Dict[str, Any]:
        """Безопасный парсинг JSON из ответа LLM."""
        import json
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(response[start:end])
                
                # Валидируем и нормализуем поля
                if "task_type" in result:
                    valid_types = ["function", "class", "module", "script", "api", "cli"]
                    if result["task_type"] not in valid_types:
                        # Берём первый валидный тип если LLM вернула несколько
                        for vt in valid_types:
                            if vt in str(result["task_type"]).lower():
                                result["task_type"] = vt
                                break
                        else:
                            result["task_type"] = "function"
                
                if "complexity" in result:
                    valid_complexity = ["simple", "medium", "complex"]
                    if result["complexity"] not in valid_complexity:
                        result["complexity"] = "medium"
                
                return result
        except (json.JSONDecodeError, ValueError):
            pass
        return fallback
    
    def enhance_for_coding(
        self,
        user_query: str,
        intent_type: str,
        plan: str = "",
        tests: str = "",
        context: str = ""
    ) -> str:
        """Создаёт улучшенный промпт для генерации кода.
        
        Использует многоуровневый анализ для глубокого понимания задачи.
        
        Args:
            user_query: Оригинальный запрос пользователя
            intent_type: Тип намерения (create/modify/debug/etc)
            plan: План реализации (если есть)
            tests: Сгенерированные тесты (если есть)
            context: Дополнительный контекст
            
        Returns:
            Оптимизированный промпт для генерации кода
        """
        logger.info(f"🔧 Глубокий анализ задачи: {user_query[:50]}...")
        
        # Многоуровневый анализ
        understanding = self.deep_understand(user_query, intent_type)
        
        # Строим улучшенный промпт на основе глубокого понимания
        enhanced = self._build_deep_code_prompt(
            understanding=understanding,
            plan=plan,
            tests=tests,
            context=context
        )
        
        logger.info(f"✅ Промпт создан (требований: {len(understanding.requirements)}, примеров: {len(understanding.examples)})")
        
        return enhanced
    
    def _build_deep_code_prompt(
        self,
        understanding: TaskUnderstanding,
        plan: str,
        tests: str,
        context: str
    ) -> str:
        """Строит промпт на основе глубокого понимания задачи."""
        
        # Секция требований
        reqs_section = ""
        if understanding.requirements:
            reqs_list = "\n".join(f"  - {r}" for r in understanding.requirements)
            reqs_section = f"""
REQUIREMENTS:
{reqs_list}
"""
        
        # Секция входов/выходов
        io_section = ""
        if understanding.inputs:
            inputs_str = "\n".join(
                f"  - {inp.get('name', 'arg')}: {inp.get('type', 'Any')} - {inp.get('description', '')}"
                for inp in understanding.inputs
            )
            outputs_str = f"{understanding.outputs.get('type', 'Any')} - {understanding.outputs.get('description', '')}"
            io_section = f"""
FUNCTION SIGNATURE:
  Name: {understanding.suggested_name}
  Inputs:
{inputs_str}
  Output: {outputs_str}
"""
        
        # Секция примеров
        examples_section = ""
        if understanding.examples:
            examples_str = "\n".join(
                f"  {i+1}. {understanding.suggested_name}({ex.get('input', '')}) -> {ex.get('output', '')}  # {ex.get('description', '')}"
                for i, ex in enumerate(understanding.examples)
            )
            examples_section = f"""
EXAMPLES:
{examples_str}
"""
        
        # Секция edge cases
        edge_cases_section = ""
        if understanding.edge_cases:
            edge_str = "\n".join(f"  - {ec}" for ec in understanding.edge_cases)
            edge_cases_section = f"""
EDGE CASES TO HANDLE:
{edge_str}
"""
        
        # Секция тестов
        tests_section = ""
        if tests.strip():
            tests_section = f"""
TESTS THE CODE MUST PASS:
```python
{tests}
```
"""
        
        # Секция плана
        plan_section = ""
        if plan.strip():
            plan_section = f"""
IMPLEMENTATION PLAN:
{plan}
"""
        
        # Секция контекста
        context_section = ""
        if context.strip():
            context_section = f"""
CONTEXT:
{context}
"""
        
        # Определяем язык документации
        lang_instruction = "Docstrings на русском языке." if understanding.language == "ru" else "Docstrings in English."
        
        prompt = f"""You are an expert Python developer. Generate production-ready code based on the detailed specification below.

ORIGINAL REQUEST: "{understanding.original_query}"
INTERPRETED AS: "{understanding.interpreted_query}"

TASK TYPE: {understanding.task_type}
DOMAIN: {understanding.domain}
COMPLEXITY: {understanding.complexity}
{reqs_section}{io_section}{examples_section}{edge_cases_section}{plan_section}{tests_section}{context_section}
CODE REQUIREMENTS:
1. Python 3.10+ with full type hints
2. Comprehensive docstrings ({lang_instruction})
3. Handle ALL edge cases listed above
4. Make examples work exactly as specified
5. Follow PEP8, use snake_case
6. Include proper error handling
7. Make code production-ready

OUTPUT ONLY THE PYTHON CODE. No markdown, no explanations. Start with imports or def.

Code:
"""
        return prompt
    
    def enhance_for_tests(
        self,
        user_query: str,
        intent_type: str,
        context: str = ""
    ) -> str:
        """Создаёт улучшенный промпт для генерации тестов.
        
        Использует многоуровневый анализ для понимания что тестировать.
        
        Args:
            user_query: Оригинальный запрос пользователя
            intent_type: Тип намерения
            context: Дополнительный контекст
            
        Returns:
            Оптимизированный промпт для генерации тестов
        """
        # Используем глубокое понимание задачи
        understanding = self.deep_understand(user_query, intent_type)
        
        return self._build_deep_test_prompt(
            understanding=understanding,
            context=context
        )
    
    def _build_deep_test_prompt(
        self,
        understanding: TaskUnderstanding,
        context: str
    ) -> str:
        """Строит промпт для тестов на основе глубокого понимания."""
        
        # Секция требований
        reqs_section = ""
        if understanding.requirements:
            reqs_list = "\n".join(f"  - {r}" for r in understanding.requirements)
            reqs_section = f"""
REQUIREMENTS TO TEST:
{reqs_list}
"""
        
        # Секция примеров как тест-кейсов
        examples_section = ""
        if understanding.examples:
            examples_str = "\n".join(
                f"  - Input: {ex.get('input', '')} -> Expected: {ex.get('output', '')}  ({ex.get('description', '')})"
                for ex in understanding.examples
            )
            examples_section = f"""
EXAMPLE TEST CASES:
{examples_str}
"""
        
        # Секция edge cases
        edge_cases_section = ""
        if understanding.edge_cases:
            edge_str = "\n".join(f"  - {ec}" for ec in understanding.edge_cases)
            edge_cases_section = f"""
EDGE CASES TO TEST:
{edge_str}
"""
        
        # Секция входов/выходов
        io_section = ""
        if understanding.inputs:
            inputs_str = ", ".join(
                f"{inp.get('name', 'arg')}: {inp.get('type', 'Any')}"
                for inp in understanding.inputs
            )
            io_section = f"""
FUNCTION TO TEST:
  {understanding.suggested_name}({inputs_str}) -> {understanding.outputs.get('type', 'Any')}
"""
        
        context_section = ""
        if context.strip():
            context_section = f"""
CONTEXT:
{context}
"""
        
        # Определяем способ вывода на основе анализа
        output_type = understanding.outputs.get('type', 'Any') if understanding.outputs else 'Any'
        output_method = understanding.outputs.get('method', 'return') if understanding.outputs else 'return'
        
        # Инструкции по способу тестирования в зависимости от типа вывода
        testing_strategy = ""
        if output_method == "print" or "print" in understanding.interpreted_query.lower() or "вывод" in understanding.interpreted_query.lower():
            testing_strategy = """
CRITICAL: This function uses print() for output (no return value).
To test print() output, use pytest's capsys fixture:

def test_example(capsys):
    function_name()  # Call the function
    captured = capsys.readouterr()
    assert "expected text" in captured.out
"""
        elif output_method == "file":
            testing_strategy = """
CRITICAL: This function writes to a file.
Use tmp_path fixture to test file operations:

def test_example(tmp_path):
    output_file = tmp_path / "output.txt"
    function_name(output_file)
    assert output_file.read_text() == "expected content"
"""
        else:
            testing_strategy = """
This function returns a value. Test the return value directly:

def test_example():
    result = function_name(args)
    assert result == expected_value
"""

        prompt = f"""You are an expert Python test engineer. Generate comprehensive pytest tests.

ORIGINAL REQUEST: "{understanding.original_query}"
INTERPRETED AS: "{understanding.interpreted_query}"

TASK TYPE: {understanding.task_type}
DOMAIN: {understanding.domain}
{io_section}{reqs_section}{examples_section}{edge_cases_section}{context_section}
{testing_strategy}
TEST REQUIREMENTS:
1. Use pytest framework (import pytest)
2. Test function named `{understanding.suggested_name}`
3. ANALYZE how the function produces output and use correct testing method:
   - If print() is used → use capsys.readouterr()
   - If return value → assert on return
   - If modifies object → assert on object state
4. Include happy path tests
5. Include edge case tests
6. Use descriptive names: test_{understanding.suggested_name}_<scenario>
7. DO NOT use @pytest.mark.parametrize unless truly needed
8. Tests should be independent and ready to run

OUTPUT ONLY THE PYTHON TEST CODE. No markdown, no explanations.

Tests:
"""
        return prompt
    
    
    def _detect_language(self, text: str) -> str:
        """Определяет язык текста.
        
        Args:
            text: Текст для анализа
            
        Returns:
            'ru' или 'en'
        """
        from utils.helpers import detect_language
        return detect_language(text)
    


# Singleton instance
_prompt_enhancer: Optional[PromptEnhancer] = None


def get_prompt_enhancer() -> PromptEnhancer:
    """Возвращает singleton экземпляр PromptEnhancer.
    
    Returns:
        PromptEnhancer instance
    """
    global _prompt_enhancer
    if _prompt_enhancer is None:
        _prompt_enhancer = PromptEnhancer()
    return _prompt_enhancer
