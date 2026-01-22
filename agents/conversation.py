"""ConversationMemory для управления историей диалога.

Хранит историю сообщений с автоматической суммаризацией
при превышении лимита контекста.
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import uuid
import json
from pathlib import Path
from infrastructure.local_llm import LocalLLM
from utils.logger import get_logger
from utils.config import get_config


logger = get_logger()


def _ensure_utc(dt: datetime) -> datetime:
    """Нормализует datetime в timezone-aware UTC.

    Старые сохранённые диалоги могут содержать naive datetime (без tzinfo).
    Для корректной работы TTL/сортировки приводим их к UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class ConversationMessage:
    """Сообщение в диалоге."""
    id: str
    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует в словарь."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMessage':
        """Создаёт из словаря."""
        return cls(
            id=data["id"],
            role=data["role"],
            content=data["content"],
            timestamp=_ensure_utc(datetime.fromisoformat(data["timestamp"])),
            metadata=data.get("metadata")
        )


@dataclass
class Conversation:
    """Диалог с историей сообщений."""
    id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    summary: Optional[str] = None
    summarized_count: int = 0  # Сколько сообщений суммаризировано
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None
    
    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationMessage:
        """Добавляет сообщение в диалог.
        
        Args:
            role: Роль (user/assistant/system)
            content: Текст сообщения
            metadata: Дополнительные данные
            
        Returns:
            Добавленное сообщение
        """
        message = ConversationMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata
        )
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)
        return message
    
    def get_recent_messages(self, count: int = 10) -> List[ConversationMessage]:
        """Возвращает последние сообщения.
        
        Args:
            count: Количество сообщений
            
        Returns:
            Список последних сообщений
        """
        return self.messages[-count:] if len(self.messages) > count else self.messages
    
    def get_context_for_llm(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Возвращает контекст для LLM.
        
        Args:
            max_messages: Максимум сообщений (не считая суммаризации)
            
        Returns:
            Список сообщений в формате [{role, content}]
        """
        result = []
        
        # Добавляем суммаризацию если есть
        if self.summary:
            result.append({
                "role": "system",
                "content": f"Краткое содержание предыдущего диалога:\n{self.summary}"
            })
        
        # Добавляем последние сообщения
        recent = self.get_recent_messages(max_messages)
        for msg in recent:
            result.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует в словарь для сериализации."""
        return {
            "id": self.id,
            "messages": [m.to_dict() for m in self.messages],
            "summary": self.summary,
            "summarized_count": self.summarized_count,
            "created_at": _ensure_utc(self.created_at).isoformat(),
            "updated_at": _ensure_utc(self.updated_at).isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Conversation':
        """Создаёт из словаря."""
        return cls(
            id=data["id"],
            messages=[ConversationMessage.from_dict(m) for m in data.get("messages", [])],
            summary=data.get("summary"),
            summarized_count=data.get("summarized_count", 0),
            created_at=_ensure_utc(datetime.fromisoformat(data["created_at"])),
            updated_at=_ensure_utc(datetime.fromisoformat(data["updated_at"])),
            metadata=data.get("metadata")
        )


class ConversationMemory:
    """Менеджер истории диалогов с суммаризацией.
    
    Функции:
    - Хранение истории сообщений по conversation_id
    - Автоматическая суммаризация при превышении лимита
    - Персистентность на диск (опционально)
    - Получение контекста для LLM
    - TTL для автоочистки старых диалогов
    - Лимит на количество диалогов в памяти
    """
    
    SUMMARIZATION_PROMPT = """Суммаризируй следующий диалог, сохранив ключевую информацию.

Важно сохранить:
- Основную тему/задачу обсуждения
- Принятые решения и их причины
- Важные детали реализации (имена функций, классов, файлов)
- Проблемы, которые были решены
- Планы на будущее (если есть)

Диалог:
{conversation}

Краткое содержание (2-4 предложения, сохрани технические детали):"""
    
    # Лимиты по умолчанию
    DEFAULT_MAX_CONVERSATIONS = 100  # Максимум диалогов в памяти
    DEFAULT_TTL_HOURS = 72  # Время жизни неактивного диалога в часах
    
    def __init__(
        self,
        max_messages_before_summary: int = 20,
        persist_dir: Optional[str] = None,
        summarization_model: Optional[str] = None,
        max_conversations: int = DEFAULT_MAX_CONVERSATIONS,
        ttl_hours: int = DEFAULT_TTL_HOURS
    ):
        """Инициализирует ConversationMemory.
        
        Args:
            max_messages_before_summary: Лимит сообщений до суммаризации
            persist_dir: Директория для сохранения (None = без персистентности)
            summarization_model: Модель для суммаризации (None = auto)
            max_conversations: Максимальное количество диалогов в памяти
            ttl_hours: Время жизни неактивного диалога в часах
        """
        self.max_messages = max_messages_before_summary
        self.persist_dir = Path(persist_dir) if persist_dir else None
        self.conversations: Dict[str, Conversation] = {}
        self._llm: Optional[LocalLLM] = None
        self._summarization_model = summarization_model
        self.max_conversations = max_conversations
        self.ttl_hours = ttl_hours
        
        # Создаём директорию если нужно
        if self.persist_dir:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._load_conversations()
        
        # Очищаем просроченные диалоги при старте
        self._cleanup_expired()
        
        logger.info(
            f"✅ ConversationMemory инициализирован "
            f"(лимит: {max_messages_before_summary} сообщений, "
            f"макс. диалогов: {max_conversations}, TTL: {ttl_hours}ч)"
        )
    
    def _get_llm(self) -> LocalLLM:
        """Ленивая инициализация LLM для суммаризации."""
        if self._llm is None:
            model = self._summarization_model or "qwen2.5-coder:7b"
            self._llm = LocalLLM(model=model, temperature=0.1)
        return self._llm
    
    def get_or_create_conversation(self, conversation_id: Optional[str] = None) -> Conversation:
        """Получает существующий или создаёт новый диалог.
        
        Args:
            conversation_id: ID диалога (None = создать новый)
            
        Returns:
            Объект Conversation
        """
        if conversation_id and conversation_id in self.conversations:
            return self.conversations[conversation_id]
        
        # Проверяем лимит перед созданием нового диалога
        self._enforce_limit()
        
        # Создаём новый диалог
        new_id = conversation_id or str(uuid.uuid4())
        conversation = Conversation(id=new_id)
        self.conversations[new_id] = conversation
        
        logger.info(f"📝 Создан новый диалог: {new_id}")
        return conversation
    
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        auto_summarize: bool = True
    ) -> ConversationMessage:
        """Добавляет сообщение в диалог.
        
        Args:
            conversation_id: ID диалога
            role: Роль (user/assistant/system)
            content: Текст сообщения
            metadata: Дополнительные данные
            auto_summarize: Автоматически суммаризировать при превышении лимита
            
        Returns:
            Добавленное сообщение
        """
        conversation = self.get_or_create_conversation(conversation_id)
        message = conversation.add_message(role, content, metadata)
        
        # Проверяем нужна ли суммаризация
        unsummarized = len(conversation.messages) - conversation.summarized_count
        if auto_summarize and unsummarized > self.max_messages:
            self._summarize_conversation(conversation)
        
        # Сохраняем на диск
        if self.persist_dir:
            self._save_conversation(conversation)
        
        return message
    
    def get_context(
        self,
        conversation_id: str,
        max_messages: int = 10
    ) -> List[Dict[str, str]]:
        """Получает контекст диалога для LLM.
        
        Args:
            conversation_id: ID диалога
            max_messages: Максимум последних сообщений
            
        Returns:
            Контекст в формате [{role, content}]
        """
        if conversation_id not in self.conversations:
            return []
        
        return self.conversations[conversation_id].get_context_for_llm(max_messages)
    
    def _summarize_conversation(self, conversation: Conversation) -> None:
        """Суммаризирует старые сообщения в диалоге.
        
        Args:
            conversation: Диалог для суммаризации
        """
        # Получаем сообщения для суммаризации (оставляем последние max_messages/2)
        keep_count = self.max_messages // 2
        to_summarize = conversation.messages[:-keep_count] if len(conversation.messages) > keep_count else []
        
        if not to_summarize:
            return
        
        # Формируем текст для суммаризации
        conversation_text = "\n".join([
            f"{m.role}: {m.content}" for m in to_summarize
        ])
        
        # Добавляем предыдущую суммаризацию если есть
        if conversation.summary:
            conversation_text = f"Предыдущая суммаризация: {conversation.summary}\n\n{conversation_text}"
        
        prompt = self.SUMMARIZATION_PROMPT.format(conversation=conversation_text)
        
        try:
            llm = self._get_llm()
            summary = llm.generate(prompt, num_predict=256)
            
            # Обновляем диалог
            conversation.summary = summary.strip()
            conversation.summarized_count = len(conversation.messages) - keep_count
            
            logger.info(f"📋 Диалог {conversation.id} суммаризирован ({conversation.summarized_count} сообщений)")
            
        except Exception as e:
            logger.error(f"❌ Ошибка суммаризации: {e}", error=e)
    
    def _save_conversation(self, conversation: Conversation) -> None:
        """Сохраняет диалог на диск.
        
        Args:
            conversation: Диалог для сохранения
        """
        if not self.persist_dir:
            return
        
        filepath = self.persist_dir / f"{conversation.id}.json"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(conversation.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения диалога: {e}", error=e)
    
    def _load_conversations(self) -> None:
        """Загружает диалоги с диска."""
        if not self.persist_dir or not self.persist_dir.exists():
            return
        
        for filepath in self.persist_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                conversation = Conversation.from_dict(data)
                self.conversations[conversation.id] = conversation
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки диалога {filepath}: {e}")
        
        logger.info(f"📂 Загружено {len(self.conversations)} диалогов")
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Удаляет диалог.
        
        Args:
            conversation_id: ID диалога
            
        Returns:
            True если удалён успешно
        """
        if conversation_id not in self.conversations:
            return False
        
        del self.conversations[conversation_id]
        
        # Удаляем файл
        if self.persist_dir:
            filepath = self.persist_dir / f"{conversation_id}.json"
            if filepath.exists():
                filepath.unlink()
        
        logger.info(f"🗑️ Диалог {conversation_id} удалён")
        return True
    
    def clear_all(self) -> None:
        """Очищает все диалоги."""
        self.conversations.clear()
        
        if self.persist_dir:
            for filepath in self.persist_dir.glob("*.json"):
                filepath.unlink()
        
        logger.info("🗑️ Все диалоги очищены")
    
    def _cleanup_expired(self) -> int:
        """Удаляет просроченные диалоги по TTL.
        
        Returns:
            Количество удалённых диалогов
        """
        now = datetime.now(timezone.utc)
        ttl_delta = timedelta(hours=self.ttl_hours)
        expired_ids = []
        
        for conv_id, conv in self.conversations.items():
            if now - conv.updated_at > ttl_delta:
                expired_ids.append(conv_id)
        
        for conv_id in expired_ids:
            self.delete_conversation(conv_id)
        
        if expired_ids:
            logger.info(f"🗑️ Удалено {len(expired_ids)} просроченных диалогов (TTL: {self.ttl_hours}ч)")
        
        return len(expired_ids)
    
    def _enforce_limit(self) -> int:
        """Удаляет самые старые диалоги при превышении лимита.
        
        Returns:
            Количество удалённых диалогов
        """
        if len(self.conversations) <= self.max_conversations:
            return 0
        
        # Сортируем по времени обновления (старые первые)
        sorted_convs = sorted(
            self.conversations.items(),
            key=lambda x: x[1].updated_at
        )
        
        # Удаляем самые старые
        to_remove = len(self.conversations) - self.max_conversations
        removed = 0
        
        for conv_id, _ in sorted_convs[:to_remove]:
            if self.delete_conversation(conv_id):
                removed += 1
        
        if removed:
            logger.info(f"🗑️ Удалено {removed} диалогов (превышен лимит {self.max_conversations})")
        
        return removed
    
    def cleanup(self) -> Dict[str, int]:
        """Выполняет полную очистку: TTL + лимит.
        
        Returns:
            Словарь с количеством удалённых диалогов по причине
        """
        expired = self._cleanup_expired()
        over_limit = self._enforce_limit()
        
        return {
            "expired": expired,
            "over_limit": over_limit,
            "total": expired + over_limit
        }


# Singleton
_conversation_memory: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    """Возвращает singleton экземпляр ConversationMemory.
    
    Returns:
        Экземпляр ConversationMemory
    """
    global _conversation_memory
    if _conversation_memory is None:
        config = get_config()
        persist_dir = Path(config.output_dir) / "conversations"
        _conversation_memory = ConversationMemory(
            max_messages_before_summary=20,
            persist_dir=str(persist_dir)
        )
    return _conversation_memory


def reset_conversation_memory() -> None:
    """Сбрасывает singleton ConversationMemory."""
    global _conversation_memory
    _conversation_memory = None
    logger.info("🔄 ConversationMemory сброшен")
