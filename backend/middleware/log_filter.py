"""Фильтр логов для uvicorn access logs.

Убирает параметр model из логов для greeting запросов,
так как модель не используется для greeting.

ПРИМЕЧАНИЕ: Uvicorn логирует через стандартный Python logging,
а не через LogManager из infrastructure/logging. Этот фильтр применяется
напрямую к стандартному логгеру uvicorn.access, что корректно, так как
uvicorn access logs не проходят через основную систему логирования.
"""
import logging
from urllib.parse import unquote, parse_qs, urlencode


def _is_greeting(task: str) -> bool:
    """Проверяет, является ли task приветствием (та же логика что в IntentAgent)."""
    from utils.helpers import is_greeting
    return is_greeting(task)


# AccessLogMiddleware не нужен - фильтр логов работает на уровне logging.Filter
# Оставляем только GreetingLogFilter


class GreetingLogFilter(logging.Filter):
    """Фильтр для логов uvicorn.access.
    
    Убирает параметр model из логов для greeting запросов.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Фильтрует логи, убирая model из URL для greeting."""
        # Получаем полное сообщение (может быть в msg или сформировано из args)
        # Сначала пробуем получить через getMessage, если нет - используем msg напрямую
        try:
            msg = record.getMessage() if hasattr(record, "getMessage") else str(record.msg)
        except Exception as e:
            # Используем sys.stderr чтобы избежать циклических вызовов логгера
            import sys
            sys.stderr.write(f"GreetingLogFilter: ошибка получения сообщения: {e}\n")
            msg = str(record.msg) if hasattr(record, "msg") else ""
        
        # Проверяем, содержит ли сообщение /api/stream и model
        if "/api/stream" in msg and "?" in msg and "model=" in msg:
            try:
                # Парсим URL из сообщения uvicorn
                # Формат: "127.0.0.1:60294 - "GET /api/stream?task=...&model=... HTTP/1.1" 200 OK"
                # Ищем часть между "/api/stream?" и " HTTP"
                if "/api/stream?" in msg:
                    # Извлекаем query часть (между "?" и " HTTP")
                    parts = msg.split("/api/stream?")
                    if len(parts) > 1:
                        query_and_rest = parts[1]
                        # Ищем где заканчивается query (перед " HTTP")
                        if " HTTP" in query_and_rest:
                            query_part = query_and_rest.split(" HTTP")[0]
                            query_params = parse_qs(query_part)
                            
                            # Проверяем, является ли task приветствием
                            task = query_params.get("task", [""])[0]
                            if task:
                                task_decoded = unquote(task)
                                if _is_greeting(task_decoded) and "model" in query_params:
                                    # Удаляем model из параметров
                                    filtered_params = {k: v for k, v in query_params.items() if k != "model"}
                                    # Собираем новый query string
                                    new_query = urlencode(filtered_params, doseq=True)
                                    # Заменяем в сообщении - ищем точное вхождение
                                    old_query_part = f"/api/stream?{query_part}"
                                    new_query_part = f"/api/stream?{new_query}" if new_query else "/api/stream"
                                    
                                    # Заменяем в record.msg (если это строка)
                                    if isinstance(record.msg, str):
                                        record.msg = record.msg.replace(old_query_part, new_query_part)
                                    
                                    # Также обновляем args если они есть (uvicorn может использовать форматирование)
                                    if hasattr(record, "args") and record.args:
                                        # args может быть кортежем, преобразуем в список для изменения
                                        args_list = list(record.args) if isinstance(record.args, tuple) else list(record.args)
                                        for i, arg in enumerate(args_list):
                                            if isinstance(arg, str) and old_query_part in arg:
                                                args_list[i] = arg.replace(old_query_part, new_query_part)
                                        record.args = tuple(args_list) if isinstance(record.args, tuple) else args_list  # type: ignore[assignment]  # LogRecord.args может быть tuple или list, мы нормализуем тип
            except Exception as e:
                # Логируем ошибку для отладки (но не через наш логгер, чтобы не было циклических вызовов)
                import sys
                sys.stderr.write(f"GreetingLogFilter error: {e}\n")
        
        return True


def setup_log_filter() -> None:
    """Настраивает фильтр логов для uvicorn.access."""
    access_logger = logging.getLogger("uvicorn.access")
    # Убираем существующие фильтры этого типа
    access_logger.filters = [f for f in access_logger.filters if not isinstance(f, GreetingLogFilter)]
    # Добавляем наш фильтр
    access_logger.addFilter(GreetingLogFilter())
    
    # Также применяем фильтр ко всем handler'ам логгера
    # (на случай если uvicorn использует handler'ы напрямую)
    for handler in access_logger.handlers:
        # Убираем существующие фильтры этого типа из handler
        handler.filters = [f for f in handler.filters if not isinstance(f, GreetingLogFilter)]
        # Добавляем наш фильтр в handler
        handler.addFilter(GreetingLogFilter())
    
    # Также применяем фильтр к root logger (на случай если uvicorn использует его)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        # Проверяем, что это handler для uvicorn.access (по имени или классу)
        handler_name = getattr(handler, 'name', '')
        if handler_name and ('uvicorn' in handler_name.lower() or 'access' in handler_name.lower()):
            handler.filters = [f for f in handler.filters if not isinstance(f, GreetingLogFilter)]
            handler.addFilter(GreetingLogFilter())
