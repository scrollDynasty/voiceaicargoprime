#!/bin/bash

# Скрипт остановки Voice AI системы
# Prime Cargo Logistics

echo "🛑 Остановка Voice AI системы..."
echo "================================"

# Функция для остановки процесса
stop_process() {
    local name=$1
    local pid_file="logs/$name.pid"
    
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if ps -p $PID > /dev/null 2>&1; then
            echo "⏹️  Остановка $name (PID: $PID)..."
            kill $PID
            sleep 2
            
            # Если процесс все еще работает, используем SIGKILL
            if ps -p $PID > /dev/null 2>&1; then
                echo "⚠️  Принудительная остановка $name..."
                kill -9 $PID
            fi
            
            rm -f "$pid_file"
            echo "✅ $name остановлен"
        else
            echo "ℹ️  $name не запущен (PID файл устарел)"
            rm -f "$pid_file"
        fi
    else
        echo "ℹ️  $name не запущен (PID файл не найден)"
    fi
}

# Остановка компонентов

stop_process "python-server"

# Очистка временных файлов
echo "🧹 Очистка временных файлов..."
rm -f temp/*.tmp

echo ""
echo "================================"
echo "✅ Voice AI система остановлена"
echo "================================"