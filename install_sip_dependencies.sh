#!/bin/bash

echo "🚀 Установка зависимостей для SIP/RTP сервера с Ollama"
echo "======================================================="

# Обновляем систему
echo "📦 Обновление системы..."
sudo apt-get update

# Устанавливаем системные зависимости
echo "🔧 Установка системных пакетов..."
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-venv \
    portaudio19-dev \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    espeak \
    curl

# Создаем виртуальное окружение
echo "🐍 Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

# Обновляем pip
echo "📦 Обновление pip..."
pip install --upgrade pip

# Устанавливаем Python пакеты
echo "🐍 Установка Python пакетов..."
pip install -r requirements.txt

# Проверяем установку Ollama
echo "🤖 Проверка Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama не установлена. Устанавливаем..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "✅ Ollama уже установлена"
fi

# Проверяем, запущен ли Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "🚀 Запускаем Ollama сервер..."
    ollama serve &
    sleep 5
fi

# Проверяем наличие модели
echo "🔍 Проверка модели LLaMA..."
if ! ollama list | grep -q "llama3.1:8b-instruct-q4_0"; then
    echo "📥 Загружаем модель llama3.1:8b-instruct-q4_0..."
    ollama pull llama3.1:8b-instruct-q4_0
else
    echo "✅ Модель llama3.1:8b-instruct-q4_0 уже загружена"
fi

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Скопируйте .env.example в .env и настройте параметры:"
echo "   cp .env.example .env"
echo ""
echo "2. Запустите тест Ollama:"
echo "   python3 test_ollama.py"
echo ""
echo "3. Запустите SIP сервер:"
echo "   python3 sip_server.py [IP_адрес] [SIP_порт]"
echo ""
echo "Пример:"
echo "   python3 sip_server.py 192.168.1.100 5060"