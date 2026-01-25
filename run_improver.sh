#!/bin/bash
# Простой скрипт для запуска Autonomous Improver
# 
# Использование:
#   ./run_improver.sh [длительность_в_часах]
#   ./run_improver.sh 4.0

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

cd "$PROJECT_DIR"

# Активируем виртуальное окружение если оно существует
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ Используется виртуальное окружение: .venv"
elif [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Используется виртуальное окружение: venv"
else
    echo "⚠️  Виртуальное окружение не найдено (.venv или venv)"
    echo "   Убедитесь, что зависимости установлены"
fi

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

python infrastructure/autonomous_improver/scripts/test.py --duration "$DURATION"

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
echo "   python infrastructure/autonomous_improver/scripts/analyze_results.py test_improver_results.json"
