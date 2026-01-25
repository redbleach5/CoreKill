# 🚀 Запуск Autonomous Improver

## Простой запуск

```bash
cd /Users/ruslan/Downloads/testmatuscrsr

# 1. Включите модуль в config.toml
# [autonomous_improver]
# enabled = true

# 2. Запустите тест (по умолчанию 4 часа)
./scripts/run_improver.sh

# Или с кастомной длительностью:
./scripts/run_improver.sh 2.0  # 2 часа
```

## Логи

Все логи пишутся в директорию `logs/`:

- **Модуль:** `logs/autonomous_improver.log` (JSONL формат)
- **Тест:** `logs/autonomous_improver_test.log` (JSONL формат)

### Просмотр логов

```bash
# Логи модуля в реальном времени
tail -f logs/autonomous_improver.log

# Логи теста
tail -f logs/autonomous_improver_test.log

# Последние 50 строк
tail -50 logs/autonomous_improver.log
```

### Формат логов

Логи в формате JSONL (одна строка JSON на событие):
```json
{"timestamp": "2026-01-22T23:29:05.302336+00:00", "level": "INFO", "source": "system", "message": "..."}
```

Для читаемого формата:
```bash
cat logs/autonomous_improver.log | python3 -m json.tool
```

## Результаты

После завершения теста:
- `test_improver_results.json` - все предложения и метрики
- `logs/autonomous_improver.log` - логи работы модуля
- `logs/autonomous_improver_test.log` - логи теста

## Анализ результатов

```bash
python3 scripts/analyze_improver_results.py test_improver_results.json
```

## Остановка

Нажмите **Ctrl+C** - тест корректно остановится и сохранит результаты.
