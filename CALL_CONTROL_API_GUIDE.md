# RingCentral Call Control API Integration Guide

## 🎯 Обзор решения

Данное руководство описывает новую архитектуру для автоматического приема звонков через RingCentral с использованием Call Control API и WebRTC для real-time audio streaming.

## 📋 Ключевые изменения

### 1. ✅ Автоматический прием звонков (РЕАЛИЗОВАНО)

**Файл**: `webhook_server.py`

- Обновлена функция `_handle_telephony_session()` для обработки только звонков в состоянии "Ringing"
- Добавлена функция `answer_call_automatically()` для автоматического ответа через Call Control API
- Добавлена функция `start_ai_conversation()` для запуска AI диалога

### 2. ✅ Воспроизведение TTS в звонке (РЕАЛИЗОВАНО)

**Файл**: `webhook_server.py`

- Добавлена функция `play_audio_to_call()` для загрузки и воспроизведения аудио
- Обновлена `ringcentral_auth.py` для поддержки загрузки файлов

### 3. 🚧 WebRTC интеграция (БАЗОВАЯ СТРУКТУРА)

**Файл**: `webrtc_integration.py` (новый)

- Создан WebRTCManager для управления real-time audio соединениями
- Реализована структура для двустороннего audio streaming
- Подготовлена база для интеграции с RingCentral WebRTC API

## 🔧 Как это работает

### Процесс обработки входящего звонка:

1. **Webhook получает событие** о входящем звонке
2. **Проверяется статус** - обрабатываются только звонки в состоянии "Ringing"
3. **Автоматический ответ** через Call Control API
4. **Генерация приветствия** через TTS
5. **Воспроизведение аудио** в активном звонке
6. **WebRTC соединение** (TODO) для real-time взаимодействия

## 📝 Примеры использования

### Автоматический ответ на звонок:

```python
# В webhook_server.py
def answer_call_automatically(session_id, party_id, caller_info):
    response = make_request(
        'POST',
        f'/restapi/v1.0/account/~/extension/~/telephony/sessions/{session_id}/parties/{party_id}/answer'
    )
    return True
```

### Воспроизведение TTS в звонке:

```python
# Генерация аудио
audio_data = await async_synthesize("Привет! Это AI ассистент.")

# Воспроизведение в звонке
play_audio_to_call(session_id, party_id, audio_data)
```

### WebRTC соединение (планируется):

```python
# Создание WebRTC сессии
from webrtc_integration import setup_webrtc_for_call

webrtc_session_id = await setup_webrtc_for_call(telephony_session_id, party_id)

# Отправка аудио
send_audio_to_webrtc(webrtc_session_id, audio_data)

# Получение аудио
incoming_audio = get_audio_from_webrtc(webrtc_session_id)
```

## ⚠️ Известные ограничения

1. **Media API**: RingCentral может иметь ограничения на размер загружаемых аудио файлов
2. **WebRTC**: Требуется дополнительная настройка для полноценной работы
3. **Latency**: Возможны задержки при воспроизведении аудио через Media API

## 🚀 Следующие шаги

### Приоритет 1: Тестирование
- [ ] Протестировать автоматический ответ на реальных звонках
- [ ] Проверить воспроизведение TTS аудио
- [ ] Измерить задержки и производительность

### Приоритет 2: WebRTC интеграция
- [ ] Изучить RingCentral WebRTC API документацию
- [ ] Реализовать полноценное WebRTC соединение
- [ ] Добавить обработку входящего аудио потока

### Приоритет 3: Улучшения
- [ ] Добавить retry логику для критичных операций
- [ ] Реализовать кэширование TTS для частых фраз
- [ ] Добавить метрики и мониторинг

## 📚 Полезные ссылки

- [RingCentral Call Control API](https://developers.ringcentral.com/api-reference/Call-Control/answerCallParty)
- [RingCentral WebRTC Guide](https://developers.ringcentral.com/guide/voice/webrtc)
- [RingCentral Media API](https://developers.ringcentral.com/api-reference/Media/uploadMedia)

## 🐛 Отладка

### Логи для мониторинга:
```bash
# Следить за webhook событиями
tail -f webhook.log | grep "telephony/sessions"

# Мониторинг автоответа
tail -f webhook.log | grep -E "(Ringing|answer_call|✅|❌)"

# WebRTC события
tail -f webhook.log | grep "WebRTC"
```

### Проверка статуса:
```bash
# Проверить webhook подписку
python check_webhook_status.py

# Тест TTS
python test_voices.py

# Проверка авторизации
python check_jwt_expiry.py
```