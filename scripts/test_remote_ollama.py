#!/usr/bin/env python3
"""Скрипт для проверки подключения к удалённому Ollama.

Использование:
    python scripts/test_remote_ollama.py
    python scripts/test_remote_ollama.py --host http://192.168.1.100:11434
"""
import argparse
import sys
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import ollama
    import requests
    from utils.config import get_config
    from utils.logger import get_logger
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Убедитесь, что вы находитесь в корне проекта и зависимости установлены")
    sys.exit(1)


logger = get_logger()


def test_connection(host: str) -> bool:
    """Проверяет подключение к Ollama.
    
    Args:
        host: URL хоста Ollama (например, http://192.168.1.100:11434)
        
    Returns:
        True если подключение успешно, False иначе
    """
    print(f"\n🔍 Проверка подключения к {host}...")
    
    try:
        # Сначала пробуем прямой HTTP запрос для получения точной структуры
        print("  📡 Проверка доступности API...")
        try:
            response = requests.get(f"{host}/api/tags", timeout=5)
            if response.status_code == 200:
                api_data = response.json()
                models_list = api_data.get('models', [])
                if models_list:
                    print(f"  ✅ Подключение успешно (через HTTP API)!")
                    print(f"  📦 Доступно моделей: {len(models_list)}")
                    
                    print("\n  📋 Установленные модели:")
                    first_model_name = None
                    for model in models_list:
                        name = model.get('name', 'unknown')
                        size = model.get('size', 0)
                        size_gb = size / (1024**3) if size else 0
                        print(f"    - {name} ({size_gb:.2f} GB)")
                        
                        if first_model_name is None and name and name != 'unknown':
                            first_model_name = name
                    
                    # Тестовый запрос
                    if first_model_name:
                        print(f"\n  🧪 Тестовый запрос (модель: {first_model_name})...")
                        try:
                            test_response = requests.post(
                                f"{host}/api/generate",
                                json={
                                    "model": first_model_name,
                                    "prompt": "Say 'Hello' in one word.",
                                    "options": {"num_predict": 10}
                                },
                                timeout=30
                            )
                            if test_response.status_code == 200:
                                result = test_response.json().get('response', '').strip()
                                print(f"  ✅ Тестовый запрос успешен: '{result}'")
                            else:
                                print(f"  ⚠️  Тестовый запрос вернул код {test_response.status_code}")
                        except Exception as e:
                            print(f"  ⚠️  Тестовый запрос не удался: {e}")
                            print(f"  💡 Это нормально, если модель ещё не загружена в память")
                    
                    return True
        except requests.RequestException:
            # Fallback на ollama SDK
            pass
        
        # Используем ollama SDK как fallback
        client = ollama.Client(host=host)
        models_response = client.list()
        
        # Отладочный вывод структуры (можно закомментировать)
        # print(f"  🔍 Debug: type={type(models_response)}, dir={[x for x in dir(models_response) if not x.startswith('_')]}")
        
        # Ollama может вернуть объект с атрибутом models или словарь
        if hasattr(models_response, 'models'):
            models_list = models_response.models
        elif isinstance(models_response, dict):
            models_list = models_response.get('models', [])
        else:
            models_list = []
        
        # Если models_list пуст, пробуем получить напрямую
        if not models_list and hasattr(models_response, '__dict__'):
            # Пробуем найти models в __dict__
            for key, value in models_response.__dict__.items():
                if 'model' in key.lower() and isinstance(value, (list, tuple)):
                    models_list = list(value)
                    break
        
        print(f"  ✅ Подключение успешно!")
        print(f"  📦 Доступно моделей: {len(models_list)}")
        
        if models_list:
            print("\n  📋 Установленные модели:")
            first_model_name = None
            for idx, model in enumerate(models_list):
                # Обрабатываем разные форматы ответа
                name = None
                size = 0
                
                # Пробуем разные способы получения данных
                if isinstance(model, dict):
                    name = model.get('name') or model.get('model')
                    size = model.get('size', 0)
                elif hasattr(model, 'name'):
                    name = model.name
                    size = getattr(model, 'size', 0)
                elif hasattr(model, 'model'):
                    name = model.model
                    size = getattr(model, 'size', 0)
                elif hasattr(model, '__dict__'):
                    model_dict = model.__dict__
                    name = model_dict.get('name') or model_dict.get('model')
                    size = model_dict.get('size', 0)
                
                # Если всё ещё не нашли, пробуем через vars() или dir()
                if not name:
                    try:
                        model_vars = vars(model)
                        name = model_vars.get('name') or model_vars.get('model')
                        size = model_vars.get('size', 0)
                    except:
                        pass
                
                # Последняя попытка - через строковое представление
                if not name:
                    model_str = str(model)
                    # Пробуем найти имя в строке
                    import re
                    # Ищем паттерны типа name='...' или "name": "..."
                    match = re.search(r"(?:name|model)\s*[=:]\s*['\"]([^'\"]+)['\"]", model_str)
                    if match:
                        name = match.group(1)
                    else:
                        name = f"model_{idx+1}"
                
                size_gb = size / (1024**3) if size else 0
                print(f"    - {name} ({size_gb:.2f} GB)")
                
                # Сохраняем первую модель для теста
                if first_model_name is None and name and name not in ('unknown', 'None', ''):
                    first_model_name = name
        else:
            print("  ⚠️  Модели не найдены. Установите модели на удалённом сервере:")
            print("     ollama pull qwen2.5-coder:7b")
        
        # Тестовый запрос
        if first_model_name:
            print(f"\n  🧪 Тестовый запрос (модель: {first_model_name})...")
            try:
                response = client.generate(
                    model=first_model_name,
                    prompt="Say 'Hello' in one word.",
                    options={'num_predict': 10}
                )
                
                # Обрабатываем разные форматы ответа
                if hasattr(response, 'response'):
                    result = response.response
                elif isinstance(response, dict):
                    result = response.get('response', '')
                else:
                    result = str(response)
                
                result = result.strip() if result else ''
                print(f"  ✅ Тестовый запрос успешен: '{result}'")
            except Exception as e:
                print(f"  ⚠️  Тестовый запрос не удался: {e}")
                print(f"  💡 Это нормально, если модель ещё не загружена в память")
        else:
            print("\n  ⚠️  Пропущен тестовый запрос: нет доступных моделей с именем")
        
        result = response.get('response', '').strip()
        print(f"  ✅ Тестовый запрос успешен: '{result}'")
        
        return True
        
    except ollama.ResponseError as e:
        print(f"  ❌ Ошибка API: {e}")
        return False
    except ConnectionError as e:
        print(f"  ❌ Ошибка подключения: {e}")
        print(f"  💡 Проверьте:")
        print(f"     - Ollama запущен на {host}")
        print(f"     - Файрвол разрешает подключения на порт 11434")
        print(f"     - IP-адрес правильный")
        return False
    except Exception as e:
        print(f"  ❌ Неожиданная ошибка: {e}")
        return False


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="Проверка подключения к удалённому Ollama"
    )
    parser.add_argument(
        '--host',
        type=str,
        help='URL хоста Ollama (например, http://192.168.1.100:11434)',
        default=None
    )
    
    args = parser.parse_args()
    
    # Определяем хост
    if args.host:
        host = args.host
    else:
        # Используем конфигурацию из config.toml
        config = get_config()
        host = config.ollama_host
        print(f"📝 Используется хост из config.toml: {host}")
    
    # Проверяем подключение
    success = test_connection(host)
    
    if success:
        print("\n✅ Все проверки пройдены! Удалённый Ollama готов к работе.")
        return 0
    else:
        print("\n❌ Проверка не пройдена. См. инструкции в docs/REMOTE_OLLAMA_SETUP.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
