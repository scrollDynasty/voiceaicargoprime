#!/bin/bash

echo "🚀 Запуск Voice AI для RingCentral"
echo "=================================="
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка конфигурации
echo "📋 Проверка конфигурации..."

if ! grep -q "username':" ringcentral_config.py | grep -v "''"; then
    echo -e "${RED}❌ Не настроен username в ringcentral_config.py${NC}"
    echo -e "${YELLOW}💡 Откройте ringcentral_config.py и заполните ваши данные RingCentral${NC}"
    exit 1
fi

if ! grep -q "public_ip':" ringcentral_config.py | grep -v "''"; then
    echo -e "${RED}❌ Не указан публичный IP в ringcentral_config.py${NC}"
    echo -e "${YELLOW}💡 Узнайте ваш внешний IP на https://whatismyip.com${NC}"
    echo -e "${YELLOW}   и добавьте его в ringcentral_config.py${NC}"
    exit 1
fi

# Проверка Ollama
echo "🤖 Проверка Ollama..."
if ! pgrep -x "ollama" > /dev/null; then
    echo -e "${YELLOW}⚠️  Ollama не запущен. Запускаю...${NC}"
    ollama serve > logs/ollama.log 2>&1 &
    sleep 3
fi

# Проверка модели
if ! ollama list | grep -q "llama3.1:8b-instruct-q4_0"; then
    echo -e "${RED}❌ Модель llama3.1:8b-instruct-q4_0 не найдена${NC}"
    echo -e "${YELLOW}💡 Загрузите модель: ollama pull llama3.1:8b-instruct-q4_0${NC}"
    exit 1
fi

# Создание директорий
mkdir -p logs
mkdir -p recordings

# Проверка портов
echo "🔍 Проверка портов..."

if netstat -tuln 2>/dev/null | grep -q ":5060 "; then
    echo -e "${RED}❌ Порт 5060 уже используется!${NC}"
    echo -e "${YELLOW}💡 Остановите процесс или измените порт в конфигурации${NC}"
    exit 1
fi

# Информация о настройках
echo ""
echo -e "${GREEN}✅ Конфигурация проверена${NC}"
echo ""
echo "📊 Параметры запуска:"

PUBLIC_IP=$(grep "public_ip" ringcentral_config.py | grep -o "'[^']*'" | sed "s/'//g" | tail -1)
USERNAME=$(grep "username" ringcentral_config.py | grep -o "'[^']*'" | sed "s/'//g" | head -1)
DOMAIN=$(grep "domain" ringcentral_config.py | grep -o "'[^']*'" | sed "s/'//g" | head -1)

echo "   🌐 Публичный IP: $PUBLIC_IP"
echo "   👤 RingCentral User: $USERNAME"
echo "   🏢 RingCentral Domain: $DOMAIN"
echo ""

# Рекомендации по настройке
echo "📞 Настройка RingCentral:"
echo "   1. Войдите в RingCentral Admin Portal"
echo "   2. Настройте переадресацию на: sip:ai@$PUBLIC_IP:5060"
echo "   3. Или используйте SIP registration с вашими credentials"
echo ""

echo "🔧 Настройка firewall (если нужно):"
echo "   sudo ufw allow 5060/udp"
echo "   sudo ufw allow 5060/tcp"
echo "   sudo ufw allow 10000:20000/udp"
echo ""

# Запуск сервера
echo -e "${GREEN}▶️  Запускаю SIP сервер...${NC}"
echo ""

# Запуск с цветным выводом логов
python3 ringcentral_sip_server.py 2>&1 | while IFS= read -r line; do
    if [[ $line == *"ERROR"* ]] || [[ $line == *"❌"* ]]; then
        echo -e "${RED}$line${NC}"
    elif [[ $line == *"SUCCESS"* ]] || [[ $line == *"✅"* ]]; then
        echo -e "${GREEN}$line${NC}"
    elif [[ $line == *"📞"* ]] || [[ $line == *"INVITE"* ]]; then
        echo -e "${YELLOW}$line${NC}"
    elif [[ $line == *"WARNING"* ]] || [[ $line == *"⚠️"* ]]; then
        echo -e "${YELLOW}$line${NC}"
    else
        echo "$line"
    fi
done