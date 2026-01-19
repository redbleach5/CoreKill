# Правила для работы в РФ

## Сервисы и инструменты

При выборе внешних сервисов учитывать доступность в России:

### ✅ Работают в РФ
- **Tailscale** — VPN для связи между устройствами (рекомендуется)
- **ZeroTier** — альтернатива Tailscale
- **Cloudflare** — CDN, Tunnel, DNS
- **GitHub** — репозитории, Actions
- **Docker Hub** — контейнеры
- **PyPI** — Python пакеты
- **npm** — Node.js пакеты

### ⚠️ Могут быть проблемы
- **ngrok** — работает нестабильно
- **Heroku** — ограничения для РФ аккаунтов
- **Vercel** — могут быть проблемы с оплатой

### ❌ Не работают / заблокированы
- Некоторые AI API без VPN (OpenAI, Anthropic напрямую)

## Удалённый Ollama

Для связи MacBook ↔ машина с GPU в разных сетях:

1. Установить Tailscale на обе машины
2. На машине с GPU:
   ```bash
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   ```
3. В `config.toml`:
   ```toml
   [ollama]
   host = "http://100.x.x.x:11434"  # Tailscale IP
   ```

## Альтернативы заблокированным сервисам

| Заблокировано | Альтернатива |
|---------------|--------------|
| OpenAI API | Ollama (локально), YandexGPT |
| Anthropic API | Ollama (локально) |
| AWS (оплата) | Selectel, Yandex Cloud |
