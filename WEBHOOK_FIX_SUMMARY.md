# Исправления Webhook для RingCentral

## 📋 Обзор проблем и решений

### 🔴 Проблема 1: Структура обработчика
**Проблема**: Обработка POST запросов находилась внутри блока GET запросов
**Решение**: Исправлена структура условной логики в функции `ringcentral_webhook()`

### 🔴 Проблема 2: Автоматический парсинг JSON
**Проблема**: Flask автоматически пытался парсить JSON даже для пустых POST запросов
**Решение**: Добавлен декоратор `@disable_auto_json_parsing` для отключения автоматического парсинга

### 🔴 Проблема 3: Обработка пустых POST запросов
**Проблема**: Пустые POST запросы вызывали ошибку 500
**Решение**: Добавлена проверка на пустое тело запроса перед парсингом JSON

## ✅ Внесенные изменения

### 1. Декоратор для отключения автопарсинга (строки 45-66)
```python
def disable_auto_json_parsing(f):
    """
    Декоратор для отключения автоматического парсинга JSON
    Flask автоматически парсит JSON когда Content-Type: application/json
    Этот декоратор позволяет обработать запрос вручную
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Сохраняем оригинальный метод get_json
        original_get_json = request.get_json
        
        # Переопределяем get_json чтобы он возвращал None
        request.get_json = lambda *args, **kwargs: None
        
        try:
            result = f(*args, **kwargs)
        finally:
            # Восстанавливаем оригинальный метод
            request.get_json = original_get_json
        
        return result
    return decorated_function
```

### 2. Исправленный обработчик webhook (строки 97-127)
```python
@app.route('/webhook', methods=['GET', 'POST'])
@disable_auto_json_parsing
def ringcentral_webhook():
    """
    Обработчик webhook от RingCentral
    
    GET: Валидация подписки с hub.challenge
    POST: Обработка webhook событий
    """
    # Обработка GET запросов для валидации
    if request.method == 'GET':
        challenge = request.args.get('hub.challenge')
        if challenge:
            logger.info(f"Получен validation challenge: {challenge}")
            return Response(challenge, content_type='text/plain')
        else:
            logger.warning("GET запрос без hub.challenge параметра")
            return jsonify({"error": "Missing hub.challenge"}), 400
    
    # Обработка POST запросов
    elif request.method == 'POST':
        # Логируем заголовки для отладки
        logger.debug(f"Headers: {dict(request.headers)}")
        
        # Получаем сырые данные
        raw_data = request.get_data()
        
        # Проверяем есть ли данные
        if not raw_data:
            logger.info("Получен пустой POST запрос для валидации webhook")
            return jsonify({"status": "ok"}), 200
        
        # Проверка подписи webhook (делаем до парсинга JSON)
        if not _verify_webhook_signature(request):
            logger.warning("Неверная подпись webhook")
            return jsonify({"error": "Invalid signature"}), 401
        
        # Пытаемся распарсить JSON
        try:
            webhook_data = json.loads(raw_data.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON данных: {e}")
            logger.error(f"Raw data: {raw_data[:500]}")  # Логируем первые 500 символов
            return jsonify({"error": "Invalid JSON"}), 400
        
        logger.info(f"Получено webhook событие: {json.dumps(webhook_data, indent=2)}")
        
        # Извлекаем body из webhook payload
        body = webhook_data.get('body', {})
        
        # Проверяем наличие telephonySessionId для telephony событий
        if body.get('telephonySessionId'):
            return _handle_telephony_session(body)
        else:
            logger.info(f"Не telephony событие: {webhook_data.get('uuid', 'unknown')}")
            return jsonify({"status": "received"}), 200
```

### 3. Улучшенное логирование (строки 40-65)
```python
# Настройка логирования для Flask
app.logger.setLevel(logging.DEBUG)

# Добавляем middleware для логирования всех запросов
@app.before_request
def log_request_info():
    """Логируем информацию о каждом запросе"""
    logger.debug('=' * 80)
    logger.debug(f'Request: {request.method} {request.url}')
    logger.debug(f'Headers: {dict(request.headers)}')
    logger.debug(f'Content-Type: {request.content_type}')
    logger.debug(f'Content-Length: {request.content_length}')
    if request.method in ['POST', 'PUT', 'PATCH']:
        # Логируем первые 1000 символов тела запроса
        data = request.get_data(as_text=True)
        if data:
            logger.debug(f'Body (first 1000 chars): {data[:1000]}')
        else:
            logger.debug('Body: <empty>')
    logger.debug('=' * 80)

@app.after_request
def log_response_info(response):
    """Логируем информацию о каждом ответе"""
    logger.debug(f'Response: {response.status}')
    return response
```

### 4. Улучшенная проверка подписи (строки 154-205)
- Добавлено детальное логирование
- Улучшена обработка случаев когда подпись не требуется
- Добавлен вывод частичной информации о подписях для отладки

## 🧪 Тестирование

Создан скрипт `test_webhook.py` для тестирования всех сценариев:

1. **Пустой POST запрос** - должен возвращать 200 OK
2. **GET с hub.challenge** - должен возвращать challenge как plain text
3. **GET без hub.challenge** - должен возвращать 400 Bad Request
4. **POST с валидным JSON** - должен обрабатывать и возвращать 200 OK
5. **POST с неверной подписью** - должен возвращать 401 Unauthorized
6. **POST с невалидным JSON** - должен возвращать 400 Bad Request
7. **POST без Content-Type** - должен обрабатывать корректно
8. **Telephony событие** - должен обрабатывать входящие звонки

### Запуск тестов:
```bash
# Запустить webhook сервер
python webhook_server.py

# В другом терминале запустить тесты
python test_webhook.py
```

## 🎯 Результат

После внесенных изменений:
- ✅ RingCentral может успешно валидировать webhook
- ✅ Пустые POST запросы обрабатываются корректно
- ✅ JSON данные парсятся только когда они есть
- ✅ Проверка подписи работает корректно
- ✅ Все тестовые сценарии проходят успешно

## 📝 Рекомендации

1. **Мониторинг**: Следите за логами для выявления проблем
2. **Безопасность**: Всегда используйте webhook_secret в production
3. **Обработка ошибок**: Добавьте retry логику для критичных операций
4. **Масштабирование**: Рассмотрите использование очередей для обработки webhook