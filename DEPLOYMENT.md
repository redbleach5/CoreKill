# Развёртывание Cursor Killer

## Требования

- Python 3.9+
- Node.js 16+
- Ollama (для локальных LLM моделей)
- 8GB+ RAM (рекомендуется 16GB)
- 50GB+ свободного места на диске

## Development

### 1. Установка зависимостей

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

### 2. Запуск Ollama

```bash
# Скачайте и запустите Ollama
ollama serve

# В другом терминале, скачайте модели
ollama pull codellama:7b
ollama pull phi3:mini
ollama pull nomic-embed-text
```

### 3. Запуск приложения

```bash
# Backend (в одном терминале)
python run.py

# Frontend (в другом терминале)
cd frontend
npm run dev
```

Приложение будет доступно на http://localhost:5173

## Production

### 1. Подготовка сервера

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем зависимости
sudo apt install -y python3.11 python3.11-venv nodejs npm nginx supervisor

# Создаём пользователя для приложения
sudo useradd -m -s /bin/bash cursor-killer
sudo su - cursor-killer
```

### 2. Установка приложения

```bash
# Клонируем репозиторий
git clone https://github.com/redbleach5/-2121.git cursor-killer
cd cursor-killer

# Создаём виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Собираем frontend
cd frontend
npm install
npm run build
cd ..
```

### 3. Конфигурация

```bash
# Копируем пример конфигурации
cp .env.example .env

# Редактируем .env для production
nano .env
```

Важные переменные для production:

```env
ENVIRONMENT=production
ALLOWED_ORIGINS=https://yourdomain.com
DEBUG=false
LOG_LEVEL=WARNING
```

### 4. Настройка Ollama

```bash
# Устанавливаем Ollama
curl https://ollama.ai/install.sh | sh

# Запускаем как сервис
sudo systemctl start ollama
sudo systemctl enable ollama

# Скачиваем модели
ollama pull codellama:7b
ollama pull phi3:mini
ollama pull nomic-embed-text
```

### 5. Настройка Supervisor для Backend

```bash
# Создаём конфиг supervisor
sudo nano /etc/supervisor/conf.d/cursor-killer.conf
```

Содержимое:

```ini
[program:cursor-killer-backend]
directory=/home/cursor-killer/cursor-killer
command=/home/cursor-killer/cursor-killer/venv/bin/uvicorn backend.api:app --host 127.0.0.1 --port 8000 --workers 4
user=cursor-killer
autostart=true
autorestart=true
stderr_logfile=/var/log/cursor-killer-backend.err.log
stdout_logfile=/var/log/cursor-killer-backend.out.log
environment=ENVIRONMENT=production
```

Запуск:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start cursor-killer-backend
```

### 6. Настройка Nginx

```bash
# Создаём конфиг Nginx
sudo nano /etc/nginx/sites-available/cursor-killer
```

Содержимое:

```nginx
upstream cursor_killer_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;

    # Редирект на HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Frontend
    location / {
        root /home/cursor-killer/cursor-killer/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://cursor_killer_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    # Health check
    location /health {
        proxy_pass http://cursor_killer_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

Активируем сайт:

```bash
sudo ln -s /etc/nginx/sites-available/cursor-killer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 7. SSL сертификат (Let's Encrypt)

```bash
# Устанавливаем Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получаем сертификат
sudo certbot certonly --nginx -d yourdomain.com

# Автоматическое обновление
sudo systemctl enable certbot.timer
```

### 8. Мониторинг

```bash
# Проверяем статус приложения
sudo supervisorctl status cursor-killer-backend

# Просмотр логов
tail -f /var/log/cursor-killer-backend.out.log
tail -f /var/log/cursor-killer-backend.err.log

# Проверяем health
curl https://yourdomain.com/health
```

## Масштабирование

### Несколько инстансов Backend

```ini
[program:cursor-killer-backend-1]
command=/home/cursor-killer/cursor-killer/venv/bin/uvicorn backend.api:app --host 127.0.0.1 --port 8001 --workers 2

[program:cursor-killer-backend-2]
command=/home/cursor-killer/cursor-killer/venv/bin/uvicorn backend.api:app --host 127.0.0.1 --port 8002 --workers 2

[program:cursor-killer-backend-3]
command=/home/cursor-killer/cursor-killer/venv/bin/uvicorn backend.api:app --host 127.0.0.1 --port 8003 --workers 2
```

Обновляем Nginx:

```nginx
upstream cursor_killer_backend {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}
```

## Резервное копирование

```bash
# Создаём скрипт резервного копирования
cat > /home/cursor-killer/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/cursor-killer"
mkdir -p $BACKUP_DIR

# Резервируем базу данных
tar -czf $BACKUP_DIR/db-$(date +%Y%m%d-%H%M%S).tar.gz /home/cursor-killer/cursor-killer/data/

# Удаляем старые резервные копии (старше 30 дней)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
EOF

chmod +x /home/cursor-killer/backup.sh

# Добавляем в cron (ежедневно в 2 часа ночи)
(crontab -l 2>/dev/null; echo "0 2 * * * /home/cursor-killer/backup.sh") | crontab -
```

## Обновление

```bash
cd /home/cursor-killer/cursor-killer

# Получаем обновления
git pull origin main

# Обновляем зависимости
source venv/bin/activate
pip install -r requirements.txt

# Собираем frontend
cd frontend
npm install
npm run build
cd ..

# Перезагружаем приложение
sudo supervisorctl restart cursor-killer-backend
```

## Troubleshooting

### Проблема: Ollama не подключается

```bash
# Проверяем, запущена ли Ollama
curl http://localhost:11434/api/tags

# Перезагружаем Ollama
sudo systemctl restart ollama
```

### Проблема: Недостаточно памяти

```bash
# Проверяем использование памяти
free -h

# Увеличиваем swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Проблема: Медленная работа

```bash
# Проверяем логи
tail -f /var/log/cursor-killer-backend.out.log

# Увеличиваем количество workers
# В supervisor config измените --workers 4 на --workers 8
```

## Лицензия

MIT
