#!/bin/bash
# Скрипт для запуска тестов конкретного модуля

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

MODULE="${1}"

if [ -z "$MODULE" ]; then
    echo -e "${RED}❌ Укажите модуль для тестирования${NC}"
    echo ""
    echo "Использование: $0 <module_name>"
    echo ""
    echo "Примеры:"
    echo "  $0 event_store"
    echo "  $0 config"
    echo "  $0 coder"
    echo "  $0 dependencies"
    exit 1
fi

# Активируем виртуальное окружение если есть
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo -e "${CYAN}🔍 Поиск тестов для модуля: ${MODULE}${NC}"
echo ""

# Ищем тесты для модуля
TEST_FILES=$(find tests -name "test_*${MODULE}*.py" -o -name "test_*${MODULE}.py" 2>/dev/null)

if [ -z "$TEST_FILES" ]; then
    echo -e "${YELLOW}⚠️  Тесты для модуля '${MODULE}' не найдены${NC}"
    echo ""
    echo "Доступные модули:"
    find tests -name "test_*.py" | sed 's|tests/test_||' | sed 's|\.py||' | sort | uniq
    exit 1
fi

echo -e "${GREEN}✅ Найдены тесты:${NC}"
echo "$TEST_FILES" | sed 's/^/  /'
echo ""

# Запускаем тесты
echo -e "${CYAN}🚀 Запуск тестов...${NC}"
pytest $TEST_FILES -v --tb=short
