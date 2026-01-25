"""Утилита для проверки доступности моделей Ollama.

Поддерживает:
- Динамическое сканирование моделей при каждом запросе
- Анализ размера моделей (параметры, VRAM)
- Выбор оптимальной модели по сложности задачи

Примеры использования:
    ```python
    from utils.model_checker import (
        get_coder_model,
        get_reasoning_model,
        get_best_model_for_complexity,
        scan_available_models,
        TaskComplexity
    )
    
    # Получить лучшую модель для генерации кода
    model = get_coder_model(min_quality=0.7)
    
    # Получить reasoning модель
    reasoning_model = get_reasoning_model(min_quality=0.8)
    
    # Выбрать модель по сложности задачи
    model = get_best_model_for_complexity(
        TaskComplexity.COMPLEX,
        prefer_coder=True
    )
    
    # Сканировать все доступные модели
    models = scan_available_models()
    for name, info in models.items():
        # {name}: {info.estimated_quality}, {info.parameter_size}
    
    # Проверить доступность модели
    from utils.model_checker import check_model_available
    if check_model_available("qwen2.5-coder:7b"):
        # Модель доступна
    ```

Зависимости:
    - ollama: для работы с Ollama API
    - re: для парсинга названий моделей
    - dataclasses: для ModelInfo
    - enum: для TaskComplexity
    - utils.logger: для логирования

Связанные утилиты:
    - infrastructure.model_router: использует эту утилиту для выбора моделей
    - utils.config: конфигурация моделей

Примечания:
    - Кэширует результаты сканирования моделей
    - Используйте invalidate_models_cache() для принудительного обновления
    - Автоматически определяет reasoning модели (DeepSeek-R1, QwQ, o1)
    - Оценивает качество моделей на основе размера и специализации
"""
import re
import ollama
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict
from utils.logger import get_logger

logger = get_logger()


class TaskComplexity(Enum):
    """Уровень сложности задачи."""
    SIMPLE = "simple"      # Простая функция, утилита
    MEDIUM = "medium"      # Класс, модуль с несколькими функциями
    COMPLEX = "complex"    # Игра, система, многофайловый проект


@dataclass
class ModelInfo:
    """Информация о модели Ollama."""
    name: str
    size_bytes: int
    parameter_size: str  # "1.5B", "7B", "13B" etc.
    quantization: str    # "Q4_K_M", "Q8_0", "fp16" etc.
    family: str          # "qwen", "llama", "codellama" etc.
    is_coder: bool       # Специализирована для кода
    is_reasoning: bool   # Reasoning модель с встроенным CoT (DeepSeek-R1, QwQ, o1)
    estimated_quality: float  # 0.0-1.0 оценка качества для генерации кода
    
    @property
    def size_gb(self) -> float:
        """Размер в гигабайтах."""
        return self.size_bytes / (1024 ** 3)
    
    @property
    def param_billions(self) -> float:
        """Количество параметров в миллиардах."""
        match = re.search(r'(\d+\.?\d*)', self.parameter_size)
        if match:
            return float(match.group(1))
        return 0.0
    
    @property
    def estimated_vram_gb(self) -> float:
        """Примерная оценка требуемой VRAM в GB.
        
        Эвристика: ~0.5-1GB на 1B параметров для Q4 квантизации,
        больше для fp16/Q8.
        """
        params = self.param_billions
        quant_multiplier = {
            'FP16': 2.0,
            'F16': 2.0,
            'Q8_0': 1.0,
            'Q6_K': 0.8,
            'Q5_K_M': 0.7,
            'Q5_K_S': 0.65,
            'Q4_K_M': 0.6,
            'Q4_K_S': 0.55,
            'DEFAULT': 0.6
        }
        multiplier = quant_multiplier.get(self.quantization.upper(), 0.6)
        # Базовая формула: params * multiplier + overhead (1-2GB)
        return round(params * multiplier + 1.5, 1)
    
    @property 
    def tier(self) -> str:
        """Категория модели по размеру.
        
        Returns:
            'light' (1-4B), 'medium' (7-14B), 'heavy' (30-70B), 'ultra' (100B+)
        """
        params = self.param_billions
        if params <= 4:
            return 'light'
        elif params <= 14:
            return 'medium'
        elif params <= 72:
            return 'heavy'
        else:
            return 'ultra'


# Кэш информации о моделях (обновляется при каждом сканировании)
_models_cache: Dict[str, ModelInfo] = {}
_cache_valid: bool = False
_cache_ollama_host: str | None = None


def _current_ollama_host() -> str | None:
    """Возвращает текущий хост Ollama, влияющий на список моделей.
    
    Нужен для корректной инвалидации кэша при переключении localhost ↔ remote.
    """
    import os
    # Сначала проверяем переменные окружения (высший приоритет)
    env_host = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST")
    if env_host:
        return env_host
    
    # Затем проверяем конфиг
    try:
        from utils.config import get_config
        config = get_config()
        host = config.ollama_host
        if host:
            return host
    except Exception as e:
        logger.debug(f"⚠️ Ошибка получения Ollama хоста из конфига: {e}")
    
    # Дефолт
    return "http://localhost:11434"


def invalidate_models_cache() -> None:
    """Инвалидирует кэш моделей для принудительного пересканирования."""
    global _cache_valid, _cache_ollama_host
    _cache_valid = False
    _cache_ollama_host = None


def check_ollama_api_available() -> bool:
    """Проверяет доступность Ollama API.
    
    Returns:
        True если Ollama API доступен, False иначе
    """
    try:
        # Простой ping к Ollama API
        ollama.list()
        return True
    except Exception as e:
        logger.debug(f"Ollama API недоступен: {e}")
        return False


def _parse_model_info(model_data: object) -> Optional[ModelInfo]:
    """Парсит информацию о модели из данных Ollama API.
    
    Args:
        model_data: Объект модели от ollama.list()
        
    Returns:
        ModelInfo или None если не удалось распарсить
    """
    try:
        name = model_data.model if hasattr(model_data, 'model') else getattr(model_data, 'name', '')
        if not name:
            return None
        
        # Размер в байтах
        size_bytes = getattr(model_data, 'size', 0)
        
        # Парсим размер параметров из названия модели
        parameter_size = _extract_parameter_size(name)
        
        # Определяем квантизацию
        quantization = _extract_quantization(name)
        
        # Определяем семейство модели
        family = _extract_family(name)
        
        # Проверяем, специализирована ли для кода
        is_coder = _is_coder_model(name)
        
        # Проверяем, является ли reasoning моделью
        is_reasoning = _is_reasoning_model(name)
        
        # Оцениваем качество для генерации кода
        estimated_quality = _estimate_code_quality(name, parameter_size, is_coder, is_reasoning)
        
        return ModelInfo(
            name=name,
            size_bytes=size_bytes,
            parameter_size=parameter_size,
            quantization=quantization,
            family=family,
            is_coder=is_coder,
            is_reasoning=is_reasoning,
            estimated_quality=estimated_quality
        )
    except Exception as e:
        logger.debug(f"Ошибка парсинга модели: {e}")
        return None


def _extract_parameter_size(model_name: str) -> str:
    """Извлекает размер параметров из названия модели.
    
    Args:
        model_name: Название модели (например, "qwen2.5-coder:7b")
        
    Returns:
        Размер параметров (например, "7B") или "unknown"
    """
    name_lower = model_name.lower()
    
    # Паттерны размеров: 1.5b, 7b, 13b, 70b, 1b, 3b, 4b, 8b, 32b
    patterns = [
        r'(\d+\.?\d*b)\b',  # 7b, 1.5b, 13b
        r':(\d+\.?\d*)b',    # :7b, :1.5b
    ]
    
    for pattern in patterns:
        match = re.search(pattern, name_lower)
        if match:
            return match.group(1).upper()
    
    # Специальные случаи
    if 'mini' in name_lower:
        return '3B'  # phi3:mini обычно 3B
    if 'tiny' in name_lower:
        return '1B'
    
    return 'unknown'


def _extract_quantization(model_name: str) -> str:
    """Извлекает тип квантизации из названия модели.
    
    Args:
        model_name: Название модели
        
    Returns:
        Тип квантизации или "default"
    """
    name_lower = model_name.lower()
    
    # Известные квантизации
    quant_patterns = ['q4_k_m', 'q4_k_s', 'q5_k_m', 'q5_k_s', 'q8_0', 'q6_k', 'fp16', 'f16']
    
    for quant in quant_patterns:
        if quant in name_lower:
            return quant.upper()
    
    return 'default'


def _extract_family(model_name: str) -> str:
    """Определяет семейство модели.
    
    Args:
        model_name: Название модели
        
    Returns:
        Семейство модели
    """
    name_lower = model_name.lower()
    
    families = {
        'qwen': ['qwen'],
        'llama': ['llama', 'codellama'],
        'deepseek': ['deepseek'],
        'phi': ['phi'],
        'gemma': ['gemma'],
        'mistral': ['mistral', 'mixtral'],
        'stable': ['stable-code', 'stablecode'],
        'codegemma': ['codegemma'],
        'starcoder': ['starcoder'],
    }
    
    for family, keywords in families.items():
        for keyword in keywords:
            if keyword in name_lower:
                return family
    
    return 'unknown'


def _is_coder_model(model_name: str) -> bool:
    """Проверяет, специализирована ли модель для кода.
    
    Args:
        model_name: Название модели
        
    Returns:
        True если модель для кода
    """
    name_lower = model_name.lower()
    coder_keywords = ['coder', 'code', 'codellama', 'starcoder', 'codegemma']
    
    # Исключаем embed модели
    if 'embed' in name_lower:
        return False
    
    return any(keyword in name_lower for keyword in coder_keywords)


# Известные reasoning модели с встроенным chain-of-thought
REASONING_MODEL_PATTERNS = frozenset([
    'deepseek-r1',   # DeepSeek-R1: рассуждает в <think> блоках
    'qwq',           # Qwen QwQ: reasoning модель от Alibaba
    'o1',            # OpenAI o1 (если через API)
    'o3',            # OpenAI o3 (если через API)
])


def _is_reasoning_model(model_name: str) -> bool:
    """Проверяет, является ли модель reasoning (с встроенным CoT).
    
    Reasoning модели (DeepSeek-R1, QwQ, o1) автоматически рассуждают
    в <think> блоках, не требуя промптов вроде "think step by step".
    
    Args:
        model_name: Название модели
        
    Returns:
        True если модель с reasoning capabilities
    """
    name_lower = model_name.lower()
    
    return any(pattern in name_lower for pattern in REASONING_MODEL_PATTERNS)


def _estimate_code_quality(
    model_name: str, 
    parameter_size: str, 
    is_coder: bool,
    is_reasoning: bool = False
) -> float:
    """Оценивает качество модели для генерации кода.
    
    Учитывает:
    - Размер параметров (больше = лучше качество)
    - Специализация для кода
    - Reasoning capabilities (DeepSeek-R1, QwQ)
    - Известные бенчмарки
    
    Args:
        model_name: Название модели
        parameter_size: Размер параметров
        is_coder: Специализирована для кода
        is_reasoning: Является reasoning моделью
        
    Returns:
        Оценка качества 0.0-1.0
    """
    # Базовая оценка по размеру (масштабируемая до будущих больших моделей)
    size_scores = {
        # Лёгкие модели (1-4B) — быстрые, для простых задач
        '0.5B': 0.2,
        '1B': 0.3,
        '1.5B': 0.4,
        '2B': 0.45,
        '3B': 0.5,
        '4B': 0.55,
        # Средние модели (7-14B) — баланс качества и скорости
        '7B': 0.7,
        '8B': 0.72,
        '13B': 0.8,
        '14B': 0.82,
        # Большие модели (30-70B) — максимальное качество
        '22B': 0.85,
        '30B': 0.88,
        '32B': 0.9,
        '34B': 0.91,
        '40B': 0.92,
        '70B': 0.95,
        '72B': 0.96,
        # Сверхбольшие модели (100B+) — enterprise уровень
        '110B': 0.97,
        '180B': 0.98,
        '405B': 0.99,
        'unknown': 0.5
    }
    
    # Для неизвестных размеров пытаемся вычислить оценку динамически
    base_score = size_scores.get(parameter_size)
    if base_score is None:
        # Динамическая оценка для новых размеров
        match = re.search(r'(\d+\.?\d*)', parameter_size)
        if match:
            params = float(match.group(1))
            if params < 2:
                base_score = 0.3 + (params - 0.5) * 0.1  # 0.3-0.45
            elif params < 10:
                base_score = 0.45 + (params - 2) * 0.035  # 0.45-0.73
            elif params < 35:
                base_score = 0.73 + (params - 10) * 0.007  # 0.73-0.91
            elif params < 100:
                base_score = 0.91 + (params - 35) * 0.001  # 0.91-0.97
            else:
                base_score = min(0.97 + (params - 100) * 0.0003, 0.99)
            base_score = round(min(max(base_score, 0.2), 0.99), 2)
        else:
            base_score = 0.5
    
    # Бонус за специализацию для кода (+0.15)
    if is_coder:
        base_score = min(base_score + 0.15, 1.0)
    
    # Бонус за reasoning capabilities (+0.12)
    # Reasoning модели лучше справляются со сложными задачами
    if is_reasoning:
        base_score = min(base_score + 0.12, 1.0)
    
    # Бонусы/штрафы за конкретные модели (на основе известных бенчмарков)
    name_lower = model_name.lower()
    
    # Известно хорошие для кода
    if 'qwen2.5-coder' in name_lower:
        base_score = min(base_score + 0.1, 1.0)
    elif 'deepseek-coder' in name_lower:
        base_score = min(base_score + 0.08, 1.0)
    elif 'deepseek-r1' in name_lower:
        # DeepSeek-R1 — топовая reasoning модель
        base_score = min(base_score + 0.1, 1.0)
    elif 'qwq' in name_lower:
        # QwQ — сильная reasoning модель от Alibaba
        base_score = min(base_score + 0.08, 1.0)
    elif 'codellama' in name_lower:
        base_score = min(base_score + 0.05, 1.0)
    
    return round(base_score, 2)


def check_model_available(model_name: str) -> bool:
    """Проверяет доступность модели Ollama.
    
    Args:
        model_name: Название модели
        
    Returns:
        True если модель доступна, False иначе
    """
    # Сначала проверяем доступность Ollama API
    if not check_ollama_api_available():
        return False
    
    try:
        models = ollama.list()
        model_names = [
            model.model if hasattr(model, 'model') else getattr(model, 'name', '')
            for model in models.models if hasattr(models, 'models')
        ] if hasattr(models, 'models') else []
        return model_name in model_names
    except Exception as e:
        logger.debug(f"Ошибка проверки модели {model_name}: {e}")
        return False


def get_available_model(preferred: str, fallbacks: List[str]) -> Optional[str]:
    """Возвращает первую доступную модель из списка.
    
    Args:
        preferred: Предпочтительная модель
        fallbacks: Список альтернативных моделей
        
    Returns:
        Название доступной модели или None если ничего не найдено
    """
    if check_model_available(preferred):
        return preferred
    
    for fallback in fallbacks:
        if check_model_available(fallback):
            return fallback
    
    return None


def get_any_available_model() -> Optional[str]:
    """Возвращает любую доступную модель Ollama.
    
    Returns:
        Название доступной модели или None если ничего не найдено
    """
    all_models = get_all_available_models()
    if all_models:
        return all_models[0]
    return None


def get_light_model() -> Optional[str]:
    """Возвращает легкую модель для быстрых операций (intent, planning).
    
    Использует scan_available_models() для динамического выбора.
    Приоритет: модели до 4B параметров.
    Исключает проблемные модели (stable-code и т.д.).
    
    Returns:
        Название легкой модели или None если ничего не найдено
    """
    # Черный список проблемных моделей
    PROBLEMATIC_MODELS = {"stable-code:latest", "stable-code"}
    
    models = scan_available_models()
    if not models:
        return None
    
    # Фильтруем embed модели и проблемные модели, находим легкие (до 4B)
    light_models = [
        m for m in models.values()
        if ('embed' not in m.name.lower() 
            and m.param_billions <= 4.0 
            and m.param_billions > 0
            and not any(problematic in m.name.lower() for problematic in PROBLEMATIC_MODELS))
    ]
    
    if not light_models:
        # Если легких нет, берём любую не-embed модель (исключая проблемные)
        candidates = [
            m for m in models.values() 
            if 'embed' not in m.name.lower()
            and not any(problematic in m.name.lower() for problematic in PROBLEMATIC_MODELS)
        ]
        if candidates:
            # Предпочитаем coder модели
            coder = [m for m in candidates if m.is_coder]
            if coder:
                return min(coder, key=lambda m: m.param_billions or 999).name
            return min(candidates, key=lambda m: m.param_billions or 999).name
        # Крайний случай: любая модель кроме embed
        non_embed = [m for m in models.values() if 'embed' not in m.name.lower()]
        if non_embed:
            return non_embed[0].name
        return list(models.keys())[0]
    
    # Предпочитаем coder модели среди лёгких
    coder_light = [m for m in light_models if m.is_coder]
    if coder_light:
        return max(coder_light, key=lambda m: m.estimated_quality).name
    
    return max(light_models, key=lambda m: m.estimated_quality).name


def get_coder_model(min_quality: float = 0.0) -> Optional[str]:
    """Возвращает лучшую модель для генерации кода.
    
    Использует scan_available_models() для динамического выбора.
    Приоритет: специализированные coder модели с высоким качеством.
    
    Args:
        min_quality: Минимальный порог качества (0.0-1.0)
        
    Returns:
        Название модели для кода или None
    """
    models = scan_available_models()
    if not models:
        return None
    
    # Фильтруем embed модели
    candidates = [m for m in models.values() if 'embed' not in m.name.lower()]
    
    if not candidates:
        return list(models.keys())[0]
    
    # Предпочитаем coder модели
    coder_models = [m for m in candidates if m.is_coder and m.estimated_quality >= min_quality]
    if coder_models:
        best = max(coder_models, key=lambda m: m.estimated_quality)
        logger.debug(f"🤖 Выбрана coder модель: {best.name} (качество: {best.estimated_quality})")
        return best.name
    
    # Fallback: любая модель с достаточным качеством
    suitable = [m for m in candidates if m.estimated_quality >= min_quality]
    if suitable:
        best = max(suitable, key=lambda m: m.estimated_quality)
        logger.debug(f"🤖 Выбрана модель: {best.name} (качество: {best.estimated_quality})")
        return best.name
    
    # Крайний случай: лучшая из доступных
    best = max(candidates, key=lambda m: m.estimated_quality)
    return best.name


def scan_available_models(force_refresh: bool = False) -> Dict[str, ModelInfo]:
    """Сканирует и возвращает информацию о всех доступных моделях.
    
    Обновляет глобальный кэш моделей.
    
    Args:
        force_refresh: Принудительно обновить кэш
        
    Returns:
        Словарь {имя_модели: ModelInfo}
    """
    global _models_cache, _cache_valid, _cache_ollama_host
    
    # Если поменяли хост Ollama (localhost ↔ remote), кэш надо сбросить
    current_host = _current_ollama_host()
    if _cache_ollama_host is not None and current_host != _cache_ollama_host:
        _cache_valid = False
    
    # Обновляем хост (даже если None) — чтобы следующая проверка была корректной
    _cache_ollama_host = current_host
    
    if _cache_valid and not force_refresh:
        return _models_cache
    
    if not check_ollama_api_available():
        logger.warning("⚠️ Ollama API недоступен, не могу получить список моделей")
        return {}
    
    try:
        models = ollama.list()
        new_cache: Dict[str, ModelInfo] = {}
        
        if hasattr(models, 'models'):
            for model_data in models.models:
                model_info = _parse_model_info(model_data)
                if model_info:
                    new_cache[model_info.name] = model_info
        
        _models_cache = new_cache
        _cache_valid = True
        
        logger.debug(f"📊 Отсканировано {len(new_cache)} моделей Ollama")
        return new_cache
        
    except Exception as e:
        logger.warning(f"⚠️ Ошибка сканирования моделей: {e}")
        return _models_cache if _models_cache else {}


def get_all_available_models() -> List[str]:
    """Возвращает список всех доступных моделей Ollama.
    
    Returns:
        Список названий доступных моделей
    """
    models = scan_available_models()
    return sorted(models.keys())


def get_all_models_info() -> List[ModelInfo]:
    """Возвращает информацию о всех доступных моделях.
    
    Returns:
        Список ModelInfo отсортированный по качеству (лучшие первые)
    """
    models = scan_available_models()
    return sorted(models.values(), key=lambda m: m.estimated_quality, reverse=True)


def get_model_info(model_name: str) -> Optional[ModelInfo]:
    """Возвращает информацию о конкретной модели.
    
    Args:
        model_name: Название модели
        
    Returns:
        ModelInfo или None если модель не найдена
    """
    models = scan_available_models()
    return models.get(model_name)


def get_reasoning_model(min_quality: float = 0.7) -> Optional[str]:
    """Возвращает лучшую reasoning модель (DeepSeek-R1, QwQ и др.).
    
    Reasoning модели имеют встроенный chain-of-thought и рассуждают
    в <think> блоках. Они лучше справляются со сложными задачами.
    
    Args:
        min_quality: Минимальный порог качества (0.0-1.0)
        
    Returns:
        Название reasoning модели или None если не найдена
    """
    models = scan_available_models()
    if not models:
        return None
    
    # Фильтруем только reasoning модели
    reasoning_models = [
        m for m in models.values() 
        if m.is_reasoning and m.estimated_quality >= min_quality
    ]
    
    if not reasoning_models:
        logger.debug("🤖 Reasoning модели не найдены")
        return None
    
    # Выбираем лучшую: сначала по качеству, затем по размеру параметров
    # Это гарантирует выбор самой мощной модели при одинаковом качестве
    def _model_priority(m: ModelInfo) -> tuple[float, float]:
        """Приоритет модели: (качество, размер_параметров_в_миллиардах)."""
        # Парсим размер параметров для сравнения
        param_match = re.search(r'(\d+\.?\d*)', m.parameter_size)
        param_value = float(param_match.group(1)) if param_match else 0.0
        return (m.estimated_quality, param_value)
    
    best = max(reasoning_models, key=_model_priority)
    logger.info(
        f"🧠 Выбрана reasoning модель: {best.name} "
        f"(качество: {best.estimated_quality}, параметры: {best.parameter_size})"
    )
    return best.name


def get_all_reasoning_models() -> List[ModelInfo]:
    """Возвращает список всех доступных reasoning моделей.
    
    Returns:
        Список ModelInfo reasoning моделей, отсортированный по качеству
    """
    models = scan_available_models()
    reasoning = [m for m in models.values() if m.is_reasoning]
    return sorted(reasoning, key=lambda m: m.estimated_quality, reverse=True)


def get_best_model_for_complexity(
    complexity: TaskComplexity,
    prefer_coder: bool = True
) -> Optional[str]:
    """Выбирает лучшую модель для заданной сложности задачи.
    
    Логика выбора:
    - SIMPLE: быстрая модель (1.5B-4B), скорость важнее качества
    - MEDIUM: баланс (7B), хорошее качество
    - COMPLEX: максимальное качество (7B+ coder), качество важнее скорости
    
    Args:
        complexity: Сложность задачи
        prefer_coder: Предпочитать модели для кода
        
    Returns:
        Название оптимальной модели или None
    """
    models = scan_available_models()
    if not models:
        return None
    
    # Фильтруем embed модели
    candidates = [m for m in models.values() if 'embed' not in m.name.lower()]
    
    if not candidates:
        return list(models.keys())[0]
    
    # Определяем минимальное и максимальное качество для каждой сложности
    quality_ranges = {
        TaskComplexity.SIMPLE: (0.3, 0.7),    # Быстрые модели 1.5B-4B
        TaskComplexity.MEDIUM: (0.55, 1.0),   # 7B или хорошая coder
        TaskComplexity.COMPLEX: (0.7, 1.0),   # 7B+ coder или 13B+
    }
    
    min_quality, max_quality = quality_ranges[complexity]
    
    # Для SIMPLE задач выбираем МИНИМАЛЬНО подходящую модель (быстрее)
    # Для MEDIUM/COMPLEX выбираем ЛУЧШУЮ модель (качественнее)
    
    if prefer_coder:
        coder_models = [
            m for m in candidates 
            if m.is_coder and m.estimated_quality >= min_quality
        ]
        if coder_models:
            if complexity == TaskComplexity.SIMPLE:
                # Для simple выбираем минимально подходящую coder модель
                suitable = [m for m in coder_models if m.estimated_quality <= max_quality]
                if suitable:
                    best = min(suitable, key=lambda m: m.estimated_quality)
                else:
                    best = min(coder_models, key=lambda m: m.estimated_quality)
            else:
                # Для medium/complex выбираем лучшую
                best = max(coder_models, key=lambda m: m.estimated_quality)
            
            logger.info(f"🤖 Выбрана coder модель {best.name} (качество: {best.estimated_quality})")
            return best.name
    
    # Fallback: любая модель с достаточным качеством
    suitable = [m for m in candidates if m.estimated_quality >= min_quality]
    if suitable:
        if complexity == TaskComplexity.SIMPLE:
            # Для simple выбираем минимально подходящую
            best = min(suitable, key=lambda m: m.estimated_quality)
        else:
            # Для medium/complex выбираем лучшую
            best = max(suitable, key=lambda m: m.estimated_quality)
        
        logger.info(f"🤖 Выбрана модель {best.name} (качество: {best.estimated_quality})")
        return best.name
    
    # Если ничего не подходит, берём лучшую из доступных
    best = max(candidates, key=lambda m: m.estimated_quality)
    logger.warning(
        f"⚠️ Нет модели с качеством >= {min_quality}, "
        f"выбрана лучшая: {best.name} (качество: {best.estimated_quality})"
    )
    return best.name
