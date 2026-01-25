"""Валидаторы для входных данных backend."""
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


# === Константы для валидации ===

# Максимальная длина промпта (архитектурный лимит)
MAX_PROMPT_LENGTH = 50000

# Подозрительные паттерны для prompt injection (архитектурная защита)
SUSPICIOUS_PATTERNS = [
    'ignore previous',
    'ignore all previous',
    'disregard',
    'disregard the above',
    'disregard all previous',
    'new instructions',
    'new instruction',
    'system:',
    'system override',
    'override',
    'forget all',
    'forget previous',
    'you are now',
    'you must now',
    'act as if',
    'pretend to be',
]

# Опасные паттерны в коде (базовая защита от code injection)
DANGEROUS_CODE_PATTERNS = [
    "eval(",
    "exec(",
    "__import__",
    "os.system",
    "subprocess",
]


# === Общие функции валидации ===

def validate_prompt(prompt: str) -> str:
    """Валидирует промпт на архитектурном уровне.
    
    Выполняет:
    - Проверку длины
    - Проверку на опасные паттерны в коде
    - Проверку на prompt injection паттерны
    
    Args:
        prompt: Текст промпта/задачи
        
    Returns:
        Валидированный текст (stripped)
        
    Raises:
        ValueError: Если промпт не валиден
    """
    if not prompt or not prompt.strip():
        raise ValueError("Промпт не может быть пустым")
    
    prompt_stripped = prompt.strip()
    
    # Проверка длины (архитектурный лимит)
    if len(prompt_stripped) > MAX_PROMPT_LENGTH:
        raise ValueError(
            f"Промпт слишком длинный: {len(prompt_stripped)} символов "
            f"(максимум {MAX_PROMPT_LENGTH})"
        )
    
    prompt_lower = prompt_stripped.lower()
    
    # Проверка на опасные паттерны в коде (базовая защита от code injection)
    for pattern in DANGEROUS_CODE_PATTERNS:
        if pattern in prompt_lower:
            raise ValueError(
                f"Промпт содержит опасный паттерн кода: '{pattern}'. "
                "Пожалуйста, опишите задачу на естественном языке."
            )
    
    # Проверка на prompt injection паттерны (архитектурная защита)
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern in prompt_lower:
            raise ValueError(
                f"Промпт содержит подозрительный паттерн: '{pattern}'. "
                "Пожалуйста, опишите задачу более ясно."
            )
    
    return prompt_stripped


class TaskRequestV2(BaseModel):
    """Валидированный запрос на выполнение задачи."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    task: str = Field(
        ...,
        min_length=1,
        max_length=MAX_PROMPT_LENGTH,
        description="Текст задачи на русском или английском"
    )
    model: str = Field(
        default="",
        max_length=200,
        description="Модель Ollama (если пусто, будет выбрана автоматически)"
    )
    temperature: float = Field(
        default=0.25,
        ge=0.1,
        le=0.7,
        description="Температура генерации"
    )
    disable_web_search: bool = Field(
        default=False,
        description="Отключить веб-поиск"
    )
    max_iterations: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Максимальное количество итераций"
    )
    
    @field_validator('task')
    @classmethod
    def validate_task(cls, v: str) -> str:
        """Валидирует текст задачи.
        
        Использует общую функцию validate_prompt() для архитектурной валидации.
        
        Args:
            v: Текст задачи
            
        Returns:
            Валидированный текст
            
        Raises:
            ValueError: Если текст не валиден
        """
        return validate_prompt(v)
    
    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Валидирует название модели.
        
        Args:
            v: Название модели
            
        Returns:
            Валидированное название
            
        Raises:
            ValueError: Если название не валидно
        """
        if not v:
            return ""
        
        # Модель должна содержать только буквы, цифры, двоеточие и дефис
        import re
        if not re.match(r'^[a-zA-Z0-9:\-_.]+$', v):
            raise ValueError("Название модели содержит недопустимые символы")
        
        return v.strip()


class FeedbackRequestV2(BaseModel):
    """Валидированный запрос на сохранение feedback."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    task: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Текст задачи"
    )
    task_id: Optional[str] = Field(
        None,
        max_length=100,
        description="ID задачи (если есть)"
    )
    feedback: str = Field(
        ...,
        description="Тип feedback: positive или negative"
    )
    
    @field_validator('feedback')
    @classmethod
    def validate_feedback(cls, v: str) -> str:
        """Валидирует тип feedback.
        
        Args:
            v: Тип feedback
            
        Returns:
            Валидированный тип
            
        Raises:
            ValueError: Если тип не валиден
        """
        if v not in ["positive", "negative"]:
            raise ValueError("feedback должен быть 'positive' или 'negative'")
        
        return v.lower()
