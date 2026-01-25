#!/bin/bash
# Скрипт для запуска теста Autonomous Improver

set -e

echo "🧪 Тест Autonomous Improver"
echo "=========================="
echo ""

# Проверяем конфигурацию
if ! grep -q "enabled = true" config.toml 2>/dev/null || ! grep -A5 "\[autonomous_improver\]" config.toml | grep -q "enabled = true"; then
    echo "⚠️  ВНИМАНИЕ: autonomous_improver.enabled = false в config.toml"
    echo "   Установите enabled = true для запуска теста"
    echo ""
    read -p "Продолжить? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Проверяем наличие модели
echo "🔍 Проверка моделей Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama не установлен"
    exit 1
fi

MODELS=$(ollama list 2>/dev/null | grep -v "NAME" | awk '{print $1}' || echo "")
if [ -z "$MODELS" ]; then
    echo "⚠️  Нет установленных моделей"
    echo "   Установите легкую модель: ollama pull phi3:mini"
    exit 1
fi

echo "✅ Модели найдены:"
echo "$MODELS" | head -5
echo ""

# Запускаем тест
DURATION=${1:-4.0}
echo "🚀 Запуск теста на $DURATION часов..."
echo ""

python3 scripts/test_autonomous_improver.py --duration "$DURATION"

echo ""
echo "✅ Тест завершён"
echo ""
echo "📊 Для анализа результатов:"
echo "   python3 scripts/analyze_improver_results.py test_improver_results.json"
