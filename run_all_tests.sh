#!/bin/bash
# Скрипт для запуска всех тестов проекта и сбора результатов
# Обновлено: 23 января 2026 - добавлена поддержка coverage и группировки тестов

# Не используем set -e, чтобы запустить все тесты даже при ошибках в отдельных секциях

# Парсинг аргументов
COVERAGE=false
CATEGORY=""
NEW_TESTS_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage|-c)
            COVERAGE=true
            shift
            ;;
        --category)
            CATEGORY="$2"
            shift 2
            ;;
        --new-only)
            NEW_TESTS_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Использование: $0 [опции]"
            echo ""
            echo "Опции:"
            echo "  --coverage, -c          Запустить тесты с измерением покрытия"
            echo "  --category CATEGORY      Запустить тесты только для категории (utils|backend|infrastructure|agents)"
            echo "  --new-only              Запустить только новые тесты (созданные для покрытия)"
            echo "  --help, -h              Показать эту справку"
            echo ""
            echo "Примеры:"
            echo "  $0                      # Запустить все тесты"
            echo "  $0 --coverage           # Запустить все тесты с покрытием"
            echo "  $0 --category utils     # Запустить только utils тесты"
            echo "  $0 --new-only           # Запустить только новые тесты"
            exit 0
            ;;
        *)
            echo "Неизвестная опция: $1"
            echo "Используйте --help для справки"
            exit 1
            ;;
    esac
done

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Директория для результатов
RESULTS_DIR="test_results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULTS_PATH="${RESULTS_DIR}/${TIMESTAMP}"

# Создаем директорию для результатов
mkdir -p "${RESULTS_PATH}"

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🧪 Запуск всех тестов проекта${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Показываем выбранные опции
if [ "$COVERAGE" = true ]; then
    echo -e "${CYAN}📊 Режим: С измерением покрытия${NC}"
fi
if [ -n "$CATEGORY" ]; then
    echo -e "${CYAN}📁 Категория: ${CATEGORY}${NC}"
fi
if [ "$NEW_TESTS_ONLY" = true ]; then
    echo -e "${CYAN}🆕 Только новые тесты${NC}"
fi

echo ""
echo -e "📁 Результаты будут сохранены в: ${RESULTS_PATH}"
echo ""

# Функция для проверки наличия команды
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}❌ Команда '$1' не найдена${NC}"
        return 1
    fi
    return 0
}

# Функция для проверки виртуального окружения
check_venv() {
    if [ -z "$VIRTUAL_ENV" ] && [ -d ".venv" ]; then
        echo -e "${YELLOW}⚠️  Виртуальное окружение не активировано${NC}"
        echo -e "${YELLOW}   Активирую .venv...${NC}"
        source .venv/bin/activate
    fi
}

# Инициализация счетчиков
BACKEND_PASSED=0
BACKEND_FAILED=0
FRONTEND_PASSED=0
FRONTEND_FAILED=0
AUTONOMOUS_PASSED=0
AUTONOMOUS_FAILED=0

# ============================================================================
# 1. BACKEND ТЕСТЫ (pytest)
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 Запуск Backend тестов (pytest)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

check_venv

if check_command "pytest"; then
    BACKEND_LOG="${RESULTS_PATH}/backend_tests.log"
    COVERAGE_LOG="${RESULTS_PATH}/coverage.log"
    
    # Формируем команду pytest
    PYTEST_CMD="pytest --verbose --tb=short"
    
    # Определяем какие тесты запускать
    if [ "$NEW_TESTS_ONLY" = true ]; then
        # Только новые тесты для покрытия
        TEST_PATHS="tests/test_utils_structured_helpers.py tests/test_utils_config.py tests/test_backend_dependencies.py tests/test_backend_shutdown_manager.py tests/test_infrastructure_event_store.py tests/test_infrastructure_task_checkpointer.py tests/test_infrastructure_performance_metrics.py tests/test_utils_token_counter.py tests/test_utils_artifact_saver.py tests/test_utils_file_context.py tests/test_utils_model_checker.py tests/test_infrastructure_workflow_decorators.py tests/test_infrastructure_agent_resource_manager.py"
        echo -e "${CYAN}🆕 Запуск только новых тестов для покрытия...${NC}"
    elif [ -n "$CATEGORY" ]; then
        # Тесты по категории
        case "$CATEGORY" in
            utils)
                TEST_PATHS="tests/test_utils_*.py"
                echo -e "${CYAN}📁 Запуск utils тестов...${NC}"
                ;;
            backend)
                TEST_PATHS="tests/test_backend_*.py"
                echo -e "${CYAN}📁 Запуск backend тестов...${NC}"
                ;;
            infrastructure)
                TEST_PATHS="tests/test_infrastructure_*.py"
                echo -e "${CYAN}📁 Запуск infrastructure тестов...${NC}"
                ;;
            agents)
                TEST_PATHS="tests/test_agents_*.py tests/test_coder.py tests/test_planner.py tests/test_reflection.py tests/test_debugger.py tests/test_intent.py tests/test_researcher.py tests/test_streaming_*.py"
                echo -e "${CYAN}📁 Запуск agents тестов...${NC}"
                ;;
            *)
                echo -e "${RED}❌ Неизвестная категория: $CATEGORY${NC}"
                echo "Доступные категории: utils, backend, infrastructure, agents"
                exit 1
                ;;
        esac
    else
        # Все тесты
        TEST_PATHS="tests/"
        echo "Запуск всех тестов..."
    fi
    
    # Добавляем coverage если нужно
    if [ "$COVERAGE" = true ]; then
        PYTEST_CMD="$PYTEST_CMD --cov=. --cov-report=term-missing --cov-report=html:${RESULTS_PATH}/htmlcov --cov-report=json:${RESULTS_PATH}/coverage.json"
        echo -e "${CYAN}📊 Включено измерение покрытия${NC}"
    fi
    
    echo ""
    echo "Запуск pytest..."
    echo -e "${CYAN}💡 Прогресс будет отображаться в реальном времени...${NC}"
    echo ""
    
    # Запускаем тесты с выводом в терминал И в лог (tee)
    if $PYTEST_CMD $TEST_PATHS 2>&1 | tee "${BACKEND_LOG}"; then
        BACKEND_PASSED=1
        echo ""
        echo -e "${GREEN}✅ Backend тесты пройдены${NC}"
    else
        BACKEND_FAILED=1
        echo ""
        echo -e "${RED}❌ Backend тесты провалены${NC}"
    fi
    
    # Извлекаем статистику из лога
    if [ -f "${BACKEND_LOG}" ]; then
        PASSED_COUNT=$(grep -oP '\d+ passed' "${BACKEND_LOG}" | grep -oP '\d+' | head -1 || echo "0")
        FAILED_COUNT=$(grep -oP '\d+ failed' "${BACKEND_LOG}" | grep -oP '\d+' | head -1 || echo "0")
        ERROR_COUNT=$(grep -oP '\d+ error' "${BACKEND_LOG}" | grep -oP '\d+' | head -1 || echo "0")
        SKIPPED_COUNT=$(grep -oP '\d+ skipped' "${BACKEND_LOG}" | grep -oP '\d+' | head -1 || echo "0")
        
        echo "  📊 Пройдено: ${PASSED_COUNT:-0}, Провалено: ${FAILED_COUNT:-0}, Ошибок: ${ERROR_COUNT:-0}, Пропущено: ${SKIPPED_COUNT:-0}"
        
        # Показываем покрытие если было измерено
        if [ "$COVERAGE" = true ] && [ -f "${RESULTS_PATH}/coverage.json" ]; then
            echo ""
            echo -e "${CYAN}📊 Покрытие кода:${NC}"
            if command -v python3 &> /dev/null; then
                python3 -c "
import json
try:
    with open('${RESULTS_PATH}/coverage.json', 'r') as f:
        data = json.load(f)
        total = data.get('totals', {})
        covered = total.get('covered_lines', 0)
        total_lines = total.get('num_statements', 0)
        if total_lines > 0:
            percent = (covered / total_lines) * 100
            print(f'  Покрыто строк: {covered}/{total_lines} ({percent:.1f}%)')
        else:
            print('  Данные покрытия недоступны')
except Exception as e:
    print(f'  Ошибка чтения покрытия: {e}')
" 2>/dev/null || echo "  Используйте HTML отчёт для детальной информации"
            fi
            echo -e "  📄 HTML отчёт: ${RESULTS_PATH}/htmlcov/index.html"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  pytest не найден, пропускаем backend тесты${NC}"
fi

echo ""

# ============================================================================
# 2. AUTONOMOUS IMPROVER ТЕСТЫ
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🤖 Запуск Autonomous Improver тестов${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

AUTONOMOUS_LOG="${RESULTS_PATH}/autonomous_improver_tests.log"

if [ -d "infrastructure/autonomous_improver/tests" ]; then
    echo "Запуск тестов Autonomous Improver..."
    
    # Запускаем тесты с выводом в терминал И в лог (tee)
    pytest \
        --verbose \
        --tb=short \
        infrastructure/autonomous_improver/tests/ \
        2>&1 | tee "${AUTONOMOUS_LOG}" && {
        AUTONOMOUS_PASSED=1
        echo -e "${GREEN}✅ Autonomous Improver тесты пройдены${NC}"
    } || {
        AUTONOMOUS_FAILED=1
        echo -e "${RED}❌ Autonomous Improver тесты провалены${NC}"
    }
    
    # Извлекаем статистику
    if [ -f "${AUTONOMOUS_LOG}" ]; then
        PASSED_COUNT=$(grep -oP '\d+ passed' "${AUTONOMOUS_LOG}" | grep -oP '\d+' | head -1 || echo "0")
        FAILED_COUNT=$(grep -oP '\d+ failed' "${AUTONOMOUS_LOG}" | grep -oP '\d+' | head -1 || echo "0")
        ERROR_COUNT=$(grep -oP '\d+ error' "${AUTONOMOUS_LOG}" | grep -oP '\d+' | head -1 || echo "0")
        
        echo "  📊 Пройдено: ${PASSED_COUNT:-0}, Провалено: ${FAILED_COUNT:-0}, Ошибок: ${ERROR_COUNT:-0}"
    fi
else
    echo -e "${YELLOW}⚠️  Директория infrastructure/autonomous_improver/tests не найдена${NC}"
fi

echo ""

# ============================================================================
# 3. FRONTEND ТЕСТЫ (vitest)
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🎨 Запуск Frontend тестов (vitest)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

FRONTEND_LOG="${RESULTS_PATH}/frontend_tests.log"

if [ -d "frontend" ]; then
    cd frontend
    
    if check_command "npm"; then
        # Проверяем, установлены ли зависимости
        if [ ! -d "node_modules" ]; then
            echo -e "${YELLOW}⚠️  node_modules не найдены, устанавливаю зависимости...${NC}"
            npm install
        fi
        
        echo "Запуск vitest..."
        
        # Запускаем тесты с выводом в терминал И в лог (tee)
        npx vitest run --reporter=verbose 2>&1 | tee "../${FRONTEND_LOG}" && {
            FRONTEND_PASSED=1
            echo -e "${GREEN}✅ Frontend тесты пройдены${NC}"
        } || {
            FRONTEND_FAILED=1
            echo -e "${RED}❌ Frontend тесты провалены${NC}"
        }
        
        # Извлекаем статистику из лога
        if [ -f "../${FRONTEND_LOG}" ]; then
            PASSED_COUNT=$(grep -oP '\d+ passed' "../${FRONTEND_LOG}" | grep -oP '\d+' | head -1 || echo "0")
            FAILED_COUNT=$(grep -oP '\d+ failed' "../${FRONTEND_LOG}" | grep -oP '\d+' | head -1 || echo "0")
            TOTAL_COUNT=$(grep -oP '\d+ total' "../${FRONTEND_LOG}" | grep -oP '\d+' | head -1 || echo "0")
            
            echo "  📊 Всего: ${TOTAL_COUNT:-0}, Пройдено: ${PASSED_COUNT:-0}, Провалено: ${FAILED_COUNT:-0}"
        fi
        
        cd ..
    else
        echo -e "${YELLOW}⚠️  npm не найден, пропускаем frontend тесты${NC}"
        cd ..
    fi
else
    echo -e "${YELLOW}⚠️  Директория frontend не найдена${NC}"
fi

echo ""

# ============================================================================
# 4. СОЗДАНИЕ ИТОГОВОГО ОТЧЕТА
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 Создание итогового отчета${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

SUMMARY_FILE="${RESULTS_PATH}/summary.txt"

# Создаем текстовый отчет
{
    echo "═══════════════════════════════════════════════════════════"
    echo "📊 ИТОГОВЫЙ ОТЧЕТ О ТЕСТИРОВАНИИ"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Дата и время: $(date)"
    echo "Директория результатов: ${RESULTS_PATH}"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "РЕЗУЛЬТАТЫ:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Backend
    if [ $BACKEND_PASSED -eq 1 ]; then
        echo "✅ Backend тесты: ПРОЙДЕНЫ"
    elif [ $BACKEND_FAILED -eq 1 ]; then
        echo "❌ Backend тесты: ПРОВАЛЕНЫ"
    else
        echo "⚠️  Backend тесты: НЕ ЗАПУЩЕНЫ"
    fi
    
    # Autonomous Improver
    if [ $AUTONOMOUS_PASSED -eq 1 ]; then
        echo "✅ Autonomous Improver тесты: ПРОЙДЕНЫ"
    elif [ $AUTONOMOUS_FAILED -eq 1 ]; then
        echo "❌ Autonomous Improver тесты: ПРОВАЛЕНЫ"
    else
        echo "⚠️  Autonomous Improver тесты: НЕ ЗАПУЩЕНЫ"
    fi
    
    # Frontend
    if [ $FRONTEND_PASSED -eq 1 ]; then
        echo "✅ Frontend тесты: ПРОЙДЕНЫ"
    elif [ $FRONTEND_FAILED -eq 1 ]; then
        echo "❌ Frontend тесты: ПРОВАЛЕНЫ"
    else
        echo "⚠️  Frontend тесты: НЕ ЗАПУЩЕНЫ"
    fi
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "ФАЙЛЫ РЕЗУЛЬТАТОВ:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📄 Логи:"
    [ -f "${RESULTS_PATH}/backend_tests.log" ] && echo "  - backend_tests.log"
    [ -f "${RESULTS_PATH}/autonomous_improver_tests.log" ] && echo "  - autonomous_improver_tests.log"
    [ -f "${RESULTS_PATH}/frontend_tests.log" ] && echo "  - frontend_tests.log"
    echo ""
    if [ "$COVERAGE" = true ]; then
        echo "📊 Отчёты покрытия:"
        [ -f "${RESULTS_PATH}/coverage.json" ] && echo "  - coverage.json"
        [ -d "${RESULTS_PATH}/htmlcov" ] && echo "  - htmlcov/index.html (откройте в браузере)"
        echo ""
    fi
} > "${SUMMARY_FILE}"

echo -e "${GREEN}✅ Отчет создан${NC}"
echo ""

# ============================================================================
# 5. ИТОГОВАЯ СВОДКА
# ============================================================================
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📋 ИТОГОВАЯ СВОДКА${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

TOTAL_PASSED=$((BACKEND_PASSED + AUTONOMOUS_PASSED + FRONTEND_PASSED))
TOTAL_FAILED=$((BACKEND_FAILED + AUTONOMOUS_FAILED + FRONTEND_FAILED))

if [ $TOTAL_FAILED -eq 0 ] && [ $TOTAL_PASSED -gt 0 ]; then
    echo -e "${GREEN}✅ Все тесты пройдены успешно!${NC}"
    EXIT_CODE=0
elif [ $TOTAL_FAILED -gt 0 ]; then
    echo -e "${RED}❌ Некоторые тесты провалены${NC}"
    EXIT_CODE=1
else
    echo -e "${YELLOW}⚠️  Тесты не были запущены${NC}"
    EXIT_CODE=2
fi

echo ""
echo "📁 Все результаты сохранены в: ${RESULTS_PATH}"
echo "📄 Итоговый отчет: ${SUMMARY_FILE}"

if [ "$COVERAGE" = true ] && [ -d "${RESULTS_PATH}/htmlcov" ]; then
    echo "📊 HTML отчёт покрытия: ${RESULTS_PATH}/htmlcov/index.html"
fi

echo ""

# Показываем краткую сводку
cat "${SUMMARY_FILE}"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Полезные команды для дальнейшей работы
if [ "$COVERAGE" = true ]; then
    echo ""
    echo -e "${CYAN}💡 Полезные команды:${NC}"
    echo "  • Открыть HTML отчёт: open ${RESULTS_PATH}/htmlcov/index.html"
    echo "  • Проверить покрытие по модулям: pytest --cov=utils --cov-report=term-missing"
    echo "  • Проверить покрытие backend: pytest --cov=backend --cov-report=term-missing"
    echo "  • Проверить покрытие infrastructure: pytest --cov=infrastructure --cov-report=term-missing"
fi

echo ""

exit $EXIT_CODE
