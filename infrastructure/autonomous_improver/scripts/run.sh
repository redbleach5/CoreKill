#!/bin/bash
# Простой скрипт для запуска Autonomous Improver
# 
# Использование:
#   ./infrastructure/autonomous_improver/scripts/run.sh [длительность_в_часах]
#   ./infrastructure/autonomous_improver/scripts/run.sh 4.0
#
# Что делает:
#   1. Проверяет конфигурацию (autonomous_improver.enabled = true)
#   2. Создаёт директорию для логов
#   3. Запускает тест через test.py
#   4. Выводит информацию о результатах
#
# Результаты:
#   - Логи модуля: logs/autonomous_improver.log
#   - Логи теста: logs/autonomous_improver_test.log
#   - Результаты: test_improver_results.json
#
# Зависимости:
#   - Python 3
#   - infrastructure/autonomous_improver/scripts/test.py
#   - config.toml с autonomous_improver.enabled = true

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Скрипт находится в infrastructure/autonomous_improver/scripts/
# Нужно подняться на 3 уровня вверх до корня проекта
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

cd "$PROJECT_DIR"

# Создаём директорию для логов
mkdir -p logs

# Параметры по умолчанию
DURATION=${1:-4.0}

echo "🤖 Autonomous Improver"
echo "======================"
echo ""
echo "⏱️  Длительность: $DURATION часов"
echo "📁 Проект: $PROJECT_DIR"
echo "📝 Логи модуля: logs/autonomous_improver.log"
echo "📝 Логи теста: logs/autonomous_improver_test.log"
echo ""

# Проверяем конфигурацию
if ! grep -A10 "\[autonomous_improver\]" config.toml | grep -q "enabled = true"; then
    echo "⚠️  autonomous_improver.enabled = false в config.toml"
    echo "   Включите для запуска: enabled = true"
    exit 1
fi

# Запускаем тест
echo "🚀 Запуск..."
echo "   (Нажмите Ctrl+C для остановки)"
echo ""

python3 infrastructure/autonomous_improver/scripts/test.py --duration "$DURATION"

echo ""
echo "✅ Готово!"
echo ""
echo "📊 Результаты:"
echo "   - Логи модуля: logs/autonomous_improver.log"
echo "   - Логи теста: logs/autonomous_improver_test.log"
echo "   - Результаты: test_improver_results.json"
echo ""
echo "💡 Команды:"
echo "   # Просмотр логов модуля:"
echo "   tail -f logs/autonomous_improver.log"
echo ""
echo "   # Анализ результатов:"
echo "   python3 scripts/analyze_improver_results.py test_improver_results.json"
