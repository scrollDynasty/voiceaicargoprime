# Руководство по настройке SIP/RTP интеграции с RingCentral

## Что это дает?

С SIP/RTP интеграцией вы получаете:
- ✅ **Real-time доступ к аудио** - прямые RTP пакеты без задержек
- ✅ **Полный контроль** - никаких браузеров, WebPhone SDK или mock объектов
- ✅ **Производительность** - минимальная задержка, максимальное качество
- ✅ **Надежность** - стандартный протокол телефонии, используемый везде

## Архитектура решения

```
┌─────────────────────────────────────────────────────┐
│                  RingCentral                         │
│                 (SIP Provider)                       │
└────────────────────┬────────────────────────────────┘
                     │ SIP/RTP
                     │
┌────────────────────▼────────────────────────────────┐
│              SIP Server (pjsua2)                    │
│  ┌──────────────────────────────────────────────┐  │
│  │          AICallHandler                       │  │
│  │  - Автоматический ответ на звонки           │  │
│  │  - Управление SIP сессией                   │  │
│  └────────────────┬─────────────────────────────┘  │
│                   │                                 │
│  ┌────────────────▼─────────────────────────────┐  │
│  │         AudioProcessor                       │  │
│  │  - Real-time обработка RTP потоков          │  │
│  │  - Буферизация аудио                        │  │
│  │  - Передача в AI систему                    │  │
│  └────────────────┬─────────────────────────────┘  │
└───────────────────┼─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│               Python AI System                       │
│  ┌──────────────────────────────────────────────┐  │
│  │     Speech Recognition (Whisper)             │  │
│  └──────────────────┬───────────────────────────┘  │
│                     ▼                               │
│  ┌──────────────────────────────────────────────┐  │
│  │         LLM (Ollama/Llama)                   │  │
│  └──────────────────┬───────────────────────────┘  │
│                     ▼                               │
│  ┌──────────────────────────────────────────────┐  │
│  │      Text-to-Speech (Coqui TTS)              │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Установка зависимостей

### 1. Установка PJSIP/pjsua2

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3-dev python3-pip
sudo apt-get install -y libasound2-dev libssl-dev libsrtp2-dev

# Установка PJSIP
cd /tmp
wget https://github.com/pjsip/pjproject/archive/2.13.tar.gz
tar -xzf 2.13.tar.gz
cd pjproject-2.13

# Конфигурация и сборка
./configure --enable-shared --disable-video --disable-sound
make dep && make
sudo make install

# Установка Python биндингов
cd pjsip-apps/src/python
python3 setup.py install
```

### 2. Обновление requirements.txt

```bash
# Добавьте в requirements.txt:
pjsua2>=2.13
pyaudio>=0.2.11
```

## Настройка RingCentral для SIP

### 1. Получение SIP credentials

```python
import requests
import os

# Получаем SIP данные через API
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

# Создаем SIP устройство
response = requests.post(
    'https://platform.ringcentral.com/restapi/v1.0/account/~/device',
    headers=headers,
    json={
        'type': 'SoftPhone',
        'name': 'AI Voice Assistant'
    }
)

device_info = response.json()
sip_info = device_info['sipInfo']

print(f"SIP Username: {sip_info['username']}")
print(f"SIP Password: {sip_info['password']}")
print(f"SIP Domain: {sip_info['domain']}")
print(f"Outbound Proxy: {sip_info['outboundProxy']}")
```

### 2. Обновление конфигурации

Добавьте в `config.py`:

```python
# SIP Configuration
SIP = {
    "username": os.getenv("RINGCENTRAL_SIP_USERNAME"),
    "password": os.getenv("RINGCENTRAL_SIP_PASSWORD"),
    "domain": os.getenv("RINGCENTRAL_SIP_DOMAIN", "sip.ringcentral.com"),
    "proxy": os.getenv("RINGCENTRAL_SIP_PROXY", "sip.ringcentral.com:5060"),
    "transport": os.getenv("SIP_TRANSPORT", "UDP"),  # UDP, TCP, TLS
    "port": int(os.getenv("SIP_PORT", "5060")),
    "secure": os.getenv("SIP_SECURE", "False").lower() == "true"
}
```

## Запуск системы

### 1. Настройка переменных окружения

```bash
# .env файл
RINGCENTRAL_SIP_USERNAME=your_sip_username
RINGCENTRAL_SIP_PASSWORD=your_sip_password
RINGCENTRAL_SIP_DOMAIN=sip.ringcentral.com
```

### 2. Запуск SIP сервера

```bash
# Запуск как отдельный процесс
python3 sip_rtp_integration.py

# Или интеграция в main.py
```

### 3. Обновленный main.py

```python
# В main.py добавьте:
from sip_rtp_integration import start_sip_server

# В функции start():
# Запускаем SIP сервер в отдельном потоке
sip_thread = threading.Thread(target=start_sip_server, daemon=True)
sip_thread.start()
logger.info("✅ SIP сервер запущен")
```

## Преимущества над WebPhone SDK

| Параметр | WebPhone SDK | SIP/RTP интеграция |
|----------|--------------|-------------------|
| Задержка | 500-1000ms | 50-100ms |
| Требует браузер | ✅ Да | ❌ Нет |
| Real-time аудио | ❌ Нет | ✅ Да |
| Контроль над потоком | ❌ Ограничен | ✅ Полный |
| Ресурсы | Высокие (браузер) | Низкие |
| Надежность | Средняя | Высокая |

## Отладка и мониторинг

### 1. Проверка регистрации SIP

```bash
# Проверка SIP регистрации
pjsua --id sip:username@sip.ringcentral.com --registrar sip:sip.ringcentral.com --username username --password password
```

### 2. Мониторинг RTP потоков

```bash
# tcpdump для мониторинга RTP
sudo tcpdump -i any -n port 5060 or portrange 10000-20000
```

### 3. Логирование

В `sip_rtp_integration.py` уже настроено подробное логирование:
- SIP события (регистрация, звонки)
- RTP статистика (пакеты, задержка, jitter)
- AI обработка (STT, LLM, TTS)

## Troubleshooting

### Проблема: SIP регистрация не работает
- Проверьте firewall правила для портов 5060 (SIP) и 10000-20000 (RTP)
- Убедитесь что SIP credentials правильные
- Попробуйте использовать TCP вместо UDP

### Проблема: Нет аудио
- Проверьте NAT настройки
- Используйте STUN сервер: `stun.ringcentral.com`
- Проверьте кодеки (PCMU, PCMA, opus)

### Проблема: Высокая задержка
- Уменьшите размер аудио буфера
- Используйте более быструю модель STT/TTS
- Оптимизируйте LLM запросы

## Заключение

SIP/RTP интеграция - это профессиональное решение для AI систем обработки звонков:
- Прямой доступ к аудио потокам
- Минимальная задержка
- Полный контроль над звонком
- Никаких браузеров и mock объектов

Это именно то, что нужно для production-ready AI ассистента!