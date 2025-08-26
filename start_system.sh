#!/bin/bash

# Скрипт запуска Voice AI системы с WebPhone интеграцией
# Prime Cargo Logistics

echo "🚀 Запуск Voice AI системы с WebPhone интеграцией..."
echo "================================================"

# Проверка зависимостей
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 не найден. Пожалуйста, установите $1"
        exit 1
    fi
}

echo "📋 Проверка зависимостей..."
check_command node
check_command npm
check_command python3
check_command pip3

# Создание директорий
echo "📁 Создание необходимых директорий..."
mkdir -p logs
mkdir -p recordings
mkdir -p temp

# Установка Python зависимостей
echo "🐍 Установка Python зависимостей..."
pip3 install -r requirements.txt

# Установка Node.js зависимостей для WebPhone
echo "📦 Установка Node.js зависимостей..."
cd webphone-bridge
npm install
cd ..

# Функция для запуска процесса в фоне
run_background() {
    local name=$1
    local command=$2
    local dir=$3
    
    echo "▶️  Запуск $name..."
    
    if [ -n "$dir" ]; then
        cd "$dir"
    fi
    
    $command > ../logs/$name.log 2>&1 &
    local pid=$!
    echo $pid > ../logs/$name.pid
    
    if [ -n "$dir" ]; then
        cd ..
    fi
    
    echo "✅ $name запущен (PID: $pid)"
    
    # Небольшая проверка что процесс запустился
    sleep 1
    if kill -0 $pid 2>/dev/null; then
        echo "  ✓ Процесс активен"
    else
        echo "  ❌ Процесс завершился неожиданно"
        return 1
    fi
}

# Запуск Python сервера
run_background "python-server" "python3 webhook_server.py"

# Ждем запуска Python сервера
echo "⏳ Ожидание запуска Python сервера..."
sleep 5

# Проверка что Python сервер запустился
if curl -s http://localhost:5000/health > /dev/null; then
    echo "✅ Python сервер успешно запущен"
else
    echo "❌ Python сервер не отвечает"
    exit 1
fi

# Запуск WebPhone Bridge
run_background "webphone-bridge" "node webphone_bridge.js" "webphone-bridge"

# Ждем запуска WebPhone
echo "⏳ Ожидание запуска WebPhone Bridge..."
sleep 5

echo ""
echo "================================================"
echo "✅ Voice AI система успешно запущена!"
echo ""
echo "📊 Статус компонентов:"
echo "   Python AI Server: http://localhost:5000"
echo "   WebSocket Audio: ws://localhost:8080"
echo "   Health Check: http://localhost:5000/health"
echo "   WebPhone Status: http://localhost:5000/api/webphone/status"
echo ""
echo "📞 Система готова принимать звонки!"
echo ""
echo "🛑 Для остановки используйте: ./stop_system.sh"
echo "================================================"

# Мониторинг логов
echo ""
echo "📜 Мониторинг логов (Ctrl+C для выхода):"
echo ""

# Функция для красивого вывода логов
monitor_logs() {
    tail -f logs/python-server.log logs/webphone-bridge.log | while read line; do
        if [[ $line == *"ERROR"* ]] || [[ $line == *"❌"* ]]; then
            echo -e "\033[31m$line\033[0m"  # Красный для ошибок
        elif [[ $line == *"SUCCESS"* ]] || [[ $line == *"✅"* ]]; then
            echo -e "\033[32m$line\033[0m"  # Зеленый для успеха
        elif [[ $line == *"INFO"* ]] || [[ $line == *"📞"* ]]; then
            echo -e "\033[36m$line\033[0m"  # Голубой для информации
        else
            echo "$line"
        fi
    done
}

monitor_logs