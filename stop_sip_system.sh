#!/bin/bash

# Скрипт остановки SIP/RTP Voice AI системы

echo "🛑 Остановка SIP/RTP Voice AI системы"
echo "===================================="

# Функция остановки процесса
stop_process() {
    local pid_file=$1
    local name=$2
    
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if kill -0 $PID 2>/dev/null; then
            echo "⏹️  Остановка $name (PID: $PID)..."
            kill $PID
            sleep 1
            
            # Если процесс все еще работает, используем SIGKILL
            if kill -0 $PID 2>/dev/null; then
                echo "⚠️  Принудительная остановка $name..."
                kill -9 $PID
            fi
            
            rm -f "$pid_file"
            echo "✅ $name остановлен"
        else
            echo "ℹ️  $name не запущен (PID $PID не существует)"
            rm -f "$pid_file"
        fi
    else
        echo "ℹ️  $name не запущен (PID файл не найден)"
    fi
}

# Остановка SIP сервера
stop_process "logs/sip_server.pid" "SIP сервер"

# Очистка временных файлов
echo "🧹 Очистка временных файлов..."
rm -f temp/*.tmp

echo ""
echo "===================================="
echo "✅ Система остановлена"
echo "===================================="