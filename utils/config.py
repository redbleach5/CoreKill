"""Загрузка конфигурации из config.toml."""
from pathlib import Path
from typing import Optional
import sys
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]  # Fallback для Python < 3.11

from utils.logger import get_logger


logger = get_logger()


class Config:
    """Класс для загрузки и хранения конфигурации."""
    
    _instance: Optional['Config'] = None
    _config_data: dict = {}
    
    def __new__(cls) -> 'Config':
        """Singleton паттерн."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def reload(self) -> None:
        """Перезагружает конфигурацию из config.toml."""
        self._load_config()
        logger.info("🔄 Конфигурация перезагружена")
    
    def _load_config(self) -> None:
        """Загружает конфигурацию из config.toml."""
        config_path = Path(__file__).parent.parent / "config.toml"
        
        if not config_path.exists():
            # Используем значения по умолчанию
            self._config_data = {
                "default": {
                    "default_model": "codellama:13b-instruct-q4_0",
                    "max_iterations": 5,
                    "enable_web": True,
                    "temperature": 0.25,
                    "max_tokens_warning": 30000,
                    "output_dir": "output"
                }
            }
            return
        
        try:
            with open(config_path, "rb") as f:
                self._config_data = tomllib.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки config.toml: {e}, используются значения по умолчанию", error=e)
            self._config_data = {
                "default": {
                    "default_model": "codellama:13b-instruct-q4_0",
                    "max_iterations": 5,
                    "enable_web": True,
                    "temperature": 0.25,
                    "max_tokens_warning": 30000,
                    "output_dir": "output"
                }
            }
    
    # === Ollama Connection ===
    
    @property
    def ollama_host(self) -> str:
        """Хост Ollama API."""
        return self._config_data.get("ollama", {}).get("host", "http://localhost:11434")
    
    @property
    def ollama_connect_timeout(self) -> int:
        """Таймаут подключения к Ollama."""
        return self._config_data.get("ollama", {}).get("connect_timeout", 10)
    
    @property
    def ollama_use_remote(self) -> bool:
        """Использовать удалённый Ollama."""
        return self._config_data.get("ollama", {}).get("use_remote", False)
    
    # === Default Model ===
    
    @property
    def default_model(self) -> str:
        """Модель Ollama по умолчанию."""
        return self._config_data.get("default", {}).get("default_model", "codellama:7b")
    
    @property
    def fallback_model(self) -> str:
        """Альтернативная модель если основная недоступна."""
        return self._config_data.get("default", {}).get("fallback_model", "codellama:13b-instruct-q4_0")
    
    @property
    def intent_model(self) -> str:
        """Модель для классификации намерений."""
        return self._config_data.get("default", {}).get("intent_model", "phi3:mini")
    
    @property
    def intent_fallback(self) -> str:
        """Альтернативная модель для намерений."""
        return self._config_data.get("default", {}).get("intent_fallback", "tinyllama:1.1b")
    
    @property
    def embedding_model(self) -> str:
        """Модель для embeddings."""
        return self._config_data.get("default", {}).get("embedding_model", "nomic-embed-text")
    
    @property
    def max_iterations(self) -> int:
        """Максимальное количество итераций."""
        return self._config_data.get("default", {}).get("max_iterations", 5)
    
    @property
    def enable_web(self) -> bool:
        """Включен ли веб-поиск по умолчанию."""
        return self._config_data.get("default", {}).get("enable_web", True)
    
    @property
    def temperature(self) -> float:
        """Температура генерации по умолчанию."""
        return self._config_data.get("default", {}).get("temperature", 0.25)
    
    @property
    def max_tokens_warning(self) -> int:
        """Порог предупреждения о токенах."""
        return self._config_data.get("default", {}).get("max_tokens_warning", 30000)
    
    @property
    def enable_model_roster(self) -> bool:
        """Включено ли роевое использование моделей."""
        return self._config_data.get("default", {}).get("enable_model_roster", False)
    
    # === Reasoning Models ===
    
    @property
    def prefer_reasoning_models(self) -> bool:
        """Предпочитать reasoning модели (DeepSeek-R1, QwQ) для complex задач."""
        return self._config_data.get("reasoning", {}).get("prefer_reasoning_models", True)
    
    @property
    def reasoning_show_thinking(self) -> bool:
        """Показывать <think> блоки в UI."""
        return self._config_data.get("reasoning", {}).get("show_thinking", False)
    
    @property
    def reasoning_min_quality(self) -> float:
        """Минимальное качество для reasoning модели."""
        return self._config_data.get("reasoning", {}).get("min_quality", 0.7)
    
    @property
    def reasoning_prefer_for_task_types(self) -> list[str]:
        """Типы задач где предпочтительны reasoning модели."""
        return self._config_data.get("reasoning", {}).get(
            "prefer_for_task_types", 
            ["debug", "refactor", "analyze"]
        )
    
    # === Structured Output ===
    
    @property
    def structured_output_enabled(self) -> bool:
        """Включён ли structured output через Pydantic."""
        return self._config_data.get("structured_output", {}).get("enabled", True)
    
    @property
    def structured_output_max_retries(self) -> int:
        """Количество retry при ошибке валидации."""
        return self._config_data.get("structured_output", {}).get("max_retries", 2)
    
    @property
    def structured_output_enabled_agents(self) -> list[str]:
        """Агенты которые используют structured output."""
        return self._config_data.get("structured_output", {}).get("enabled_agents", ["intent"])
    
    @property
    def structured_output_fallback(self) -> bool:
        """Fallback на ручной парсинг если structured output не работает."""
        return self._config_data.get("structured_output", {}).get("fallback_to_manual_parsing", True)
    
    @property
    def output_dir(self) -> str:
        """Директория для сохранения артефактов."""
        return self._config_data.get("default", {}).get("output_dir", "output")
    
    # === LLM Generation Limits ===
    
    @property
    def llm_tokens_planning(self) -> int:
        """Максимум токенов для генерации плана."""
        return self._config_data.get("llm", {}).get("tokens_planning", 256)
    
    @property
    def llm_tokens_tests(self) -> int:
        """Максимум токенов для генерации тестов."""
        return self._config_data.get("llm", {}).get("tokens_tests", 2048)
    
    @property
    def llm_tokens_code(self) -> int:
        """Максимум токенов для генерации кода."""
        return self._config_data.get("llm", {}).get("tokens_code", 4096)
    
    @property
    def llm_tokens_analysis(self) -> int:
        """Максимум токенов для анализа/рефлексии."""
        return self._config_data.get("llm", {}).get("tokens_analysis", 1024)
    
    @property
    def llm_tokens_intent(self) -> int:
        """Максимум токенов для классификации намерения."""
        return self._config_data.get("llm", {}).get("tokens_intent", 128)
    
    @property
    def llm_tokens_debug(self) -> int:
        """Максимум токенов для анализа ошибок."""
        return self._config_data.get("llm", {}).get("tokens_debug", 2048)
    
    @property
    def llm_tokens_critic(self) -> int:
        """Максимум токенов для критического анализа."""
        return self._config_data.get("llm", {}).get("tokens_critic", 512)
    
    # === Quality Thresholds ===
    
    @property
    def quality_threshold(self) -> float:
        """Минимальный порог качества для успешного результата."""
        return self._config_data.get("quality", {}).get("threshold", 0.7)
    
    @property
    def confidence_threshold(self) -> float:
        """Минимальный порог уверенности агентов."""
        return self._config_data.get("quality", {}).get("confidence_threshold", 0.75)
    
    @property
    def retry_threshold(self) -> float:
        """Порог для повторного запуска (если качество ниже, should_retry = true)."""
        return self._config_data.get("quality", {}).get("retry_threshold", 0.5)
    
    # === Web Search ===
    
    @property
    def tavily_api_key(self) -> Optional[str]:
        """API ключ для Tavily Search."""
        import os
        # Приоритет: переменная окружения > config.toml
        env_key = os.environ.get("TAVILY_API_KEY")
        if env_key:
            return env_key
        return self._config_data.get("web_search", {}).get("tavily_api_key")
    
    @property
    def web_search_timeout(self) -> int:
        """Таймаут веб-поиска в секундах."""
        return self._config_data.get("web_search", {}).get("timeout", 10)
    
    @property
    def web_search_max_results(self) -> int:
        """Максимальное количество результатов веб-поиска."""
        return self._config_data.get("web_search", {}).get("max_results", 3)
    
    # === RAG Settings ===
    
    @property
    def rag_persist_directory(self) -> str:
        """Директория для хранения ChromaDB."""
        return self._config_data.get("rag", {}).get("persist_directory", ".chromadb")
    
    @property
    def rag_memory_collection(self) -> str:
        """Название коллекции для памяти задач."""
        return self._config_data.get("rag", {}).get("memory_collection", "task_memory")
    
    @property
    def rag_code_collection(self) -> str:
        """Название коллекции для кодовой базы."""
        return self._config_data.get("rag", {}).get("code_collection", "code_knowledge")
    
    @property
    def rag_similarity_threshold(self) -> float:
        """Минимальный порог схожести для результатов RAG."""
        return self._config_data.get("rag", {}).get("similarity_threshold", 0.5)
    
    @property
    def rag_max_results(self) -> int:
        """Максимальное количество результатов из RAG."""
        return self._config_data.get("rag", {}).get("max_results", 5)
    
    # === Interaction Settings ===
    
    @property
    def interaction_default_mode(self) -> str:
        """Режим взаимодействия по умолчанию: auto, chat, plan, analyze, code."""
        return self._config_data.get("interaction", {}).get("default_mode", "auto")
    
    @property
    def chat_model(self) -> str:
        """Лёгкая модель для режима chat (диалоги, приветствия)."""
        return self._config_data.get("interaction", {}).get("chat_model", "phi3:mini")
    
    @property
    def chat_model_fallback(self) -> str:
        """Fallback модель для chat если основная недоступна."""
        return self._config_data.get("interaction", {}).get("chat_model_fallback", "tinyllama:1.1b")
    
    @property
    def interaction_auto_confirm(self) -> bool:
        """Автоматически запускать workflow без подтверждения."""
        return self._config_data.get("interaction", {}).get("auto_confirm", True)
    
    @property
    def interaction_show_thinking(self) -> bool:
        """Показывать процесс размышления агента."""
        return self._config_data.get("interaction", {}).get("show_thinking", True)
    
    @property
    def interaction_max_context_messages(self) -> int:
        """Максимум сообщений в контексте до суммаризации."""
        return self._config_data.get("interaction", {}).get("max_context_messages", 20)
    
    @property
    def interaction_persist_conversations(self) -> bool:
        """Сохранять историю диалогов на диск."""
        return self._config_data.get("interaction", {}).get("persist_conversations", True)
    
    @property
    def llm_tokens_chat(self) -> int:
        """Максимум токенов для ответа в режиме chat."""
        return self._config_data.get("interaction", {}).get("tokens_chat", 2048)
    
    # === Hardware Limits ===
    
    @property
    def max_model_vram_gb(self) -> float:
        """Максимальный размер модели в GB (0 = без лимита)."""
        return self._config_data.get("hardware", {}).get("max_model_vram_gb", 0)
    
    @property
    def allow_heavy_models(self) -> bool:
        """Разрешить использование моделей 30B+ для COMPLEX задач."""
        return self._config_data.get("hardware", {}).get("allow_heavy_models", True)
    
    @property
    def allow_ultra_models(self) -> bool:
        """Разрешить использование моделей 100B+."""
        return self._config_data.get("hardware", {}).get("allow_ultra_models", False)
    
    # === Context Engine Settings ===
    
    @property
    def context_engine_enabled(self) -> bool:
        """Включена ли индексация кодовой базы."""
        return self._config_data.get("context_engine", {}).get("enabled", True)
    
    @property
    def context_engine_max_context_tokens(self) -> int:
        """Максимальный размер контекста в токенах."""
        return self._config_data.get("context_engine", {}).get("max_context_tokens", 4000)
    
    @property
    def context_engine_max_chunk_tokens(self) -> int:
        """Максимальный размер чанка в токенах."""
        return self._config_data.get("context_engine", {}).get("max_chunk_tokens", 500)
    
    @property
    def context_engine_cache_directory(self) -> str:
        """Директория для кэша индексов."""
        return self._config_data.get("context_engine", {}).get("cache_directory", ".context_cache")
    
    @property
    def context_engine_default_extensions(self) -> list[str]:
        """Расширения файлов по умолчанию для индексации."""
        return self._config_data.get("context_engine", {}).get("default_extensions", [".py"])
    
    # === LLM Timeouts ===
    
    def get_stage_timeout(self, stage: str) -> int:
        """Возвращает таймаут для конкретного этапа workflow.
        
        Читает свежее значение из файла для hot-reload.
        
        Args:
            stage: Название этапа (intent, planning, coding, etc.)
            
        Returns:
            Таймаут в секундах
        """
        # Hot-reload таймаутов — читаем свежее значение из файла
        try:
            config_path = Path(__file__).parent.parent / "config.toml"
            if config_path.exists():
                with open(config_path, "rb") as f:
                    fresh_config = tomllib.load(f)
                    timeouts = fresh_config.get("timeouts", {})
                    return timeouts.get(stage, timeouts.get("default", 120))
        except Exception:
            pass
        # Fallback на кэшированные значения
        timeouts = self._config_data.get("timeouts", {})
        return timeouts.get(stage, timeouts.get("default", 120))
    
    @property
    def timeout_intent(self) -> int:
        """Таймаут для определения намерения."""
        return self._config_data.get("timeouts", {}).get("intent", 60)
    
    @property
    def timeout_planning(self) -> int:
        """Таймаут для планирования."""
        return self._config_data.get("timeouts", {}).get("planning", 90)
    
    @property
    def timeout_research(self) -> int:
        """Таймаут для исследования/контекста."""
        return self._config_data.get("timeouts", {}).get("research", 90)
    
    @property
    def timeout_testing(self) -> int:
        """Таймаут для генерации тестов."""
        return self._config_data.get("timeouts", {}).get("testing", 120)
    
    @property
    def timeout_coding(self) -> int:
        """Таймаут для генерации кода."""
        return self._config_data.get("timeouts", {}).get("coding", 180)
    
    @property
    def timeout_validation(self) -> int:
        """Таймаут для валидации."""
        return self._config_data.get("timeouts", {}).get("validation", 120)
    
    @property
    def timeout_debug(self) -> int:
        """Таймаут для анализа ошибок."""
        return self._config_data.get("timeouts", {}).get("debug", 120)
    
    @property
    def timeout_fixing(self) -> int:
        """Таймаут для исправления кода."""
        return self._config_data.get("timeouts", {}).get("fixing", 150)
    
    @property
    def timeout_reflection(self) -> int:
        """Таймаут для рефлексии."""
        return self._config_data.get("timeouts", {}).get("reflection", 90)
    
    @property
    def timeout_critic(self) -> int:
        """Таймаут для критического анализа."""
        return self._config_data.get("timeouts", {}).get("critic", 90)
    
    @property
    def timeout_chat(self) -> int:
        """Таймаут для chat режима."""
        return self._config_data.get("timeouts", {}).get("chat", 90)
    
    @property
    def timeout_default(self) -> int:
        """Дефолтный таймаут."""
        return self._config_data.get("timeouts", {}).get("default", 120)
    
    # === Task Persistence Settings ===
    
    @property
    def persistence_enabled(self) -> bool:
        """Включена ли система checkpoint для сохранения состояния задач."""
        return self._config_data.get("persistence", {}).get("enabled", True)
    
    @property
    def persistence_checkpoint_directory(self) -> str:
        """Директория для хранения checkpoint файлов."""
        return self._config_data.get("persistence", {}).get("checkpoint_directory", ".task_checkpoints")
    
    @property
    def persistence_max_checkpoint_age_hours(self) -> int:
        """Максимальный возраст checkpoint в часах."""
        return self._config_data.get("persistence", {}).get("max_checkpoint_age_hours", 24)
    
    @property
    def persistence_auto_pause_on_disconnect(self) -> bool:
        """Автоматически помечать задачи как paused при потере соединения."""
        return self._config_data.get("persistence", {}).get("auto_pause_on_disconnect", True)


def get_config() -> Config:
    """Возвращает экземпляр конфигурации."""
    return Config()
