# Интеграция Voice AI с RingCentral

## Как это работает

Когда кто-то звонит на ваш номер RingCentral, звонок можно перенаправить на вашу локальную нейросеть через SIP протокол. Вот схема:

```
[Звонящий] → [RingCentral] → [SIP Trunk] → [Ваш локальный SIP сервер] → [Нейросеть AI]
```

## Что нужно для работы

### 1. На стороне RingCentral

У вас должен быть один из следующих планов:
- RingCentral Office
- RingCentral MVP
- Любой план с поддержкой SIP trunking

### 2. На вашей стороне

- **Публичный IP адрес** или **проброс портов** на роутере
- Открытые порты:
  - 5060 (SIP) - для сигнализации
  - 10000-20000 (RTP) - для аудио потока

## Пошаговая настройка

### Шаг 1: Получение SIP credentials от RingCentral

1. Войдите в RingCentral Admin Portal
2. Перейдите в **Phone System** → **Phones & Devices**
3. Нажмите **Add Device** → **Other Phone** → **SIP Phone**
4. Получите:
   - **SIP Domain** (например, sip.ringcentral.com)
   - **Username** (обычно ваш extension)
   - **Password** (SIP пароль)
   - **Outbound Proxy** (если требуется)

### Шаг 2: Настройка проброса портов (если у вас нет публичного IP)

На вашем роутере настройте:
```
Внешний порт 5060 → Внутренний IP:5060 (UDP/TCP)
Внешний порт 10000-20000 → Внутренний IP:10000-20000 (UDP)
```

### Шаг 3: Настройка локального SIP сервера

1. Создайте файл конфигурации:
```bash
nano ringcentral_config.py
```

2. Добавьте настройки:
```python
# RingCentral SIP настройки
RINGCENTRAL_CONFIG = {
    'domain': 'sip.ringcentral.com',
    'username': 'ваш_extension',
    'password': 'ваш_sip_пароль',
    'extension': 'ваш_номер_extension',
    'outbound_proxy': 'sip-ams.ringcentral.com',  # или другой в зависимости от региона
    'transport': 'UDP',
    'register_interval': 300,  # секунд
    'codec': 'PCMU',  # или PCMA
}

# Локальные настройки
LOCAL_CONFIG = {
    'public_ip': 'ваш_публичный_ip',  # или внешний IP роутера
    'local_ip': '0.0.0.0',  # слушать на всех интерфейсах
    'sip_port': 5060,
    'rtp_start_port': 10000,
    'rtp_end_port': 20000,
}
```

### Шаг 4: Модификация SIP сервера для работы с RingCentral

Создайте новый файл `ringcentral_sip_server.py`:

```python
#!/usr/bin/env python3
"""
SIP сервер для интеграции с RingCentral
"""

import socket
import threading
import hashlib
import time
import re
from datetime import datetime
import logging
from sip_voice_ai_engine import VoiceAIEngine
from sip_speech_processor import SpeechProcessor
from ringcentral_config import RINGCENTRAL_CONFIG, LOCAL_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RingCentralSIPServer:
    def __init__(self):
        self.config = RINGCENTRAL_CONFIG
        self.local_config = LOCAL_CONFIG
        self.ai_engine = VoiceAIEngine()
        self.speech_processor = SpeechProcessor()
        self.registered = False
        self.call_id_counter = 0
        
        # SIP socket
        self.sip_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sip_socket.bind((self.local_config['local_ip'], self.local_config['sip_port']))
        
        logger.info(f"🚀 RingCentral SIP сервер запущен на порту {self.local_config['sip_port']}")
        
    def register_with_ringcentral(self):
        """Регистрация на RingCentral SIP сервере"""
        register_request = self.build_register_request()
        
        # Отправляем REGISTER запрос
        server_addr = (self.config['domain'], 5060)
        self.sip_socket.sendto(register_request.encode(), server_addr)
        
        logger.info(f"📤 Отправлен REGISTER запрос на {self.config['domain']}")
        
    def build_register_request(self):
        """Построение SIP REGISTER запроса"""
        from_uri = f"sip:{self.config['username']}@{self.config['domain']}"
        to_uri = from_uri
        contact_uri = f"sip:{self.config['username']}@{self.local_config['public_ip']}:{self.local_config['sip_port']}"
        call_id = f"{int(time.time())}@{self.local_config['public_ip']}"
        
        request = f"REGISTER sip:{self.config['domain']} SIP/2.0\\r\\n"
        request += f"Via: SIP/2.0/UDP {self.local_config['public_ip']}:{self.local_config['sip_port']};branch=z9hG4bK{int(time.time())}\\r\\n"
        request += f"From: {from_uri};tag={int(time.time())}\\r\\n"
        request += f"To: {to_uri}\\r\\n"
        request += f"Call-ID: {call_id}\\r\\n"
        request += f"CSeq: 1 REGISTER\\r\\n"
        request += f"Contact: {contact_uri}\\r\\n"
        request += f"Expires: {self.config['register_interval']}\\r\\n"
        request += f"User-Agent: VoiceAI/1.0\\r\\n"
        request += f"Content-Length: 0\\r\\n"
        request += "\\r\\n"
        
        return request
        
    def run(self):
        """Запуск сервера"""
        # Сначала регистрируемся
        self.register_with_ringcentral()
        
        # Запускаем поток для переregistрации
        threading.Thread(target=self.registration_loop, daemon=True).start()
        
        # Основной цикл обработки сообщений
        while True:
            try:
                data, addr = self.sip_socket.recvfrom(65535)
                message = data.decode('utf-8')
                threading.Thread(target=self.handle_sip_message, args=(message, addr)).start()
            except Exception as e:
                logger.error(f"Ошибка: {e}")

    def registration_loop(self):
        """Цикл переregistрации"""
        while True:
            time.sleep(self.config['register_interval'] - 30)  # За 30 секунд до истечения
            self.register_with_ringcentral()
            
    def handle_sip_message(self, message, addr):
        """Обработка входящих SIP сообщений"""
        lines = message.split('\\r\\n')
        if not lines:
            return
            
        first_line = lines[0]
        
        if first_line.startswith('INVITE'):
            logger.info("📞 Входящий звонок!")
            self.handle_invite(message, addr)
        elif first_line.startswith('SIP/2.0 200 OK'):
            logger.info("✅ Успешная регистрация на RingCentral")
            self.registered = True
        elif first_line.startswith('SIP/2.0 401'):
            logger.info("🔐 Требуется аутентификация")
            self.handle_auth_challenge(message, addr)

if __name__ == "__main__":
    server = RingCentralSIPServer()
    server.run()
```

### Шаг 5: Настройка переадресации в RingCentral

1. В RingCentral Admin Portal перейдите в **Call Handling & Forwarding**
2. Настройте правило переадресации:
   - **Forward to**: Other Phone
   - **Number**: sip:ai@ваш_публичный_ip:5060
3. Или используйте **Simultaneous Ring** для параллельного звонка

### Шаг 6: Запуск системы

```bash
# Запуск Ollama (в отдельном терминале)
ollama serve

# Запуск SIP сервера
python3 ringcentral_sip_server.py
```

## Проверка работоспособности

### 1. Проверка регистрации
В логах должно появиться:
```
✅ Успешная регистрация на RingCentral
```

### 2. Тестовый звонок
Позвоните на ваш RingCentral номер. В логах должно появиться:
```
📞 Входящий звонок!
🎤 Обработка аудио...
🤖 AI ответ: ...
```

## Возможные проблемы

### "Не регистрируется на RingCentral"
- Проверьте правильность SIP credentials
- Убедитесь, что порты открыты
- Проверьте firewall

### "Звонки не доходят"
- Проверьте настройки переадресации в RingCentral
- Убедитесь, что указан правильный публичный IP
- Проверьте NAT настройки

### "Плохое качество звука"
- Увеличьте пропускную способность
- Используйте кодек G.711 (PCMU/PCMA)
- Проверьте сетевые задержки

## Альтернативный вариант через RingCentral API

Если прямая SIP интеграция сложна, можно использовать:
1. **WebRTC SDK** - для браузерной интеграции
2. **Call Control API** - для управления звонками через REST API
3. **RingCentral Softphone SDK** - для создания собственного софтфона

## Безопасность

⚠️ **Важно:**
- Используйте VPN или зашифрованное соединение
- Ограничьте доступ по IP в firewall
- Регулярно меняйте SIP пароли
- Мониторьте логи на предмет подозрительной активности