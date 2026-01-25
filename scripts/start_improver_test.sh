#!/bin/bash
# Удобный скрипт для запуска теста Autonomous Improver

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "🧪 Запуск теста Autonomous Improver"
echo "=================================="
echo ""

# Проверяем конфигурацию
if ! grep -A10 "\[autonomous_improver\]" config.toml | grep -q "enabled = true"; then
    echo "⚠️  ВНИМАНИЕ: autonomous_improver.enabled = false в config.toml"
    echo ""
    read -p "Включить для теста? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Временно включаем
        sed -i.bak 's/\[autonomous_improver\]/\[autonomous_improver\]\nenabled = true/' config.toml || \
        sed -i '' 's/enabled = false/enabled = true/' config.toml
        echo "✅ Временно включен autonomous_improver в config.toml"
        RESTORE_CONFIG=true
    else
        echo "❌ Тест отменён"
        exit 1
    fi
else
    RESTORE_CONFIG=false
fi

# Проверяем модели
echo "🔍 Проверка моделей Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama не установлен"
    exit 1
fi

MODELS=$(ollama list 2>/dev/null | grep -v "NAME" | awk '{print $1}' || echo "")
if [ -z "$MODELS" ]; then
    echo "⚠️  Нет установленных моделей"
    echo "   Установите: ollama pull phi3:mini"
    exit 1
fi

echo "✅ Доступные модели:"
echo "$MODELS" | head -5
echo ""

# Запускаем тест
DURATION=${1:-4.0}
echo "🚀 Запуск теста на $DURATION часов..."
echo "   (Нажмите Ctrl+C для остановки)"
echo ""

# Обработка сигналов для корректной остановки
trap 'echo ""; echo "🛑 Остановка теста..."; kill $TEST_PID 2>/dev/null; wait $TEST_PID 2>/dev/null; echo "✅ Тест остановлен"; if [ "$RESTORE_CONFIG" = true ]; then mv config.toml.bak config.toml 2>/dev/null || sed -i "" "s/enabled = true/enabled = false/" config.toml; echo "🔄 Конфигурация восстановлена"; fi; exit 0' INT TERM

python3 scripts/test_autonomous_improver.py --duration "$DURATION" &
TEST_PID=$!

wait $TEST_PID
EXIT_CODE=$?

# Восстанавливаем конфигурацию если нужно
if [ "$RESTORE_CONFIG" = true ]; then
    mv config.toml.bak config.toml 2>/dev/null || sed -i "" "s/enabled = true/enabled = false/" config.toml
    echo "🔄 Конфигурация восстановлена"
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Тест завершён успешно"
    echo ""
    echo "📊 Для анализа результатов:"
    echo "   python3 scripts/analyze_improver_results.py test_improver_results.json"
else
    echo ""
    echo "⚠️  Тест завершён с кодом: $EXIT_CODE"
fi
