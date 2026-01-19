"""Валидаторы для входных данных backend."""
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class TaskRequestV2(BaseModel):
    """Валидированный запрос на выполнение задачи."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    task: str = Field(
        ...,
        min_length=1,
        max_length=10000,
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
        
        Args:
            v: Текст задачи
            
        Returns:
            Валидированный текст
            
        Raises:
            ValueError: Если текст не валиден
        """
        if not v or not v.strip():
            raise ValueError("Задача не может быть пустой")
        
        # Проверяем на опасные паттерны (базовая защита от injection)
        dangerous_patterns = [
            "eval(",
            "exec(",
            "__import__",
            "os.system",
            "subprocess",
        ]
        
        task_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in task_lower:
                raise ValueError(f"Задача содержит опасный паттерн: {pattern}")
        
        return v.strip()
    
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
