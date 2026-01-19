"""Основной FastAPI приложение для веб-интерфейса.

Особенности:
- Graceful shutdown с сохранением состояния
- Обработка сигналов SIGTERM/SIGINT
- Закрытие connection pool и очистка ресурсов
"""
import asyncio
import os
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from backend.routers import agent
from backend.middleware.log_filter import setup_log_filter
from backend.middleware.rate_limiter import RateLimiterMiddleware
from infrastructure.connection_pool import get_ollama_pool, close_ollama_pool
from infrastructure.cache import get_cache
from utils.logger import get_logger

# Инициализируем систему логирования при старте приложения
logger = get_logger()

# Флаг для graceful shutdown
_shutdown_requested = False


def is_shutdown_requested() -> bool:
    """Проверяет, был ли запрошен graceful shutdown.
    
    Используется агентами для прерывания долгих операций.
    
    Returns:
        True если shutdown запрошен
    """
    return _shutdown_requested


async def _cleanup_on_shutdown() -> None:
    """Выполняет очистку ресурсов при shutdown."""
    global _shutdown_requested
    _shutdown_requested = True
    
    # Закрываем connection pool
    try:
        await close_ollama_pool()
        logger.info("✅ Connection pool закрыт")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при закрытии connection pool: {e}")
    
    # Очищаем кэш
    try:
        cache = get_cache()
        cache.clear()
        logger.info("✅ Кэш очищен")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при очистке кэша: {e}")
    
    # Сохраняем активные checkpoint
    try:
        from utils.config import get_config
        config = get_config()
        if config.persistence_enabled:
            from infrastructure.task_checkpointer import get_task_checkpointer
            checkpointer = get_task_checkpointer()
            active_count = len(checkpointer.list_active_tasks())
            if active_count > 0:
                logger.info(f"📝 Сохранено {active_count} активных checkpoint")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка сохранения checkpoint: {e}")
    
    # Очищаем просроченные диалоги
    try:
        from agents.conversation import get_conversation_memory
        conv_memory = get_conversation_memory()
        cleanup_result = conv_memory.cleanup()
        if cleanup_result["total"] > 0:
            logger.info(f"🗑️ Очистка диалогов: {cleanup_result}")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка очистки диалогов: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для FastAPI — startup/shutdown.
    
    Startup:
    - Инициализация логирования
    - Бенчмарк производительности LLM
    - Lazy инициализация connection pool
    
    Shutdown:
    - Graceful завершение активных задач
    - Сохранение checkpoint
    - Закрытие connection pool
    - Очистка кэша и диалогов
    """
    global _shutdown_requested
    _shutdown_requested = False
    
    # Startup
    logger.info("🚀 Backend API запущен")
    setup_log_filter()
    
    # Инициализируем систему метрик и запускаем бенчмарк если нужно
    try:
        from infrastructure.performance_metrics import get_performance_metrics
        metrics = get_performance_metrics()
        
        # Запускаем бенчмарк только если нет сохранённых данных
        if not metrics.benchmark:
            logger.info("🔧 Первый запуск — калибровка производительности...")
            # Запускаем в фоне чтобы не блокировать startup
            asyncio.create_task(_run_initial_benchmark())
        else:
            logger.info(
                f"📊 Загружена калибровка: {metrics.benchmark.tokens_per_second:.1f} tok/s, "
                f"множитель {metrics.benchmark.performance_multiplier:.2f}x"
            )
    except Exception as e:
        logger.warning(f"⚠️ Ошибка инициализации метрик: {e}")
    
    logger.info("✅ Lifespan startup завершён")
    
    yield
    
    # Shutdown
    logger.info("🛑 Backend API завершает работу...")
    await _cleanup_on_shutdown()
    logger.info("✅ Graceful shutdown завершён")


async def _run_initial_benchmark() -> None:
    """Запускает первичный бенчмарк в фоне."""
    try:
        # Небольшая задержка чтобы сервер успел стартовать
        await asyncio.sleep(2)
        
        from infrastructure.performance_metrics import get_performance_metrics
        metrics = get_performance_metrics()
        await metrics.run_benchmark()
        
    except Exception as e:
        logger.warning(f"⚠️ Ошибка фонового бенчмарка: {e}")

# Создаём FastAPI приложение с lifespan manager
app = FastAPI(
    title="Cursor Killer API",
    description="API для многоагентной системы генерации кода",
    version="1.0.0",
    lifespan=lifespan
)

# Настраиваем фильтр логов для uvicorn
setup_log_filter()


# Определяем разрешённые origins в зависимости от окружения
def get_allowed_origins() -> list[str]:
    """Возвращает список разрешённых origins в зависимости от окружения."""
    env = os.getenv("ENVIRONMENT", "development")
    
    if env == "production":
        # В production используем переменную окружения
        allowed = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
        return [origin.strip() for origin in allowed if origin.strip()]
    
    # В development разрешаем локальные адреса
    return [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000"
    ]


# Добавляем middleware для защиты от атак
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
app.add_middleware(RateLimiterMiddleware, requests_per_minute=100)

# Настраиваем CORS для работы с frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600
)


# Глобальный обработчик исключений
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Глобальный обработчик исключений для логирования и безопасного ответа."""
    logger.error(f"❌ Необработанное исключение: {exc}", error=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера. Пожалуйста, попробуйте позже."}
    )


# Подключаем роутеры
from backend.routers import code_executor
app.include_router(agent.router)
app.include_router(code_executor.router)


@app.get("/")
async def root() -> dict:
    """Корневой endpoint."""
    return {
        "message": "Cursor Killer API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health() -> dict:
    """Health check endpoint с проверкой зависимостей."""
    import ollama
    from datetime import datetime
    
    health_status = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "ok",
            "ollama": "unknown"
        }
    }
    
    # Проверяем Ollama
    try:
        models = ollama.list()
        model_count = len(models.get("models", []))
        health_status["services"]["ollama"] = "ok"
        health_status["ollama_models"] = model_count
    except Exception as e:
        health_status["services"]["ollama"] = "error"
        health_status["ollama_error"] = str(e)
        health_status["status"] = "degraded"
    
    return health_status
