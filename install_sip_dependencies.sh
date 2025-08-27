#!/bin/bash

echo "🚀 Установка зависимостей для SIP/RTP сервера"
echo "============================================="

# Обновляем систему
echo "📦 Обновление системы..."
sudo apt-get update

# Устанавливаем системные зависимости
echo "🔧 Установка системных пакетов..."
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    portaudio19-dev \
    libsndfile1 \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev

# Устанавливаем Python пакеты для SIP/RTP
echo "🐍 Установка Python пакетов..."
pip3 install --upgrade pip

# SIP/RTP библиотеки
pip3 install \
    pyVoIP \
    pjsua2 \
    aiortc \
    av

# Аудио обработка
pip3 install \
    pyaudio \
    sounddevice \
    scipy \
    numpy

# Удаляем веб-зависимости из requirements.txt
echo "🧹 Обновляем requirements.txt (удаляем веб-компоненты)..."
cat > requirements_sip.txt << EOF
# Core SIP/RTP
pyVoIP==1.6.5
pjsua2
aiortc

# Speech processing  
openai-whisper
torch
torchaudio
numpy
librosa==0.10.1
soundfile==0.12.1

# Text-to-Speech
TTS

# Audio processing
pydub==0.25.1
webrtcvad
pyaudio
sounddevice
scipy

# AI
openai
anthropic

# Utilities
python-dotenv==1.0.0
structlog

# System utilities
psutil
EOF

echo "✅ Установка завершена!"
echo ""
echo "📞 Теперь можно запустить SIP сервер:"
echo "   python3 sip_server.py [IP_адрес] [SIP_порт]"
echo ""
echo "Пример:"
echo "   python3 sip_server.py 192.168.1.100 5060"