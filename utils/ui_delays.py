"""Утилиты для получения задержек UI из конфигурации.

Позволяет сделать задержки опциональными для улучшения производительности.
Используется в workflow для плавности интерфейса.

Примеры использования:
    ```python
    from utils.ui_delays import ui_sleep, get_ui_delay
    
    # Задержка для обычных событий
    await ui_sleep("normal")
    
    # Задержка для критических событий (final_result и т.д.)
    await ui_sleep("critical")
    
    # Получить значение задержки (если нужно)
    delay = await get_ui_delay()
    if delay > 0:
        # Задержка UI: {delay} секунд
    ```

Зависимости:
    - asyncio: для асинхронных задержек
    - utils.config: для получения конфигурации

Связанные утилиты:
    - infrastructure.workflow_nodes: использует для плавности UI
    - backend.workflow_streamer: использует для задержек при стриминге

Примечания:
    - Задержки можно отключить в config.toml (enable_ui_smoothness_delays)
    - Если задержки отключены, функции возвращают 0.0
    - Используется только в UI режиме для улучшения UX
"""
import asyncio
from utils.config import get_config


async def get_ui_delay() -> float:
    """Возвращает задержку для UI событий.
    
    Returns:
        Задержка в секундах (0.0 если задержки отключены)
    """
    config = get_config()
    if config.enable_ui_smoothness_delays:
        return config.ui_delay_seconds
    return 0.0


async def get_critical_delay() -> float:
    """Возвращает задержку для критических событий (final_result и т.д.).
    
    Returns:
        Задержка в секундах (0.0 если задержки отключены)
    """
    config = get_config()
    if config.enable_ui_smoothness_delays:
        return config.critical_delay_seconds
    return 0.0


async def ui_sleep(delay_type: str = "normal") -> None:
    """Выполняет задержку для UI если она включена.
    
    Args:
        delay_type: Тип задержки ("normal" или "critical")
    """
    if delay_type == "critical":
        delay = await get_critical_delay()
    else:
        delay = await get_ui_delay()
    
    if delay > 0:
        await asyncio.sleep(delay)
