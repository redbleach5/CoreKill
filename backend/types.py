"""Типы и модели данных для backend API.

Содержит Pydantic модели и Enum типы для всей системы.
Следует принципу единого источника истины для типов.
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class InteractionMode(str, Enum):
    """Режимы взаимодействия с системой.
    
    - auto: Автоматический выбор режима на основе анализа запроса
    - chat: Простой диалог с LLM без запуска workflow
    - plan: Только планирование и обсуждение без генерации кода
    - analyze: Анализ кода или задачи без генерации
    - code: Полный workflow генерации кода (TDD)
    """
    AUTO = "auto"
    CHAT = "chat"
    PLAN = "plan"
    ANALYZE = "analyze"
    CODE = "code"


class MessageRole(str, Enum):
    """Роли в диалоге."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Сообщение в диалоге."""
    id: str = Field(..., description="Уникальный ID сообщения")
    role: MessageRole = Field(..., description="Роль отправителя")
    content: str = Field(..., description="Текст сообщения")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Время отправки")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Дополнительные данные")
    
    class Config:
        use_enum_values = True


class ConversationContext(BaseModel):
    """Контекст диалога для передачи в LLM."""
    messages: List[Message] = Field(default_factory=list, description="История сообщений")
    summary: Optional[str] = Field(default=None, description="Суммаризация старых сообщений")
    total_messages: int = Field(default=0, description="Общее количество сообщений в сессии")
    
    def get_context_for_llm(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Возвращает контекст для LLM в формате messages.
        
        Args:
            max_messages: Максимальное количество последних сообщений
            
        Returns:
            Список сообщений в формате [{role, content}]
        """
        result = []
        
        # Добавляем суммаризацию как системное сообщение если есть
        if self.summary:
            result.append({
                "role": "system",
                "content": f"Краткое содержание предыдущего диалога:\n{self.summary}"
            })
        
        # Добавляем последние сообщения
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        for msg in recent:
            result.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return result


class TaskRequest(BaseModel):
    """Запрос на выполнение задачи."""
    task: str = Field(..., description="Текст задачи на русском или английском")
    mode: InteractionMode = Field(
        default=InteractionMode.AUTO, 
        description="Режим взаимодействия"
    )
    model: str = Field(default="", description="Модель Ollama (если пусто, выбирается автоматически)")
    temperature: float = Field(default=0.25, ge=0.1, le=0.7, description="Температура генерации")
    disable_web_search: bool = Field(default=False, description="Отключить веб-поиск")
    max_iterations: int = Field(default=3, ge=1, le=5, description="Максимальное количество итераций")
    conversation_id: Optional[str] = Field(default=None, description="ID диалога для сохранения контекста")
    
    class Config:
        use_enum_values = True


class SessionSettings(BaseModel):
    """Настройки сессии пользователя."""
    mode: InteractionMode = Field(default=InteractionMode.AUTO, description="Режим по умолчанию")
    auto_confirm: bool = Field(default=True, description="Автоматически запускать workflow без подтверждения")
    show_thinking: bool = Field(default=True, description="Показывать процесс 'размышления'")
    max_context_messages: int = Field(default=20, description="Максимум сообщений в контексте до суммаризации")
    
    class Config:
        use_enum_values = True


class IntentClassification(BaseModel):
    """Результат классификации намерения с рекомендацией режима."""
    intent_type: str = Field(..., description="Тип намерения (create, modify, debug, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность классификации")
    description: str = Field(..., description="Описание намерения")
    recommended_mode: InteractionMode = Field(..., description="Рекомендуемый режим работы")
    requires_code_generation: bool = Field(..., description="Требуется ли генерация кода")
    
    class Config:
        use_enum_values = True


class StreamQueryParams(BaseModel):
    """Валидация query параметров для /api/stream endpoint.
    
    Обеспечивает типизацию и валидацию всех параметров SSE стриминга.
    """
    task: str = Field(..., min_length=1, description="Текст задачи")
    mode: InteractionMode = Field(default=InteractionMode.AUTO, description="Режим взаимодействия")
    model: str = Field(default="", description="Модель Ollama (пусто = авто-выбор)")
    temperature: float = Field(default=0.25, ge=0.1, le=0.7, description="Температура генерации")
    disable_web_search: bool = Field(default=False, description="Отключить веб-поиск")
    max_iterations: int = Field(default=3, ge=1, le=5, description="Максимальное количество итераций")
    conversation_id: Optional[str] = Field(default=None, description="ID диалога для сохранения контекста")
    project_path: Optional[str] = Field(default=None, description="Путь к проекту для индексации")
    file_extensions: Optional[str] = Field(default=None, description="Расширения файлов через запятую (например: .py,.js)")
    
    class Config:
        use_enum_values = True


class IndexProjectRequest(BaseModel):
    """Запрос на индексацию проекта."""
    project_path: str = Field(..., min_length=1, description="Путь к корневой папке проекта")
    file_extensions: List[str] = Field(default_factory=lambda: [".py"], description="Список расширений файлов для индексации")
