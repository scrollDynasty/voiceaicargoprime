#!/bin/bash
# Скрипт установки PJSIP для SIP/RTP интеграции

echo "🔧 Установка PJSIP для SIP/RTP интеграции..."

# Обновление системы
echo "📦 Обновление пакетов..."
sudo apt-get update -y

# Установка зависимостей
echo "📦 Установка зависимостей..."
sudo apt-get install -y \
    build-essential \
    python3-dev \
    python3-pip \
    libasound2-dev \
    libssl-dev \
    libsrtp2-dev \
    libopus-dev \
    portaudio19-dev \
    python3-numpy

# Создание временной директории
TEMP_DIR="/tmp/pjsip_install"
mkdir -p $TEMP_DIR
cd $TEMP_DIR

# Загрузка PJSIP
echo "📥 Загрузка PJSIP v2.13..."
wget https://github.com/pjsip/pjproject/archive/refs/tags/2.13.tar.gz
tar -xzf 2.13.tar.gz
cd pjproject-2.13

# Конфигурация PJSIP
echo "⚙️ Конфигурация PJSIP..."
./configure \
    --enable-shared \
    --disable-video \
    --disable-sound \
    --with-ssl \
    --enable-epoll \
    CFLAGS="-O2 -DNDEBUG"

# Компиляция
echo "🔨 Компиляция PJSIP (это может занять несколько минут)..."
make dep
make -j$(nproc)

# Установка
echo "📦 Установка PJSIP..."
sudo make install
sudo ldconfig

# Установка Python биндингов
echo "🐍 Установка Python биндингов..."
cd pjsip-apps/src/python
python3 setup.py build
sudo python3 setup.py install

# Проверка установки
echo "✅ Проверка установки..."
python3 -c "import pjsua2; print('PJSIP установлен успешно!')"

# Установка дополнительных Python пакетов
echo "📦 Установка Python пакетов для аудио обработки..."
pip3 install --upgrade \
    pyaudio \
    sounddevice \
    scipy \
    librosa

# Очистка
echo "🧹 Очистка временных файлов..."
cd /
rm -rf $TEMP_DIR

echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Получите SIP credentials от RingCentral"
echo "2. Добавьте их в .env файл:"
echo "   RINGCENTRAL_SIP_USERNAME=your_username"
echo "   RINGCENTRAL_SIP_PASSWORD=your_password"
echo "3. Запустите SIP сервер: python3 sip_rtp_integration.py"