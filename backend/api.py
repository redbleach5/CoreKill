"""Основной FastAPI приложение для веб-интерфейса."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import agent
from backend.middleware.log_filter import setup_log_filter
from utils.logger import get_logger

# Инициализируем систему логирования при старте приложения
logger = get_logger()
logger.info("🚀 Backend API запущен")

# Создаём FastAPI приложение
app = FastAPI(
    title="Cursor Killer API",
    description="API для многоагентной системы генерации кода",
    version="1.0.0"
)

# Настраиваем фильтр логов для uvicorn (убирает model из логов для greeting)
# Вызываем сразу после создания app и также при старте приложения
setup_log_filter()

@app.on_event("startup")
async def setup_logging_filter() -> None:
    """Настраивает фильтр логов при старте приложения (повторно для надёжности)."""
    setup_log_filter()

# Настраиваем CORS для работы с frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Подключаем роутеры
app.include_router(agent.router)


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
    """Health check endpoint."""
    return {"status": "ok"}
