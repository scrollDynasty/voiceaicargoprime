# RingCentral API Integration - Изменения

## Созданные файлы

### 1. ringcentral_client.py
- JWT авторизация и refresh token логика
- Call Control API методы (answer, transfer, hangup)
- Создание webhook subscription
- Validation token handling

### 2. Обновленный webhook_server.py
- Обработка telephony/sessions событий
- Автоматический ответ на входящие звонки
- REST endpoints для управления звонками
- Автоматическое создание webhook subscription при старте

## Необходимые переменные окружения (.env)

```
# RingCentral API
RINGCENTRAL_CLIENT_ID=your_client_id
RINGCENTRAL_CLIENT_SECRET=your_client_secret
RINGCENTRAL_JWT_TOKEN=your_jwt_token
RINGCENTRAL_MAIN_NUMBER=+15135725833

# Webhook
WEBHOOK_URL=https://your-domain.com/webhook
WEBHOOK_SECRET=your_secret_here
```

## Как запустить

1. Создайте JWT токен в RingCentral Developer Console
2. Настройте переменные окружения в .env
3. Запустите: python webhook_server.py

Сервер автоматически создаст webhook subscription и начнет обрабатывать входящие звонки.
