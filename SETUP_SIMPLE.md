# Упрощенная установка Voice AI для SIP

## О проекте

Этот проект реализует голосового ассистента для SIP телефонии БЕЗ использования сложных библиотек типа pjsua2. Вместо этого используется:
- Прямая работа с SIP протоколом через сокеты
- Ollama для локальной AI модели (вместо OpenAI)
- Whisper для распознавания речи
- TTS для синтеза речи

## Быстрая установка

### 1. Установка системных зависимостей
```bash
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-venv \
    portaudio19-dev \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    espeak \
    curl \
    python3-requests
```

### 2. Установка Ollama
```bash
# Установка
curl -fsSL https://ollama.com/install.sh | sh

# Запуск сервера (в отдельном терминале)
ollama serve

# Загрузка модели (в другом терминале)
ollama pull llama3.1:8b-instruct-q4_0
```

### 3. Создание виртуального окружения
```bash
cd /path/to/project
python3 -m venv venv
source venv/bin/activate
```

### 4. Установка Python зависимостей
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Настройка
```bash
# Копируем пример конфигурации
cp .env.example .env

# Редактируем .env файл
nano .env
```

Основные параметры в .env:
```
# SIP настройки вашей АТС
SIP_USERNAME=your_extension
SIP_PASSWORD=your_password
SIP_SERVER=your_pbx_ip
SIP_PORT=5060

# Ollama (обычно менять не нужно)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q4_0
```

## Проверка установки

### 1. Тест Ollama
```bash
python3 test_ollama.py
```

Должен показать:
- ✅ Ollama сервер доступен
- ✅ Модель найдена
- ✅ Тестовый ответ получен

### 2. Запуск SIP сервера
```bash
# Формат: python3 sip_server.py [ваш_IP] [порт]
python3 sip_server.py 192.168.1.100 5060
```

## Как это работает

1. **SIP сервер** слушает входящие звонки на указанном IP и порту
2. **Аудио поток** принимается через RTP протокол
3. **Whisper** распознает речь абонента
4. **Ollama (LLaMA)** генерирует ответ
5. **TTS** синтезирует голос
6. **Ответ** отправляется обратно абоненту

## Решение проблем

### "Не удалось подключиться к Ollama"
```bash
# Проверьте, запущен ли сервер
ps aux | grep ollama

# Если нет, запустите
ollama serve
```

### "Модель не найдена"
```bash
# Проверьте список моделей
ollama list

# Загрузите нужную модель
ollama pull llama3.1:8b-instruct-q4_0
```

### "Ошибка при установке pyaudio"
```bash
# Установите системные зависимости
sudo apt-get install -y portaudio19-dev python3-pyaudio
```

### "SIP сервер не принимает звонки"
1. Проверьте firewall:
```bash
sudo ufw allow 5060/udp
sudo ufw allow 5060/tcp
sudo ufw allow 10000:20000/udp
```

2. Проверьте правильность IP адреса:
```bash
ip addr show
```

## Минимальные требования

- Ubuntu 20.04+ или Debian 11+
- Python 3.8+
- 8GB RAM (для модели LLaMA)
- 10GB свободного места на диске
- Стабильное сетевое соединение

## Преимущества этого подхода

✅ **Без pjsua2** - не нужна сложная компиляция PJSIP
✅ **Локальная AI** - работает без интернета после загрузки модели
✅ **Простая архитектура** - легко понять и модифицировать код
✅ **Минимум зависимостей** - только необходимые библиотеки