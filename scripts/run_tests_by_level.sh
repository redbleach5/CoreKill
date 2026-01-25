#!/bin/bash
# Скрипт для запуска тестов по уровням

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

LEVEL="${1:-all}"

case "$LEVEL" in
    unit|fast)
        echo -e "${CYAN}🚀 Запуск unit тестов (быстрые)...${NC}"
        pytest -m "unit and fast" -v --tb=short
        ;;
    integration)
        echo -e "${CYAN}🔗 Запуск integration тестов...${NC}"
        pytest -m integration -v --tb=short
        ;;
    e2e)
        echo -e "${CYAN}🌐 Запуск E2E тестов...${NC}"
        pytest -m e2e -v --tb=short
        ;;
    smoke)
        echo -e "${CYAN}💨 Запуск smoke тестов...${NC}"
        pytest -m smoke -v --tb=short
        ;;
    critical)
        echo -e "${CYAN}⚠️  Запуск critical тестов...${NC}"
        pytest -m critical -v --tb=short
        ;;
    real|reality)
        echo -e "${CYAN}🔍 Запуск тестов реального поведения (smoke + critical)...${NC}"
        pytest -m "smoke or critical" -v --tb=short
        ;;
    backend)
        echo -e "${CYAN}📦 Запуск backend тестов...${NC}"
        pytest -m backend -v --tb=short
        ;;
    infrastructure)
        echo -e "${CYAN}🏗️  Запуск infrastructure тестов...${NC}"
        pytest -m infrastructure -v --tb=short
        ;;
    agents)
        echo -e "${CYAN}🤖 Запуск agents тестов...${NC}"
        pytest -m agents -v --tb=short
        ;;
    utils)
        echo -e "${CYAN}🛠️  Запуск utils тестов...${NC}"
        pytest -m utils -v --tb=short
        ;;
    all)
        echo -e "${CYAN}📊 Запуск всех тестов...${NC}"
        pytest -v --tb=short
        ;;
    *)
        echo -e "${RED}❌ Неизвестный уровень: $LEVEL${NC}"
        echo ""
        echo "Использование: $0 [LEVEL]"
        echo ""
        echo "Уровни:"
        echo "  unit, fast      - Unit тесты (быстрые)"
        echo "  integration     - Integration тесты"
        echo "  e2e             - E2E тесты"
        echo "  smoke           - Smoke тесты"
        echo "  critical        - Critical тесты"
        echo "  real, reality   - Smoke + Critical (реальное поведение)"
        echo ""
        echo "Категории:"
        echo "  backend         - Backend тесты"
        echo "  infrastructure  - Infrastructure тесты"
        echo "  agents          - Agents тесты"
        echo "  utils           - Utils тесты"
        echo ""
        echo "  all             - Все тесты (по умолчанию)"
        exit 1
        ;;
esac
