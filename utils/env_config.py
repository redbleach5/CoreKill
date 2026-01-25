"""Управление конфигурацией из переменных окружения.

Предоставляет Pydantic модель для работы с переменными окружения.
Используется для переопределения настроек из config.toml.

Примеры использования:
    ```python
    from utils.env_config import get_env_config
    
    # Получить конфигурацию из переменных окружения
    env_config = get_env_config()
    
    # Доступ к настройкам
    model = env_config.default_model
    temperature = env_config.temperature
    ollama_url = env_config.ollama_base_url
    
    # Проверка окружения
    if env_config.is_production():
        # Запущено в production
    
    # Получить список разрешённых origins
    origins = env_config.get_allowed_origins_list()
    ```

Переменные окружения:
    - ENVIRONMENT: окружение (development/production)
    - DEBUG: режим отладки
    - BACKEND_PORT: порт backend
    - FRONTEND_PORT: порт frontend
    - OLLAMA_BASE_URL: URL Ollama API
    - DEFAULT_MODEL: модель по умолчанию
    - TEMPERATURE: температура для LLM
    - И многие другие (см. EnvironmentConfig)

Зависимости:
    - pydantic: для валидации конфигурации
    - os: для доступа к переменным окружения
    - functools: для кэширования

Связанные утилиты:
    - utils.config: основная конфигурация из config.toml
    - run.py: может использовать для переопределения настроек

Примечания:
    - Конфигурация кэшируется (lru_cache)
    - Переменные окружения имеют приоритет над config.toml
    - Все значения валидируются через Pydantic
    - Поддерживает типы: str, int, float, bool
"""
import os
from typing import Optional, Dict, Any
from functools import lru_cache
from pydantic import BaseModel, Field, ConfigDict


class EnvironmentConfig(BaseModel):
    """Конфигурация из переменных окружения."""
    
    model_config = ConfigDict(extra='ignore')
    
    # Окружение
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    verbose_logging: bool = Field(default=False, alias="VERBOSE_LOGGING")
    
    # Порты
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    frontend_port: int = Field(default=5173, alias="FRONTEND_PORT")
    
    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_timeout: int = Field(default=300, alias="OLLAMA_TIMEOUT")
    
    # Модели
    default_model: str = Field(default="codellama:7b", alias="DEFAULT_MODEL")
    intent_model: str = Field(default="phi3:mini", alias="INTENT_MODEL")
    embedding_model: str = Field(default="nomic-embed-text", alias="EMBEDDING_MODEL")
    
    # LLM параметры
    temperature: float = Field(default=0.25, alias="TEMPERATURE", ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, alias="MAX_TOKENS", ge=100)
    max_iterations: int = Field(default=5, alias="MAX_ITERATIONS", ge=1, le=10)
    
    # Веб-поиск
    enable_web_search: bool = Field(default=True, alias="ENABLE_WEB_SEARCH")
    web_search_timeout: int = Field(default=10, alias="WEB_SEARCH_TIMEOUT")
    
    # RAG
    enable_rag: bool = Field(default=True, alias="ENABLE_RAG")
    rag_similarity_threshold: float = Field(default=0.5, alias="RAG_SIMILARITY_THRESHOLD", ge=0.0, le=1.0)
    
    # Безопасность
    allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost:8000",
        alias="ALLOWED_ORIGINS"
    )
    rate_limit_requests_per_minute: int = Field(default=100, alias="RATE_LIMIT_REQUESTS_PER_MINUTE")
    cors_max_age: int = Field(default=3600, alias="CORS_MAX_AGE")
    
    # Логирование
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/app.log", alias="LOG_FILE")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    
    # Хранилище
    output_dir: str = Field(default="output", alias="OUTPUT_DIR")
    artifacts_dir: str = Field(default="artifacts", alias="ARTIFACTS_DIR")
    max_artifact_size_mb: int = Field(default=100, alias="MAX_ARTIFACT_SIZE_MB")
    
    # Производительность
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_ttl_seconds: int = Field(default=3600, alias="CACHE_TTL_SECONDS")
    connection_pool_size: int = Field(default=10, alias="CONNECTION_POOL_SIZE")
    
    @classmethod
    def from_env(cls) -> 'EnvironmentConfig':
        """Создаёт конфигурацию из переменных окружения.
        
        Returns:
            Экземпляр EnvironmentConfig
        """
        env_dict: dict[str, str | int | float | bool] = {}
        for field_name, field_info in cls.model_fields.items():
            alias = field_info.alias or field_name.upper()
            value = os.getenv(alias)
            
            if value is not None:
                # Преобразуем строки в нужные типы
                if field_info.annotation in (bool, Optional[bool]):
                    env_dict[field_name] = value.lower() in ('true', '1', 'yes', 'on')
                elif field_info.annotation in (int, Optional[int]):
                    try:
                        env_dict[field_name] = int(value)
                    except ValueError:
                        pass
                elif field_info.annotation in (float, Optional[float]):
                    try:
                        env_dict[field_name] = float(value)
                    except ValueError:
                        pass
                else:
                    env_dict[field_name] = value
        
        return cls(**env_dict)  # type: ignore[arg-type]
    
    def get_allowed_origins_list(self) -> list[str]:
        """Возвращает список разрешённых origins.
        
        Returns:
            Список origins
        """
        return [origin.strip() for origin in self.allowed_origins.split(',') if origin.strip()]
    
    def is_production(self) -> bool:
        """Проверяет, запущено ли в production.
        
        Returns:
            True если production, False иначе
        """
        return self.environment.lower() == "production"
    
    def is_development(self) -> bool:
        """Проверяет, запущено ли в development.
        
        Returns:
            True если development, False иначе
        """
        return self.environment.lower() == "development"


@lru_cache(maxsize=1)
def get_env_config() -> EnvironmentConfig:
    """Возвращает кэшированную конфигурацию из переменных окружения.
    
    Returns:
        Экземпляр EnvironmentConfig
    """
    return EnvironmentConfig.from_env()
