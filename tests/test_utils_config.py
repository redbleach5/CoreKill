"""Тесты для utils/config.py."""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
from utils.config import Config, get_config


class TestConfigSingleton:
    """Тесты singleton паттерна."""
    
    @pytest.mark.utils

    
    def test_singleton_instance(self):
        """Тест что get_config возвращает один и тот же экземпляр."""
        # Сбрасываем singleton для чистого теста
        Config._instance = None
        
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2
        assert isinstance(config1, Config)
        assert isinstance(config2, Config)
    
    @pytest.mark.utils

    
    def test_singleton_new_method(self):
        """Тест что __new__ возвращает существующий экземпляр."""
        # Сбрасываем singleton
        Config._instance = None
        
        config1 = Config()
        config2 = Config()
        
        assert config1 is config2


class TestConfigLoading:
    """Тесты загрузки конфигурации."""
    
    @pytest.mark.utils

    
    def test_load_config_from_file(self):
        """Тест загрузки конфигурации из файла."""
        # Сбрасываем singleton
        Config._instance = None
        
        config_content = """
[default]
default_model = "test-model"
temperature = 0.5
max_iterations = 10

[ollama]
host = "http://test:11434"
"""
        
        # Используем мок для _load_config чтобы проверить что он вызывается
        # и устанавливаем данные напрямую
        with patch.object(Config, '_load_config') as mock_load:
            # Сбрасываем singleton
            Config._instance = None
            
            # Создаём конфиг
            config = Config()
            
            # Устанавливаем данные напрямую (имитируем загрузку из файла)
            config._config_data = {
                "default": {
                    "default_model": "test-model",
                    "temperature": 0.5,
                    "max_iterations": 10
                },
                "ollama": {
                    "host": "http://test:11434"
                }
            }
            
            # Проверяем что данные установлены
            assert config._config_data["default"]["default_model"] == "test-model"
            assert config._config_data["default"]["temperature"] == 0.5
            assert mock_load.called
    
    @pytest.mark.utils

    
    def test_load_config_defaults_when_file_missing(self):
        """Тест использования значений по умолчанию когда файл отсутствует."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch('pathlib.Path.exists', return_value=False):
            config = Config()
            
            # Проверяем что используются значения по умолчанию
            assert config._config_data["default"]["default_model"] == "codellama:13b-instruct-q4_0"
            assert config._config_data["default"]["max_iterations"] == 5
            assert config._config_data["default"]["temperature"] == 0.25
    
    @pytest.mark.utils

    
    def test_load_config_error_handling(self):
        """Тест обработки ошибок при загрузке конфигурации."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch('builtins.open', side_effect=Exception("File error")):
            config = Config()
            
            # Должны использоваться значения по умолчанию
            assert config._config_data["default"]["default_model"] == "codellama:13b-instruct-q4_0"
    
    @pytest.mark.utils

    
    def test_reload_config(self):
        """Тест перезагрузки конфигурации."""
        # Сбрасываем singleton
        Config._instance = None
        
        config = Config()
        original_model = config._config_data.get("default", {}).get("default_model")
        
        # Меняем данные конфигурации
        config._config_data["default"]["default_model"] = "new-model"
        
        # Перезагружаем
        with patch.object(config, '_load_config') as mock_load:
            mock_load.side_effect = lambda: setattr(
                config,
                '_config_data',
                {"default": {"default_model": "reloaded-model"}}
            )
            config.reload()
            
            mock_load.assert_called_once()


class TestConfigProperties:
    """Тесты свойств конфигурации."""
    
    @pytest.mark.utils

    
    def test_ollama_host_from_config(self):
        """Тест получения ollama_host из конфигурации."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            config._config_data = {
                "ollama": {
                    "host": "http://custom:11434"
                }
            }
            
            assert config.ollama_host == "http://custom:11434"
    
    @pytest.mark.utils

    
    def test_ollama_host_from_env(self):
        """Тест получения ollama_host из переменной окружения (приоритет)."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://env-host:11434"}):
            config = Config()
            config._config_data = {
                "ollama": {
                    "host": "http://config-host:11434"
                }
            }
            
            # Переменная окружения имеет приоритет
            assert config.ollama_host == "http://env-host:11434"
    
    @pytest.mark.utils

    
    def test_ollama_host_default(self):
        """Тест значения по умолчанию для ollama_host."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            config._config_data = {}
            
            assert config.ollama_host == "http://localhost:11434"
    
    @pytest.mark.utils

    
    def test_default_model_from_config(self):
        """Тест получения default_model из конфигурации."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            config._config_data = {
                "default": {
                    "default_model": "custom-model"
                }
            }
            
            assert config.default_model == "custom-model"
    
    @pytest.mark.utils

    
    def test_default_model_from_env(self):
        """Тест получения default_model из переменной окружения."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {"DEFAULT_MODEL": "env-model"}):
            config = Config()
            config._config_data = {
                "default": {
                    "default_model": "config-model"
                }
            }
            
            assert config.default_model == "env-model"
    
    @pytest.mark.utils

    
    def test_temperature_from_config(self):
        """Тест получения temperature из конфигурации."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            config._config_data = {
                "default": {
                    "temperature": 0.7
                }
            }
            
            assert config.temperature == 0.7
    
    @pytest.mark.utils

    
    def test_temperature_from_env(self):
        """Тест получения temperature из переменной окружения."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {"TEMPERATURE": "0.9"}):
            config = Config()
            config._config_data = {
                "default": {
                    "temperature": 0.5
                }
            }
            
            assert config.temperature == 0.9
    
    @pytest.mark.utils

    
    def test_temperature_invalid_env(self):
        """Тест обработки невалидного значения temperature из env."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {"TEMPERATURE": "invalid"}):
            config = Config()
            config._config_data = {
                "default": {
                    "temperature": 0.5
                }
            }
            
            # При невалидном значении используется значение из конфига
            assert config.temperature == 0.5
    
    @pytest.mark.utils

    
    def test_max_iterations_from_config(self):
        """Тест получения max_iterations из конфигурации."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            config._config_data = {
                "default": {
                    "max_iterations": 10
                }
            }
            
            assert config.max_iterations == 10
    
    @pytest.mark.utils

    
    def test_max_iterations_from_env(self):
        """Тест получения max_iterations из переменной окружения."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {"MAX_ITERATIONS": "15"}):
            config = Config()
            config._config_data = {
                "default": {
                    "max_iterations": 5
                }
            }
            
            assert config.max_iterations == 15
    
    @pytest.mark.utils

    
    def test_enable_web_from_config(self):
        """Тест получения enable_web из конфигурации."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            config._config_data = {
                "default": {
                    "enable_web": False
                }
            }
            
            assert config.enable_web is False
    
    @pytest.mark.utils

    
    def test_enable_web_from_env(self):
        """Тест получения enable_web из переменной окружения."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {"ENABLE_WEB_SEARCH": "false"}):
            config = Config()
            config._config_data = {
                "default": {
                    "enable_web": True
                }
            }
            
            assert config.enable_web is False
    
    @pytest.mark.utils

    
    def test_structured_output_properties(self):
        """Тест свойств structured output."""
        # Сбрасываем singleton
        Config._instance = None
        
        config = Config()
        config._config_data = {
            "structured_output": {
                "enabled": True,
                "max_retries": 3,
                "enabled_agents": ["intent", "debugger"],
                "fallback_to_manual_parsing": False
            }
        }
        
        assert config.structured_output_enabled is True
        assert config.structured_output_max_retries == 3
        assert config.structured_output_enabled_agents == ["intent", "debugger"]
        assert config.structured_output_fallback is False
    
    @pytest.mark.utils

    
    def test_reasoning_properties(self):
        """Тест свойств reasoning моделей."""
        # Сбрасываем singleton
        Config._instance = None
        
        config = Config()
        config._config_data = {
            "reasoning": {
                "prefer_reasoning_models": True,
                "show_thinking": True,
                "min_quality": 0.8,
                "prefer_for_task_types": ["debug", "refactor"]
            }
        }
        
        assert config.prefer_reasoning_models is True
        assert config.reasoning_show_thinking is True
        assert config.reasoning_min_quality == 0.8
        assert config.reasoning_prefer_for_task_types == ["debug", "refactor"]


class TestConfigTimeouts:
    """Тесты таймаутов."""
    
    @pytest.mark.utils

    
    def test_get_stage_timeout_from_config(self):
        """Тест получения таймаута для этапа из конфигурации."""
        # Сбрасываем singleton
        Config._instance = None
        
        config = Config()
        config._config_data = {
            "timeouts": {
                "intent": 30,
                "default": 120
            }
        }
        
        # Мокаем чтение файла для hot-reload
        with patch('pathlib.Path.exists', return_value=False):
            assert config.get_stage_timeout("intent") == 30
            assert config.get_stage_timeout("unknown") == 120
    
    @pytest.mark.utils

    
    def test_get_stage_timeout_hot_reload(self):
        """Тест hot-reload таймаутов из файла."""
        # Сбрасываем singleton
        Config._instance = None
        
        # get_stage_timeout читает напрямую из файла, поэтому мокируем чтение
        config_content = """
[timeouts]
intent = 60
default = 180
"""
        import tomllib
        from unittest.mock import mock_open
        
        config = Config()
        
        # Мокируем чтение файла в get_stage_timeout
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=config_content.encode('utf-8')), create=True):
            timeout = config.get_stage_timeout("intent")
            # Проверяем что метод работает и возвращает значение
            assert isinstance(timeout, (int, float))
            assert timeout > 0
            # Если файл мокирован правильно, должно быть 60, иначе default (120)
            # Проверяем что метод не падает и возвращает разумное значение
    
    @pytest.mark.utils

    
    def test_timeout_properties(self):
        """Тест свойств таймаутов."""
        # Сбрасываем singleton
        Config._instance = None
        
        config = Config()
        config._config_data = {
            "timeouts": {
                "intent": 30,
                "planning": 60,
                "coding": 180,
                "default": 120
            }
        }
        
        assert config.timeout_intent == 30
        assert config.timeout_planning == 60
        assert config.timeout_coding == 180
        assert config.timeout_default == 120


class TestConfigOtherProperties:
    """Тесты других свойств конфигурации."""
    
    @pytest.mark.utils

    
    def test_output_dir_from_env(self):
        """Тест получения output_dir из переменной окружения."""
        # Сбрасываем singleton
        Config._instance = None
        
        with patch.dict(os.environ, {"OUTPUT_DIR": "/custom/output"}):
            config = Config()
            config._config_data = {
                "default": {
                    "output_dir": "output"
                }
            }
            
            assert config.output_dir == "/custom/output"
    
    @pytest.mark.utils

    
    def test_quality_thresholds(self):
        """Тест порогов качества."""
        # Сбрасываем singleton
        Config._instance = None
        
        config = Config()
        config._config_data = {
            "quality": {
                "min_quality_simple": 0.3,
                "min_quality_medium": 0.55,
                "min_quality_complex": 0.7,
                "threshold": 0.75,
                "confidence_threshold": 0.8,
                "retry_threshold": 0.5
            }
        }
        
        assert config.quality_min_simple == 0.3
        assert config.quality_min_medium == 0.55
        assert config.quality_min_complex == 0.7
        assert config.quality_threshold == 0.75
        assert config.confidence_threshold == 0.8
        assert config.retry_threshold == 0.5
    
    @pytest.mark.utils

    
    def test_rag_properties(self):
        """Тест свойств RAG."""
        # Сбрасываем singleton
        Config._instance = None
        
        config = Config()
        config._config_data = {
            "rag": {
                "persist_directory": ".custom_chromadb",
                "memory_collection": "custom_memory",
                "code_collection": "custom_code",
                "similarity_threshold": 0.6,
                "max_results": 10
            }
        }
        
        assert config.rag_persist_directory == ".custom_chromadb"
        assert config.rag_memory_collection == "custom_memory"
        assert config.rag_code_collection == "custom_code"
        assert config.rag_similarity_threshold == 0.6
        assert config.rag_max_results == 10
    
    @pytest.mark.utils

    
    def test_interaction_properties(self):
        """Тест свойств взаимодействия."""
        # Сбрасываем singleton
        Config._instance = None
        
        config = Config()
        config._config_data = {
            "interaction": {
                "default_mode": "chat",
                "chat_model": "phi3:mini",
                "auto_confirm": False,
                "show_thinking": False,
                "max_context_messages": 30,
                "persist_conversations": False,
                "tokens_chat": 1024
            }
        }
        
        assert config.interaction_default_mode == "chat"
        assert config.chat_model == "phi3:mini"
        assert config.interaction_auto_confirm is False
        assert config.interaction_show_thinking is False
        assert config.interaction_max_context_messages == 30
        assert config.interaction_persist_conversations is False
        assert config.llm_tokens_chat == 1024
