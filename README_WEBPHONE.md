# Voice AI System with RingCentral WebPhone Integration
## Prime Cargo Logistics

### 🚀 Обзор новой архитектуры

Эта система использует RingCentral WebPhone (JavaScript) для автоматического приема входящих звонков и Python AI для обработки речи. Решение обходит проблему с недостающими Security/AI scopes в RingCentral API.

### 📋 Архитектура системы

```
┌─────────────────────┐         ┌──────────────────────┐
│  RingCentral Cloud  │         │   WebPhone Bridge    │
│                     │◄────────┤  (Node.js/JavaScript)│
│  Incoming Calls     │  WebRTC │                      │
└─────────────────────┘         │  - Auto Answer       │
                                │  - Audio Capture     │
                                └──────────┬───────────┘
                                          │
                                     WebSocket
                                    Audio Stream
                                          │
                                          ▼
                                ┌──────────────────────┐
                                │   Python AI Server   │
                                │                      │
                                │  - Speech-to-Text    │
                                │  - LLM Processing    │
                                │  - Text-to-Speech    │
                                └──────────────────────┘
```

### 🔧 Компоненты системы

#### 1. **WebPhone Bridge** (Node.js)
- **Файл**: `webphone-bridge/webphone_bridge.js`
- **Функции**:
  - Авторизация через JWT токен
  - Автоматический прием всех входящих звонков
  - Захват аудио потока от звонящего
  - Передача аудио в Python через WebSocket
  - Воспроизведение синтезированной речи обратно

#### 2. **Python AI Server**
- **Файлы**: 
  - `webhook_server.py` - основной сервер
  - `audio_stream_handler.py` - обработка аудио потоков
  - `speech_processor.py` - STT/TTS
  - `llm_handler.py` - AI ответы
- **Функции**:
  - WebSocket сервер для приема аудио
  - Распознавание речи (Whisper)
  - Генерация ответов (Llama 3.1)
  - Синтез речи (Coqui TTS)

### 📦 Установка и настройка

#### Предварительные требования:
- Node.js >= 16.0.0
- Python >= 3.8
- CUDA-совместимая GPU (рекомендуется)
- RingCentral аккаунт с WebPhone доступом

#### 1. Клонирование репозитория:
```bash
git clone https://github.com/scrollDynasty/voiceaicargoprime.git
cd voiceaicargoprime
```

#### 2. Настройка окружения:

Создайте `.env` файл в корне проекта:
```env
# RingCentral настройки
RINGCENTRAL_CLIENT_ID=your_client_id
RINGCENTRAL_CLIENT_SECRET=your_client_secret
RINGCENTRAL_JWT_TOKEN=your_jwt_token
RINGCENTRAL_SERVER=https://platform.ringcentral.com
```

Создайте `.env` файл в `webphone-bridge/`:
```env
# Копируйте те же настройки RingCentral
RINGCENTRAL_CLIENT_ID=your_client_id
RINGCENTRAL_CLIENT_SECRET=your_client_secret
RINGCENTRAL_JWT_TOKEN=your_jwt_token
RINGCENTRAL_SERVER=https://platform.ringcentral.com

# Python сервер
PYTHON_AI_SERVER=http://localhost:5000
PYTHON_AI_ENDPOINT=/api/handle-webphone-call

# WebSocket настройки
WEBSOCKET_PORT=8080
```

#### 3. Установка зависимостей:

Python:
```bash
pip install -r requirements.txt
```

Node.js:
```bash
cd webphone-bridge
npm install
cd ..
```

### 🚀 Запуск системы

#### Автоматический запуск:
```bash
chmod +x start_system.sh stop_system.sh
./start_system.sh
```

#### Ручной запуск:

1. Python сервер:
```bash
python webhook_server.py
```

2. WebPhone Bridge:
```bash
cd webphone-bridge
node webphone_bridge.js
```

### 📞 Как это работает

1. **Входящий звонок** → RingCentral отправляет SIP INVITE на WebPhone
2. **Автоматический ответ** → WebPhone автоматически принимает звонок через `session.accept()`
3. **Захват аудио** → WebPhone захватывает аудио поток от звонящего
4. **Стриминг в Python** → Аудио передается через WebSocket на Python сервер
5. **AI обработка**:
   - STT: Whisper распознает речь
   - LLM: Llama 3.1 генерирует ответ
   - TTS: Coqui синтезирует речь
6. **Воспроизведение** → Синтезированный ответ отправляется обратно и воспроизводится в звонке

### 🔍 Мониторинг и отладка

#### Проверка статуса:
```bash
# Health check
curl http://localhost:5000/health

# WebPhone status
curl http://localhost:5000/api/webphone/status
```

#### Логи:
- Python: `logs/python-server.log`
- WebPhone: `logs/webphone-bridge.log`
- Аудио записи: `recordings/`

#### Тестирование подключения:
```bash
cd webphone-bridge
node test_connection.js
```

### 🛠️ Решение проблем

#### WebPhone не принимает звонки:
1. Проверьте JWT токен не истек
2. Убедитесь что у аккаунта есть WebPhone permissions
3. Проверьте firewall не блокирует WebSocket порт 8080

#### Нет аудио от Python:
1. Проверьте что Whisper модель загружена
2. Убедитесь что GPU доступна для TTS
3. Проверьте WebSocket соединение активно

#### Ошибка 403 в RingCentral:
- Эта система специально разработана чтобы избежать этой ошибки!
- WebPhone не требует Security/AI scopes

### 📊 Производительность

- **Задержка ответа**: 1-3 секунды
- **Максимум одновременных звонков**: 5 (RTX 4060 8GB)
- **Качество аудио**: 16kHz, моно
- **Поддерживаемые языки**: Английский

### 🔐 Безопасность

- JWT токены хранятся в `.env` файлах
- WebSocket работает только на localhost
- Все звонки логируются для аудита
- Аудио файлы автоматически удаляются через 30 дней

### 📝 API Endpoints

#### POST /api/handle-webphone-call
Обработка нового звонка от WebPhone
```json
{
  "callId": "uuid",
  "sessionId": "sip-session-id",
  "from": "+1234567890",
  "to": "+0987654321",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### GET /api/webphone/status
Получить статус системы
```json
{
  "status": "operational",
  "websocket_running": true,
  "active_calls": 2,
  "calls": [...]
}
```

### 🤝 Вклад в проект

1. Fork репозиторий
2. Создайте feature branch
3. Commit изменения
4. Push в branch
5. Создайте Pull Request

### 📄 Лицензия

MIT License - см. LICENSE файл

### 👥 Контакты

Prime Cargo Logistics Inc.
- Email: support@primecargologistics.com
- Phone: (513) 572-5833

---

**Важно**: Эта система находится в активной разработке. Используйте в production среде с осторожностью.