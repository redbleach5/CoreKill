# Развёртывание Cursor Killer

## Требования

- **Python 3.12+**
- **Node.js 18+**
- **Ollama** (локальные LLM модели)
- 8GB+ RAM (рекомендуется 16GB для 7B моделей)
- 20GB+ места на диске (для моделей)

## Development

### 1. Установка зависимостей

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

### 2. Установка моделей Ollama

```bash
# Запустите Ollama
ollama serve

# Установите модели (в другом терминале)
ollama pull qwen2.5-coder:7b    # Основная модель для кода
ollama pull phi3:mini            # Лёгкая модель для chat
ollama pull nomic-embed-text     # Embeddings для RAG

# Опционально: лёгкая fallback модель
ollama pull tinyllama:1.1b
```

### 3. Запуск

```bash
python run.py
```

Приложение: http://localhost:5173

## Production

### 1. Подготовка сервера

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.12 python3.12-venv nodejs npm nginx

# Создаём пользователя
sudo useradd -m -s /bin/bash cursor-killer
sudo su - cursor-killer
```

### 2. Установка Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh

# Запуск как сервис
sudo systemctl enable ollama
sudo systemctl start ollama

# Установка моделей
ollama pull qwen2.5-coder:7b
ollama pull phi3:mini
ollama pull nomic-embed-text
```

### 3. Установка приложения

```bash
git clone <repository-url> cursor-killer
cd cursor-killer

# Виртуальное окружение
python3.12 -m venv .venv
source .venv/bin/activate

# Зависимости
pip install -r requirements.txt

# Frontend build
cd frontend && npm install && npm run build && cd ..
```

### 4. Конфигурация

```bash
# Копируем и редактируем конфиг
cp .env.example .env
nano .env
```

Важные переменные для production:

```bash
ENVIRONMENT=production
DEBUG=false
ALLOWED_ORIGINS=https://your-domain.com
```

### 5. Systemd сервис

```bash
sudo nano /etc/systemd/system/cursor-killer.service
```

```ini
[Unit]
Description=Cursor Killer Backend
After=network.target ollama.service

[Service]
Type=simple
User=cursor-killer
WorkingDirectory=/home/cursor-killer/cursor-killer
Environment="PATH=/home/cursor-killer/cursor-killer/.venv/bin"
ExecStart=/home/cursor-killer/cursor-killer/.venv/bin/uvicorn backend.api:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cursor-killer
sudo systemctl start cursor-killer
```

### 6. Nginx reverse proxy

```bash
sudo nano /etc/nginx/sites-available/cursor-killer
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend (static files)
    location / {
        root /home/cursor-killer/cursor-killer/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
        
        # SSE support
        proxy_buffering off;
        proxy_read_timeout 86400;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/cursor-killer /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 7. SSL (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Docker (альтернатива)

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код
COPY . .

# Frontend build
RUN cd frontend && npm install && npm run build

EXPOSE 8000

CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      - ollama

volumes:
  ollama_data:
```

## Hardware рекомендации

| Модель | RAM | VRAM | Рекомендуется для |
|--------|-----|------|-------------------|
| tinyllama:1.1b | 4GB | 2GB | Быстрые ответы, chat |
| phi3:mini | 8GB | 4GB | Chat, простые задачи |
| qwen2.5-coder:7b | 16GB | 8GB | Генерация кода |
| qwen2.5-coder:14b | 32GB | 16GB | Сложные задачи |
| qwen2.5-coder:32b | 64GB | 24GB | Enterprise |

## Мониторинг

### Логи

```bash
# Backend логи
journalctl -u cursor-killer -f

# Ollama логи
journalctl -u ollama -f

# Приложение логи
tail -f logs/app.jsonl | jq
```

### Health check

```bash
# Backend
curl http://localhost:8000/api/health

# Ollama
curl http://localhost:11434/api/tags
```

## Troubleshooting

### Ollama не запускается

```bash
# Проверьте статус
sudo systemctl status ollama

# Перезапустите
sudo systemctl restart ollama
```

### Медленная генерация

1. Проверьте что используется GPU: `nvidia-smi`
2. Уменьшите размер модели в `config.toml`
3. Включите `allow_heavy_models = false` для использования меньших моделей

### Out of Memory

```bash
# Увеличьте swap
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### CORS ошибки

Проверьте `ALLOWED_ORIGINS` в `.env` — должен содержать URL фронтенда.
