"""Загрузка конфигурации из config.toml."""
from pathlib import Path
from typing import Optional
try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback для Python < 3.11

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
    
    @property
    def output_dir(self) -> str:
        """Директория для сохранения артефактов."""
        return self._config_data.get("default", {}).get("output_dir", "output")


def get_config() -> Config:
    """Возвращает экземпляр конфигурации."""
    return Config()
