#!/bin/bash

# Скрипт запуска SIP/RTP Voice AI системы
# Прямой перехват звонков без веб-интерфейса

echo "🚀 Запуск SIP/RTP Voice AI системы"
echo "===================================="
echo "📞 Прямой перехват звонков через SIP"
echo ""

# Проверка зависимостей
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 не найден. Запустите ./install_sip_dependencies.sh"
        exit 1
    fi
}

echo "📋 Проверка зависимостей..."
check_command python3
check_command pip3

# Создание директорий
echo "📁 Создание необходимых директорий..."
mkdir -p logs
mkdir -p recordings
mkdir -p temp

# Получение IP адреса
if [ -z "$1" ]; then
    # Автоматическое определение IP
    LOCAL_IP=$(hostname -I | awk '{print $1}')
    echo "🌐 Используется автоматически определенный IP: $LOCAL_IP"
else
    LOCAL_IP=$1
    echo "🌐 Используется указанный IP: $LOCAL_IP"
fi

# SIP порт (по умолчанию 5060)
SIP_PORT=${2:-5060}
echo "📡 SIP порт: $SIP_PORT"

# Проверка, не занят ли порт
if netstat -tuln | grep -q ":$SIP_PORT "; then
    echo "❌ Порт $SIP_PORT уже используется!"
    echo "💡 Попробуйте другой порт или остановите процесс, использующий этот порт"
    exit 1
fi

# Запуск SIP сервера
echo ""
echo "▶️  Запуск SIP сервера..."
python3 sip_server.py $LOCAL_IP $SIP_PORT > logs/sip_server.log 2>&1 &
SIP_PID=$!
echo $SIP_PID > logs/sip_server.pid

sleep 2

# Проверка что сервер запустился
if kill -0 $SIP_PID 2>/dev/null; then
    echo "✅ SIP сервер успешно запущен (PID: $SIP_PID)"
else
    echo "❌ SIP сервер не смог запуститься"
    echo "📋 Проверьте логи: tail -f logs/sip_server.log"
    exit 1
fi

echo ""
echo "===================================="
echo "✅ SIP/RTP Voice AI система запущена!"
echo ""
echo "📊 Информация о системе:"
echo "   SIP адрес: sip:ai@$LOCAL_IP:$SIP_PORT"
echo "   RTP порты: 10000-10100"
echo "   Логи: logs/sip_server.log"
echo ""
echo "📞 Настройка SIP клиента:"
echo "   Server: $LOCAL_IP"
echo "   Port: $SIP_PORT"
echo "   Username: ai"
echo "   Password: (не требуется)"
echo ""
echo "🛑 Для остановки: ./stop_sip_system.sh"
echo "===================================="
echo ""
echo "📜 Мониторинг логов..."
echo ""

# Цветной вывод логов
tail -f logs/sip_server.log | while read line; do
    if [[ $line == *"ERROR"* ]] || [[ $line == *"❌"* ]]; then
        echo -e "\033[31m$line\033[0m"  # Красный
    elif [[ $line == *"SUCCESS"* ]] || [[ $line == *"✅"* ]]; then
        echo -e "\033[32m$line\033[0m"  # Зеленый
    elif [[ $line == *"📞"* ]] || [[ $line == *"INVITE"* ]]; then
        echo -e "\033[33m$line\033[0m"  # Желтый
    elif [[ $line == *"INFO"* ]] || [[ $line == *"🎤"* ]]; then
        echo -e "\033[36m$line\033[0m"  # Голубой
    else
        echo "$line"
    fi
done