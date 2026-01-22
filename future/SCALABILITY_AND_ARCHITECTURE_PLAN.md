# План масштабируемости и архитектурных улучшений

## Дата: 2026-01-21

---

## 🎯 Цели масштабирования

### Текущие ограничения
- **Однопользовательский режим:** Только один пользователь одновременно
- **Синхронная обработка:** Задачи выполняются последовательно
- **In-memory состояние:** Нет персистентности задач между перезапусками
- **Локальные ресурсы:** Привязка к одной машине с Ollama
- **Отсутствие очередей:** Нет управления приоритетами задач

### Целевые показатели (через 6-12 месяцев)
- **100+ одновременных пользователей**
- **1000+ задач в день**
- **< 5s latency для простых задач**
- **99.9% uptime**
- **Horizontal scaling** (добавление серверов)

---

## 📊 Текущая vs Целевая архитектура

### Текущая (монолитная)

```
┌─────────────────────────────────────────────┐
│              Single Process                  │
│                                              │
│  ┌──────────┐    ┌──────────┐   ┌────────┐ │
│  │ Frontend │ -> │ FastAPI  │ ->│ Ollama │ │
│  │  (Vite)  │    │ Backend  │   │ (Local)│ │
│  └──────────┘    └──────────┘   └────────┘ │
│                        │                     │
│                        v                     │
│                   ┌─────────┐               │
│                   │ ChromaDB│               │
│                   │ (Local) │               │
│                   └─────────┘               │
└─────────────────────────────────────────────┘

ПРОБЛЕМЫ:
- Один сервер = single point of failure
- Нет горизонтального масштабирования
- LLM блокирует другие запросы
- Нет распределённого кэша
```

### Целевая (микросервисная + очереди)

```
┌─────────────────────────────────────────────────────────────┐
│                        Load Balancer (nginx)                 │
└─────────┬───────────────────────────────────────────────────┘
          │
          v
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  API     │  │  API     │  │  API     │  (Horizontal      │
│  │ Instance │  │ Instance │  │ Instance │   scaling)        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
└───────┼────────────-┼─────────────┼────────────────────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────────────┐
│                      Message Queue (Redis)                   │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Priority │  │ Standard │  │   Batch  │  (Task queues)   │
│  │  Queue   │  │  Queue   │  │  Queue   │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
└───────┼────────────-┼─────────────┼────────────────────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────────────┐
│                       Worker Pool                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Worker 1 │  │ Worker 2 │  │ Worker N │  (Auto-scale)    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
└───────┼────────────-┼─────────────┼────────────────────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────────────┐
│                   Backend Services                           │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐  │
│  │  Ollama  │  │  Ollama  │  │  ChromaDB │  │  Redis   │  │
│  │ Server 1 │  │ Server 2 │  │ Cluster   │  │  Cache   │  │
│  └──────────┘  └──────────┘  └───────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘

ПРЕИМУЩЕСТВА:
✅ Horizontal scaling
✅ Load balancing
✅ Task queues с приоритетами
✅ Fault tolerance
✅ Distributed caching
✅ Independent scaling компонентов
```

---

## 🏗️ Поэтапный план миграции

### Фаза 1: Очереди задач (1-2 недели)

**Цель:** Разделить API и обработку задач

**Технологии:** 
- **Redis** (message broker)
- **Celery** или **RQ** (task queue)

**Реализация:**

```python
# infrastructure/task_queue.py
"""Система очередей задач."""

from celery import Celery
from kombu import Queue, Exchange
from typing import Dict, Any
import redis

app = Celery('cursor_killer')

# Конфигурация
app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/1',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Очереди с приоритетами
    task_queues=[
        Queue('priority', Exchange('priority'), routing_key='priority'),
        Queue('standard', Exchange('standard'), routing_key='standard'),
        Queue('batch', Exchange('batch'), routing_key='batch'),
    ],
    
    # Routing
    task_routes={
        'tasks.generate_code_priority': {'queue': 'priority'},
        'tasks.generate_code': {'queue': 'standard'},
        'tasks.batch_process': {'queue': 'batch'},
    },
    
    # Limits
    task_time_limit=600,  # 10 минут
    task_soft_time_limit=540,  # 9 минут (soft limit)
    worker_max_tasks_per_child=100,  # Перезапуск после 100 задач
)

# Task definitions
@app.task(name='tasks.generate_code', bind=True)
def generate_code_task(self, task_id: str, params: Dict[str, Any]):
    """Фоновая задача генерации кода."""
    from infrastructure.workflow_graph import create_workflow
    from infrastructure.task_checkpointer import TaskCheckpointer
    
    try:
        # Создаём workflow
        workflow = create_workflow()
        
        # Обновляем статус
        self.update_state(state='PROCESSING', meta={'stage': 'intent'})
        
        # Запускаем
        result = workflow.invoke(params)
        
        # Сохраняем результат
        checkpointer = TaskCheckpointer()
        checkpointer.save_checkpoint(task_id, result, status='completed')
        
        return {'status': 'success', 'result': result}
        
    except Exception as e:
        # Retry с exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

@app.task(name='tasks.generate_code_priority')
def generate_code_priority(task_id: str, params: Dict[str, Any]):
    """Приоритетная задача."""
    return generate_code_task.apply_async(
        args=[task_id, params],
        queue='priority'
    )
```

**API интеграция:**

```python
# backend/routers/agent.py

from infrastructure.task_queue import generate_code_task
from infrastructure.task_checkpointer import TaskCheckpointer

@router.post("/api/tasks")
async def create_task(request: TaskRequest):
    """Создаёт задачу и помещает в очередь."""
    
    # Генерируем ID
    task_id = str(uuid.uuid4())
    
    # Отправляем в очередь
    celery_task = generate_code_task.apply_async(
        args=[task_id, request.dict()],
        task_id=task_id
    )
    
    return {
        "task_id": task_id,
        "status": "queued",
        "check_url": f"/api/tasks/{task_id}"
    }

@router.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Проверяет статус задачи."""
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id)
    
    if result.state == 'PENDING':
        return {"status": "queued"}
    elif result.state == 'PROCESSING':
        return {"status": "processing", "meta": result.info}
    elif result.state == 'SUCCESS':
        checkpointer = TaskCheckpointer()
        checkpoint = checkpointer.load_checkpoint(task_id)
        return {"status": "completed", "result": checkpoint}
    else:
        return {"status": "failed", "error": str(result.info)}
```

**Frontend polling:**

```tsx
// frontend/src/hooks/useTaskPolling.ts
import { useState, useEffect } from 'react'

export function useTaskPolling(taskId: string, interval = 2000) {
  const [status, setStatus] = useState<'queued' | 'processing' | 'completed' | 'failed'>('queued')
  const [result, setResult] = useState(null)
  
  useEffect(() => {
    const poll = async () => {
      const res = await fetch(`/api/tasks/${taskId}`)
      const data = await res.json()
      
      setStatus(data.status)
      
      if (data.status === 'completed') {
        setResult(data.result)
      }
    }
    
    const timer = setInterval(poll, interval)
    
    // Останавливаем polling при завершении
    if (status === 'completed' || status === 'failed') {
      clearInterval(timer)
    }
    
    return () => clearInterval(timer)
  }, [taskId, status, interval])
  
  return { status, result }
}
```

**Checklist:**
- [ ] Установить Redis
- [ ] Настроить Celery/RQ
- [ ] Создать task definitions
- [ ] API endpoints для задач
- [ ] Frontend polling
- [ ] Мониторинг очередей (Flower для Celery)
- [ ] Graceful shutdown workers

---

### Фаза 2: Распределённое кэширование (1 неделя)

**Цель:** Shared cache между инстансами API

```python
# infrastructure/distributed_cache.py
"""Распределённый кэш через Redis."""

import redis
import json
import hashlib
from typing import Optional, Any
from functools import wraps

class DistributedCache:
    """Redis-based distributed cache."""
    
    def __init__(self, host='localhost', port=6379, db=2):
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )
    
    def get(self, key: str) -> Optional[Any]:
        """Получает значение из кэша."""
        value = self.redis.get(key)
        return json.loads(value) if value else None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """Сохраняет значение в кэш."""
        self.redis.setex(
            key,
            ttl,
            json.dumps(value)
        )
    
    def delete(self, key: str):
        """Удаляет значение из кэша."""
        self.redis.delete(key)
    
    def invalidate_pattern(self, pattern: str):
        """Удаляет все ключи по паттерну."""
        for key in self.redis.scan_iter(match=pattern):
            self.redis.delete(key)

# Декоратор для кэширования
def cached(ttl: int = 3600, key_prefix: str = ""):
    """Декоратор для кэширования результатов функции."""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Генерируем ключ кэша
            cache_key = _generate_cache_key(key_prefix, func.__name__, args, kwargs)
            
            # Проверяем кэш
            cache = DistributedCache()
            cached_value = cache.get(cache_key)
            
            if cached_value is not None:
                return cached_value
            
            # Вычисляем и кэшируем
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator

def _generate_cache_key(prefix: str, func_name: str, args, kwargs) -> str:
    """Генерирует ключ кэша."""
    # Сериализуем аргументы
    args_str = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True)
    args_hash = hashlib.md5(args_str.encode()).hexdigest()
    
    return f"{prefix}:{func_name}:{args_hash}"
```

**Использование:**

```python
# agents/researcher.py

from infrastructure.distributed_cache import cached

class ResearcherAgent:
    
    @cached(ttl=7200, key_prefix="research")  # 2 часа
    def research(self, query: str, intent_type: str, **kwargs) -> str:
        """Исследование с кэшированием."""
        # ... существующая логика ...
        return context
```

**Checklist:**
- [ ] Redis для кэша
- [ ] Distributed cache класс
- [ ] Декоратор @cached
- [ ] Кэширование частых запросов
- [ ] Cache invalidation стратегия
- [ ] Мониторинг hit rate

---

### Фаза 3: Database для персистентности (1-2 недели)

**Цель:** Сохранение состояния задач, пользователей, настроек

**Технология:** PostgreSQL

```python
# infrastructure/database.py
"""PostgreSQL database для персистентности."""

from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum
from datetime import datetime

Base = declarative_base()

class TaskStatus(enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task(Base):
    """Модель задачи."""
    __tablename__ = 'tasks'
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)  # Для multi-user
    status = Column(Enum(TaskStatus), default=TaskStatus.QUEUED)
    
    # Входные данные
    task_description = Column(String, nullable=False)
    intent_type = Column(String)
    complexity = Column(String)
    model = Column(String)
    
    # Результат
    result = Column(JSON, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Метрики
    duration_seconds = Column(Integer, nullable=True)
    quality_score = Column(Integer, nullable=True)

class User(Base):
    """Модель пользователя."""
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True)
    api_key = Column(String, unique=True)
    
    # Квоты
    monthly_quota = Column(Integer, default=1000)
    used_quota = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)

# Database session
engine = create_engine('postgresql://user:pass@localhost/cursor_killer')
SessionLocal = sessionmaker(bind=engine)

def get_db():
    """Dependency для FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Checklist:**
- [ ] PostgreSQL setup
- [ ] SQLAlchemy models
- [ ] Alembic migrations
- [ ] CRUD operations
- [ ] Connection pooling
- [ ] Backup strategy

---

### Фаза 4: Horizontal Scaling + Load Balancer (1 неделя)

**Цель:** Несколько инстансов API за load balancer

**nginx config:**

```nginx
# /etc/nginx/sites-available/cursor-killer

upstream api_backend {
    least_conn;  # Least connections балансировка
    
    server 127.0.0.1:8001 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8002 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8003 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.cursor-killer.com;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req zone=api_limit burst=20 nodelay;
    
    # Timeouts
    proxy_connect_timeout 10s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    
    location /api/ {
        proxy_pass http://api_backend;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
    }
    
    # Static files
    location / {
        root /var/www/cursor-killer/frontend/dist;
        try_files $uri /index.html;
    }
}
```

**Systemd для множественных инстансов:**

```ini
# /etc/systemd/system/cursor-killer-api@.service

[Unit]
Description=Cursor Killer API Instance %i
After=network.target

[Service]
Type=notify
User=cursor
WorkingDirectory=/opt/cursor-killer
Environment="PORT=800%i"

ExecStart=/opt/cursor-killer/.venv/bin/uvicorn \
    backend.api:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --log-level info

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Запуск 3 инстансов
systemctl enable cursor-killer-api@1
systemctl enable cursor-killer-api@2
systemctl enable cursor-killer-api@3

systemctl start cursor-killer-api@{1,2,3}
```

**Checklist:**
- [ ] nginx setup
- [ ] Systemd services
- [ ] Health checks
- [ ] Session affinity (if needed)
- [ ] SSL/TLS (certbot)
- [ ] Monitoring (Prometheus)

---

### Фаза 5: Ollama Cluster (2-3 недели)

**Цель:** Несколько серверов Ollama для LLM

**Архитектура:**

```
┌──────────────────────────────────────────┐
│         Ollama Load Balancer             │
│  (Round-robin между серверами Ollama)    │
└─────────┬────────────────────────────────┘
          │
    ┌─────┴─────┬────────────┐
    │           │            │
    v           v            v
┌────────┐  ┌────────┐  ┌────────┐
│Ollama 1│  │Ollama 2│  │Ollama 3│
│GPU 0-1 │  │GPU 2-3 │  │GPU 4-5 │
└────────┘  └────────┘  └────────┘
```

```python
# infrastructure/ollama_cluster.py
"""Кластер Ollama серверов с балансировкой."""

from typing import List, Optional
import httpx
import random
from dataclasses import dataclass

@dataclass
class OllamaNode:
    """Узел кластера Ollama."""
    host: str
    port: int
    gpu_ids: List[int]
    max_concurrent: int = 2
    current_load: int = 0

class OllamaCluster:
    """Менеджер кластера Ollama."""
    
    def __init__(self):
        self.nodes: List[OllamaNode] = [
            OllamaNode(host="gpu1.local", port=11434, gpu_ids=[0, 1]),
            OllamaNode(host="gpu2.local", port=11434, gpu_ids=[2, 3]),
            OllamaNode(host="gpu3.local", port=11434, gpu_ids=[4, 5]),
        ]
        self.client = httpx.AsyncClient()
    
    def get_available_node(self) -> Optional[OllamaNode]:
        """Находит доступный узел (least loaded)."""
        available = [n for n in self.nodes if n.current_load < n.max_concurrent]
        
        if not available:
            return None
        
        # Least loaded
        return min(available, key=lambda n: n.current_load)
    
    async def generate(self, model: str, prompt: str, **kwargs):
        """Генерирует через доступный узел."""
        node = self.get_available_node()
        
        if not node:
            raise Exception("Все узлы заняты")
        
        try:
            node.current_load += 1
            
            response = await self.client.post(
                f"http://{node.host}:{node.port}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    **kwargs
                },
                timeout=600.0
            )
            
            return response.json()
            
        finally:
            node.current_load -= 1
    
    async def health_check(self) -> Dict[str, bool]:
        """Проверяет здоровье узлов."""
        health = {}
        
        for node in self.nodes:
            try:
                response = await self.client.get(
                    f"http://{node.host}:{node.port}/api/tags",
                    timeout=5.0
                )
                health[f"{node.host}:{node.port}"] = response.status_code == 200
            except:
                health[f"{node.host}:{node.port}"] = False
        
        return health
```

**Checklist:**
- [ ] Ollama на нескольких серверах
- [ ] Load balancer для Ollama
- [ ] Health checks
- [ ] Failover logic
- [ ] Model sync между узлами
- [ ] GPU monitoring

---

### Фаза 6: Monitoring & Alerting (1 неделя)

**Технологии:**
- **Prometheus** - метрики
- **Grafana** - дашборды
- **AlertManager** - алерты

```python
# infrastructure/metrics_exporter.py
"""Prometheus metrics exporter."""

from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Метрики
task_counter = Counter('tasks_total', 'Total tasks', ['status', 'intent_type'])
task_duration = Histogram('task_duration_seconds', 'Task duration', ['intent_type'])
active_tasks = Gauge('tasks_active', 'Active tasks')
queue_size = Gauge('queue_size', 'Queue size', ['queue_name'])

def record_task_start(intent_type: str):
    """Записывает начало задачи."""
    active_tasks.inc()
    task_counter.labels(status='started', intent_type=intent_type).inc()

def record_task_complete(intent_type: str, duration: float, success: bool):
    """Записывает завершение задачи."""
    active_tasks.dec()
    
    status = 'success' if success else 'failed'
    task_counter.labels(status=status, intent_type=intent_type).inc()
    
    task_duration.labels(intent_type=intent_type).observe(duration)

# Запуск exporter
if __name__ == '__main__':
    start_http_server(9090)
    
    while True:
        # Update queue sizes
        from infrastructure.task_queue import app
        inspector = app.control.inspect()
        
        active = inspector.active()
        for queue_name, tasks in active.items():
            queue_size.labels(queue_name=queue_name).set(len(tasks))
        
        time.sleep(15)
```

**Grafana dashboard:**

```json
{
  "dashboard": {
    "title": "Cursor Killer Metrics",
    "panels": [
      {
        "title": "Tasks per Minute",
        "targets": [
          {
            "expr": "rate(tasks_total[1m])"
          }
        ]
      },
      {
        "title": "Task Duration (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, task_duration_seconds)"
          }
        ]
      },
      {
        "title": "Active Tasks",
        "targets": [
          {
            "expr": "tasks_active"
          }
        ]
      }
    ]
  }
}
```

**Checklist:**
- [ ] Prometheus setup
- [ ] Metrics exporter
- [ ] Grafana dashboards
- [ ] Alerts (Slack/Email)
- [ ] SLA monitoring

---

## 🎯 Результаты после всех фаз

### Производительность
- ✅ 100+ одновременных пользователей
- ✅ Horizontal scaling (добавление серверов)
- ✅ < 5s latency для простых задач
- ✅ Task queues с приоритетами
- ✅ Distributed caching

### Надёжность
- ✅ 99.9% uptime через load balancing
- ✅ Graceful degradation при сбоях
- ✅ Auto-recovery
- ✅ Backup & disaster recovery

### Мониторинг
- ✅ Real-time метрики
- ✅ Dashboards в Grafana
- ✅ Alerts при проблемах
- ✅ Logging aggregation

---

## 💰 Оценка стоимости инфраструктуры

### Минимальная конфигурация (100 пользователей)

**Сервера:**
- 3x API (4 CPU, 8GB RAM) = $60/мес
- 2x Ollama GPU (RTX 3090) = $200/мес (аренда GPU VPS)
- 1x PostgreSQL (2 CPU, 4GB) = $20/мес
- 1x Redis (1 CPU, 2GB) = $10/мес

**Итого:** ~$290/мес

### Средняя конфигурация (1000 пользователей)

- 5x API = $100/мес
- 5x Ollama GPU = $500/мес
- 1x PostgreSQL (4 CPU, 8GB) = $40/мес
- 1x Redis Cluster = $30/мес
- 1x nginx LB = $10/мес

**Итого:** ~$680/мес

---

## 📋 Checklist миграции

### Подготовка
- [ ] Backup текущей системы
- [ ] Документация процесса миграции
- [ ] Rollback plan

### Фаза 1: Очереди
- [ ] Redis setup
- [ ] Celery/RQ integration
- [ ] Task endpoints
- [ ] Frontend polling
- [ ] Мониторинг очередей

### Фаза 2: Кэширование
- [ ] Redis cache
- [ ] Distributed cache класс
- [ ] Cache decorators
- [ ] Hit rate monitoring

### Фаза 3: Database
- [ ] PostgreSQL setup
- [ ] SQLAlchemy models
- [ ] Migrations (Alembic)
- [ ] Backup стратегия

### Фаза 4: Scaling
- [ ] nginx load balancer
- [ ] Multiple API instances
- [ ] Health checks
- [ ] SSL/TLS

### Фаза 5: Ollama Cluster
- [ ] Multiple Ollama servers
- [ ] Load balancer
- [ ] Failover
- [ ] Model sync

### Фаза 6: Monitoring
- [ ] Prometheus
- [ ] Grafana
- [ ] Alerts
- [ ] Logging

---

**Автор:** AI Assistant  
**Дата создания:** 2026-01-21  
**Версия:** 1.0
