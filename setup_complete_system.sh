#!/bin/bash

# Полная установка и настройка Voice AI системы с WebPhone
# Prime Cargo Logistics

set -e  # Выход при любой ошибке

echo "🚀 ПОЛНАЯ УСТАНОВКА VOICE AI СИСТЕМЫ С WEBPHONE"
echo "=================================================="
echo "Prime Cargo Logistics - Voice AI Call System"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для красивого вывода
print_step() {
    echo -e "${BLUE}➤${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

# Проверка ОС
check_os() {
    print_step "Проверка операционной системы..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_success "Linux обнаружен"
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        print_success "macOS обнаружен"
        OS="macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        print_success "Windows (WSL/Cygwin) обнаружен"
        OS="windows"
    else
        print_error "Неподдерживаемая ОС: $OSTYPE"
        exit 1
    fi
}

# Проверка и установка зависимостей
install_dependencies() {
    print_step "Проверка и установка зависимостей..."
    
    # Проверка Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 не найден. Пожалуйста, установите Python 3.8+"
        exit 1
    fi
    print_success "Python 3 найден: $(python3 --version)"
    
    # Проверка pip
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 не найден. Пожалуйста, установите pip"
        exit 1
    fi
    print_success "pip3 найден"
    
    # Проверка Node.js
    if ! command -v node &> /dev/null; then
        print_warning "Node.js не найден. Попытка установки..."
        
        if [[ "$OS" == "linux" ]]; then
            curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
            sudo apt-get install -y nodejs
        elif [[ "$OS" == "macos" ]]; then
            if command -v brew &> /dev/null; then
                brew install node
            else
                print_error "Homebrew не найден. Установите Node.js вручную: https://nodejs.org/"
                exit 1
            fi
        else
            print_error "Автоматическая установка Node.js не поддерживается. Установите вручную: https://nodejs.org/"
            exit 1
        fi
    fi
    print_success "Node.js найден: $(node --version)"
    
    # Проверка npm
    if ! command -v npm &> /dev/null; then
        print_error "npm не найден. Переустановите Node.js"
        exit 1
    fi
    print_success "npm найден: $(npm --version)"
    
    # Проверка дополнительных утилит
    for cmd in curl wget git; do
        if ! command -v $cmd &> /dev/null; then
            print_warning "$cmd не найден, но может потребоваться"
        else
            print_success "$cmd найден"
        fi
    done
}

# Создание структуры директорий
create_directories() {
    print_step "Создание структуры директорий..."
    
    directories=(
        "logs"
        "recordings"
        "temp"
        "backups"
    )
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            print_success "Создана директория: $dir"
        else
            print_success "Директория уже существует: $dir"
        fi
    done
}

# Установка Python зависимостей
install_python_deps() {
    print_step "Установка Python зависимостей..."
    
    # Обновляем pip
    python3 -m pip install --upgrade pip
    
    # Устанавливаем основные зависимости
    if [ -f "requirements.txt" ]; then
        print_step "Установка из requirements.txt..."
        pip3 install -r requirements.txt
        print_success "Python зависимости установлены"
    else
        print_error "requirements.txt не найден!"
        exit 1
    fi
    
    # Проверяем критически важные зависимости
    critical_deps=("torch" "whisper" "flask" "websockets")
    for dep in "${critical_deps[@]}"; do
        if python3 -c "import $dep" 2>/dev/null; then
            print_success "$dep установлен"
        else
            print_warning "$dep может быть не установлен корректно"
        fi
    done
}

# Установка Node.js зависимостей
install_node_deps() {
    print_step "Установка Node.js зависимостей..."
    
    if [ -d "webphone-bridge" ]; then
        cd webphone-bridge
        
        if [ -f "package.json" ]; then
            npm install
            print_success "Node.js зависимости установлены"
        else
            print_error "package.json не найден в webphone-bridge!"
            exit 1
        fi
        
        cd ..
    else
        print_error "Директория webphone-bridge не найдена!"
        exit 1
    fi
}

# Проверка конфигурации
check_configuration() {
    print_step "Проверка конфигурации..."
    
    # Проверяем основные файлы
    required_files=(
        "config.py"
        "voice_ai_engine.py"
        "webhook_server.py"
        "audio_stream_handler.py"
        "webphone-bridge/webphone_bridge.js"
        "webphone-bridge/package.json"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            print_success "Найден: $file"
        else
            print_error "Отсутствует критический файл: $file"
            exit 1
        fi
    done
    
    # Проверяем настройки RingCentral
    if grep -q "bXCZ510zNmybxAUXGIZruT" config.py; then
        print_success "RingCentral Client ID настроен"
    else
        print_warning "RingCentral Client ID может быть не настроен"
    fi
}

# Тест системы
test_system() {
    print_step "Тестирование системы..."
    
    # Делаем тестовый скрипт исполняемым
    chmod +x test_webphone_integration.py
    
    print_step "Запуск базовых тестов..."
    
    # Тест импортов Python
    if python3 -c "
import flask
import websockets
import torch
import whisper
from config import Config
print('✅ Все критические Python модули импортированы успешно')
"; then
        print_success "Python модули в порядке"
    else
        print_error "Проблемы с Python модулями"
        exit 1
    fi
    
    # Тест Node.js модулей
    cd webphone-bridge
    if node -e "
const SDK = require('@ringcentral/sdk');
const WebPhone = require('ringcentral-web-phone');
const axios = require('axios');
console.log('✅ Все критические Node.js модули найдены');
"; then
        print_success "Node.js модули в порядке"
    else
        print_error "Проблемы с Node.js модулями"
        exit 1
    fi
    cd ..
}

# Создание .env файла-примера
create_env_example() {
    print_step "Создание .env файла-примера..."
    
    if [ ! -f ".env.example" ]; then
        cat > .env.example << 'EOF'
# RingCentral настройки
RINGCENTRAL_CLIENT_ID=your_client_id_here
RINGCENTRAL_CLIENT_SECRET=your_client_secret_here
RINGCENTRAL_JWT_TOKEN=your_jwt_token_here
RINGCENTRAL_SERVER=https://platform.ringcentral.com
RINGCENTRAL_MAIN_NUMBER=your_main_number_here

# Python AI Server
PYTHON_AI_SERVER=http://localhost:5000
PYTHON_AI_ENDPOINT=/api/handle-webphone-call

# WebSocket и аудио
WEBSOCKET_PORT=8080
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1

# Логирование
LOG_LEVEL=info

# Производительность
MAX_CONCURRENT_CALLS=5
USE_GPU=true

# Webhook (если используется)
WEBHOOK_URL=https://your-ngrok-url.ngrok.io/webhook
WEBHOOK_SECRET=your_webhook_secret
EOF
        print_success "Создан .env.example файл"
        print_warning "ВАЖНО: Скопируйте .env.example в .env и настройте свои данные!"
    else
        print_success ".env.example уже существует"
    fi
}

# Создание скриптов быстрого запуска
create_quick_scripts() {
    print_step "Создание скриптов быстрого запуска..."
    
    # Делаем существующие скрипты исполняемыми
    chmod +x start_system.sh
    chmod +x stop_system.sh
    
    # Создаем быстрый скрипт проверки статуса
    cat > check_status.sh << 'EOF'
#!/bin/bash
echo "📊 СТАТУС VOICE AI СИСТЕМЫ"
echo "=========================="

# Проверка процессов
if pgrep -f "python.*webhook_server.py" > /dev/null; then
    echo "✅ Python AI Server: ЗАПУЩЕН"
else
    echo "❌ Python AI Server: ОСТАНОВЛЕН"
fi

if pgrep -f "node.*webphone_bridge.js" > /dev/null; then
    echo "✅ WebPhone Bridge: ЗАПУЩЕН"
else
    echo "❌ WebPhone Bridge: ОСТАНОВЛЕН"
fi

# Проверка портов
if netstat -tuln 2>/dev/null | grep -q ":5000 "; then
    echo "✅ Порт 5000 (Python): ОТКРЫТ"
else
    echo "❌ Порт 5000 (Python): ЗАКРЫТ"
fi

if netstat -tuln 2>/dev/null | grep -q ":8080 "; then
    echo "✅ Порт 8080 (WebSocket): ОТКРЫТ"
else
    echo "❌ Порт 8080 (WebSocket): ЗАКРЫТ"
fi

echo ""
echo "🔗 Полезные ссылки:"
echo "   Health Check: curl http://localhost:5000/health"
echo "   WebPhone Status: curl http://localhost:5000/api/webphone/status"
echo ""
echo "📜 Просмотр логов:"
echo "   Python: tail -f logs/python-server.log"
echo "   WebPhone: tail -f logs/webphone-bridge.log"
EOF
    chmod +x check_status.sh
    print_success "Создан check_status.sh"
    
    # Создаем скрипт для полного теста
    cat > run_full_test.sh << 'EOF'
#!/bin/bash
echo "🧪 ЗАПУСК ПОЛНОГО ТЕСТА СИСТЕМЫ"
echo "==============================="
echo ""

# Проверяем что система запущена
./check_status.sh

echo ""
echo "⏳ Ожидание 5 секунд перед тестированием..."
sleep 5

# Запускаем тест интеграции
python3 test_webphone_integration.py
EOF
    chmod +x run_full_test.sh
    print_success "Создан run_full_test.sh"
}

# Финальный отчет
final_report() {
    echo ""
    echo "🎉 УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!"
    echo "================================"
    echo ""
    echo "📋 Что установлено:"
    echo "   ✅ Python зависимости (AI, WebSocket, Flask)"
    echo "   ✅ Node.js зависимости (RingCentral WebPhone)"
    echo "   ✅ Структура директорий"
    echo "   ✅ Скрипты управления"
    echo "   ✅ Тестовые утилиты"
    echo ""
    echo "🚀 Быстрый старт:"
    echo "   1. Настройте .env файл: cp .env.example .env"
    echo "   2. Запустите систему: ./start_system.sh"
    echo "   3. Проверьте статус: ./check_status.sh"
    echo "   4. Запустите тесты: ./run_full_test.sh"
    echo ""
    echo "📞 Система готова принимать звонки через RingCentral WebPhone!"
    echo ""
    echo "🔧 Полезные команды:"
    echo "   ./start_system.sh     - Запуск всей системы"
    echo "   ./stop_system.sh      - Остановка системы"
    echo "   ./check_status.sh     - Проверка статуса"
    echo "   ./run_full_test.sh    - Полное тестирование"
    echo ""
    echo "📚 Документация: README_WEBPHONE.md"
    echo "================================"
}

# Главная функция
main() {
    check_os
    install_dependencies
    create_directories
    install_python_deps
    install_node_deps
    check_configuration
    test_system
    create_env_example
    create_quick_scripts
    final_report
}

# Обработка ошибок
trap 'print_error "Установка прервана из-за ошибки на строке $LINENO"' ERR

# Запуск установки
main "$@"