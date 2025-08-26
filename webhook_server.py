"""
Webhook Server для RingCentral интеграции
Обрабатывает telephony/sessions события от RingCentral
"""

import logging
import json
import asyncio
import hmac
import hashlib
import base64
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, Response, make_response
from flask_cors import CORS
import threading
from functools import wraps

from voice_ai_engine import voice_ai_engine
from speech_processor import async_synthesize
from config import Config
from ringcentral_auth import make_request
from audio_stream_handler import audio_stream_handler  # Новый импорт

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, Config.LOGGING["level"]),
    format=Config.LOGGING["format"],
    handlers=[
        logging.FileHandler(Config.LOGGING["file"]),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Создание Flask приложения
app = Flask(__name__)
CORS(app)

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

# Глобальные переменные
active_calls = {}
call_lock = threading.Lock()
subscription_id = None

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

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    try:
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "ringcentral_connected": subscription_id is not None,
            "subscription_active": subscription_id is not None,
            "active_calls": len(active_calls),
            "voice_ai_status": voice_ai_engine.health_check()
        }
        return jsonify(health_data), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/webhook/validate', methods=['POST'])
def webhook_validate():
    """Endpoint для валидации webhook от RingCentral"""
    logger.info("Получен запрос валидации webhook")
    return jsonify({"status": "ok"}), 200

@app.route('/webhook/test', methods=['POST'])
def webhook_test():
    """Простой endpoint для тестирования webhook"""
    logger.info("Получен тестовый POST запрос")
    return jsonify({"status": "ok", "message": "Webhook is working"}), 200

@app.route('/test/webhook', methods=['POST'])
def test_webhook():
    """Тестовый endpoint для проверки webhook событий"""
    try:
        logger.info("🧪 ТЕСТОВЫЙ WEBHOOK - получен запрос")
        
        # Логируем все заголовки
        logger.info(f"🧪 Заголовки: {dict(request.headers)}")
        
        # Логируем данные
        raw_data = request.get_data()
        logger.info(f"🧪 Сырые данные: {raw_data[:500]}")
        
        if raw_data:
            try:
                webhook_data = json.loads(raw_data.decode('utf-8'))
                logger.info(f"🧪 JSON данные: {json.dumps(webhook_data, indent=2)}")
            except json.JSONDecodeError as e:
                logger.error(f"🧪 Ошибка парсинга JSON: {e}")
        
        return jsonify({"status": "test_received", "message": "Test webhook working"}), 200
        
    except Exception as e:
        logger.error(f"🧪 Ошибка тестового webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['GET', 'POST'])
@disable_auto_json_parsing
def ringcentral_webhook():
    """
    Обработчик webhook от RingCentral
    
    GET запросы:
    - hub.challenge: Валидация подписки (возвращает challenge как plain text)
    - caller, name, called: Входящий звонок от External App
    
    POST запросы:
    - Пустой POST: Валидация webhook (возвращает Validation-Token)
    - JSON данные: Обработка webhook событий
    """
    logger.info(f"📞 Получен {request.method} запрос на /webhook")
    
    # Обработка GET запросов
    if request.method == 'GET':
        logger.info(f"🔍 GET параметры: {dict(request.args)}")
        
        # 1. Проверяем hub.challenge для верификации webhook URL
        challenge = request.args.get('hub.challenge')
        if challenge:
            logger.info(f"✅ Получен validation challenge: {challenge}")
            # Возвращаем challenge как plain text (не JSON!)
            response = Response(challenge, content_type='text/plain')
            logger.info(f"📤 Отправляем ответ: {challenge}")
            return response
        
        # 2. Проверяем параметры входящего звонка от External App
        caller = request.args.get('caller')
        name = request.args.get('name')
        called = request.args.get('called')
        
        # Проверяем наличие параметров (даже если они пустые)
        has_call_params = 'caller' in request.args or 'name' in request.args or 'called' in request.args
        
        if has_call_params:
            logger.info(f"📞 Получен входящий звонок через External App")
            logger.info(f"   Звонящий: {caller or 'Unknown'}")
            logger.info(f"   Имя: {name or 'Unknown'}")
            logger.info(f"   Вызываемый номер: {called or 'Unknown'}")
            
            # Обрабатываем звонок
            call_data = {
                'caller': caller or 'Unknown',
                'name': name or 'Unknown',
                'called': called or 'Unknown',
                'source': 'external_app'
            }
            
            # Запускаем обработку звонка в отдельном потоке
            threading.Thread(target=process_call, args=(call_data,)).start()
            
            return jsonify({
                "status": "call_received",
                "message": "Call processing started",
                "caller": caller or 'Unknown',
                "name": name or 'Unknown',
                "called": called or 'Unknown'
            }), 200
        
        # 3. Если нет известных параметров
        logger.warning("❌ GET запрос без известных параметров")
        logger.warning(f"📋 Доступные параметры: {dict(request.args)}")
        return jsonify({
            "error": "Missing required parameters",
            "expected": ["hub.challenge", "caller", "name", "called"],
            "received": dict(request.args)
        }), 400
    
    # Обработка POST запросов
    elif request.method == 'POST':
        logger.info(f"📨 POST запрос на /webhook")
        
        # Логируем заголовки для отладки
        logger.debug(f"📋 Заголовки: {dict(request.headers)}")
        
        # Получаем сырые данные
        raw_data = request.get_data()
        logger.debug(f"📦 Размер данных: {len(raw_data)} байт")
        
        # 1. Проверяем пустой POST запрос для валидации webhook
        if not raw_data:
            logger.info("✅ Получен пустой POST запрос для валидации webhook")
            
            # Проверяем наличие Validation-Token в заголовках
            validation_token = request.headers.get('Validation-Token')
            if validation_token:
                logger.info(f"🔑 Возвращаем Validation-Token: {validation_token}")
                # Создаем ответ с заголовком Validation-Token
                response = make_response(jsonify({"status": "ok"}), 200)
                response.headers['Validation-Token'] = validation_token
                response.headers['Content-Type'] = 'application/json'
                return response
            else:
                logger.info("📤 Возвращаем простой OK ответ")
                return jsonify({"status": "ok"}), 200
        
        # 2. Проверка подписи webhook (делаем до парсинга JSON)
        if not _verify_webhook_signature(request):
            logger.warning("❌ Неверная подпись webhook")
            return jsonify({"error": "Invalid signature"}), 401
        
        # 3. Пытаемся распарсить JSON
        try:
            webhook_data = json.loads(raw_data.decode('utf-8'))
            logger.info(f"📋 Получено webhook событие: {json.dumps(webhook_data, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON данных: {e}")
            logger.error(f"📄 Raw data: {raw_data[:500]}")  # Логируем первые 500 символов
            return jsonify({"error": "Invalid JSON"}), 400
        
        # 4. Обработка webhook события
        event_type = webhook_data.get('eventType', 'unknown')
        uuid = webhook_data.get('uuid', 'unknown')
        logger.info(f"🔍 Тип события: {event_type}, UUID: {uuid}")
        
        # Извлекаем body из webhook payload
        body = webhook_data.get('body', {})
        
        # Явная обработка события telephony-session-event
        if event_type == 'telephony-session-event':
            logger.info("📞 Обнаружено событие telephony-session-event")
            return _handle_telephony_session(body)
        
        # Проверяем наличие telephonySessionId для telephony событий (fallback)
        if body.get('telephonySessionId'):
            logger.info(f"📞 Обрабатываем telephony событие")
            return _handle_telephony_session(body)
        else:
            logger.info(f"📋 Не telephony событие: {webhook_data.get('uuid', 'unknown')}")
            return jsonify({"status": "received"}), 200
    
    # Неподдерживаемый метод
    else:
        logger.warning(f"❌ Неподдерживаемый метод: {request.method}")
        return jsonify({"error": "Method not allowed"}), 405

def _verify_webhook_signature(request) -> bool:
    """
    ✅ Правильная проверка подписи webhook от RingCentral
    
    RingCentral использует:
    - Заголовок: X-RC-Signature
    - Алгоритм: HMAC-SHA1
    - Кодировка: Base64
    
    Args:
        request: Flask request объект
        
    Returns:
        bool: True если подпись валидна или не требуется
    """
    # Получаем подпись из заголовка RingCentral
    signature = request.headers.get('X-RC-Signature')
    if not signature:
        # Если подпись не требуется или не настроена
        logger.debug("Подпись webhook не найдена, пропускаем проверку")
        return True
    
    # Получаем секрет из конфигурации
    webhook_secret = Config.RINGCENTRAL.get('webhook_secret')
    if not webhook_secret:
        logger.debug("Webhook secret не настроен, пропускаем проверку подписи")
        return True
    
    try:
        # ✅ Правильная HMAC проверка для RingCentral
        body = request.get_data()
        expected = base64.b64encode(
            hmac.new(
                webhook_secret.encode('utf-8'), 
                body, 
                hashlib.sha1
            ).digest()
        ).decode()
        
        # Безопасное сравнение подписей
        is_valid = hmac.compare_digest(signature, expected)
        
        if is_valid:
            logger.debug("Подпись webhook валидна")
        else:
            logger.warning(f"Неверная подпись webhook. Ожидалось: {expected[:10]}..., получено: {signature[:10]}...")
            
        return is_valid
        
    except Exception as e:
        logger.error(f"Ошибка проверки подписи: {e}")
        return False

def _handle_telephony_session(session_data: Dict[str, Any]) -> Response:
    """
    Обработка telephony/sessions событий
    
    Args:
        session_data: Данные телефонной сессии из body
        
    Returns:
        Response: Flask ответ
    """
    try:
        # Извлекаем информацию о сессии
        telephony_session_id = session_data.get('telephonySessionId')
        parties = session_data.get('parties', [])
        
        logger.info(f"Обработка telephony session: {telephony_session_id}")
        
        # Находим входящий звонок
        for party in parties:
            direction = party.get('direction')
            status = party.get('status', {})
            party_id = party.get('id')
            
            logger.info(f"Обрабатываем party: direction={direction}, status={status}, party_id={party_id}")
            
            # ✅ Улучшенная логика обработки входящих звонков
            # Обрабатываем звонки в состоянии "Ringing" для автоматического ответа
            if direction == 'Inbound' and status.get('code') == 'Ringing':
                logger.info(f"🔔 Обнаружен входящий звонок в состоянии RINGING: session={telephony_session_id}, party={party_id}")
                
                # Подготавливаем данные звонка
                call_data = {
                    "callId": f"{telephony_session_id}_{party_id}",
                    "telephonySessionId": telephony_session_id,
                    "partyId": party_id,
                    "from": party.get('from', {}),
                    "to": party.get('to', {}),
                    "direction": direction,
                    "status": status,
                    "timestamp": datetime.now().isoformat(),
                    "source": "webhook"  # Явно указываем источник
                }
                
                logger.info(f"📞 Подготовлены данные звонка для автоматического ответа:")
                logger.info(f"   Session ID: {telephony_session_id}")
                logger.info(f"   Party ID: {party_id}")
                logger.info(f"   От: {party.get('from', {}).get('phoneNumber', 'Unknown')}")
                logger.info(f"   К: {party.get('to', {}).get('phoneNumber', 'Unknown')}")
                
                # Сохраняем информацию о звонке
                with call_lock:
                    active_calls[call_data["callId"]] = call_data
                
                # Обрабатываем звонок в фоновом потоке через VoiceAIEngine
                thread = threading.Thread(target=_run_engine_for_call, args=(call_data,))
                thread.daemon = True
                thread.start()
                logger.info(f"📋 Запущен VoiceAIEngine для звонка {call_data['callId']}")
                
            elif direction == 'Inbound' and status.get('code') in ['Proceeding', 'Setup', 'Alerting']:
                # Логируем входящие звонки в других состояниях без обработки
                logger.info(f"📱 Входящий звонок в состоянии {status.get('code')} (ожидаем Ringing): session={telephony_session_id}, party={party_id}")
                
            elif direction == 'Inbound' and status.get('code') in ['Answered', 'Connected']:
                # Логируем когда звонок уже отвечен
                logger.info(f"📞 Входящий звонок уже отвечен в состоянии {status.get('code')}: session={telephony_session_id}, party={party_id}")
                
            elif direction == 'Inbound' and status.get('code') in ['Disconnected', 'Gone', 'Cancelled']:
                # Логируем завершенные звонки
                logger.info(f"📞 Входящий звонок завершен в состоянии {status.get('code')}: session={telephony_session_id}, party={party_id}")
                
                # Удаляем из активных звонков
                call_id = f"{telephony_session_id}_{party_id}"
                with call_lock:
                    if call_id in active_calls:
                        del active_calls[call_id]
                        logger.info(f"🗑️ Звонок {call_id} удален из активных")
            else:
                if direction == 'Inbound':
                    logger.info(f"⏭️ Пропускаем входящий звонок со статусом {status.get('code')} (не подходит для ответа)")
                
                # Обрабатываем изменения статуса для существующих звонков
                if party_id:
                    call_id = f"{telephony_session_id}_{party_id}"
                    with call_lock:
                        if call_id in active_calls:
                            active_calls[call_id]["status"] = status
                            active_calls[call_id]["last_update"] = datetime.now().isoformat()
                            
                            # Если звонок завершен, удаляем из активных
                            if status.get('code') in ['Disconnected', 'Gone']:
                                logger.info(f"Звонок {call_id} завершен")
                                del active_calls[call_id]
        
        return jsonify({"status": "processed"}), 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки telephony session: {e}")
        return jsonify({"error": str(e)}), 500

async def _answer_and_process_call(call_data: Dict[str, Any]):
    """
    Ответить на звонок и начать обработку
    
    Args:
        call_data: Данные о звонке
    """
    try:
        telephony_session_id = call_data['telephonySessionId']
        party_id = call_data['partyId']
        call_id = call_data['callId']
        
        logger.info(f"📞 Начинаем ответ на звонок {call_id}")
        logger.info(f"🔗 Session: {telephony_session_id}, Party: {party_id}")
        
        # Отвечаем на звонок через RingCentral API
        try:
            logger.info(f"🔄 Отправляем запрос на ответ для звонка {call_id}")
            answer_response = make_request(
                'POST',
                f'/restapi/v1.0/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/answer'
            )
            logger.info(f"✅ Успешно ответили на звонок {call_id}")
            logger.info(f"📋 Ответ API: {answer_response}")
        except Exception as e:
            logger.error(f"❌ Ошибка при ответе на звонок {call_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Небольшая задержка перед запуском Voice AI
        await asyncio.sleep(1)
        
        # Передаем звонок в Voice AI Engine для обработки (выполняется всегда)
        logger.info(f"🤖 Запускаем Voice AI для звонка {call_id}")
        try:
            response = await voice_ai_engine.handle_incoming_call(call_data)
            logger.info(f"✅ Voice AI обработал звонок {call_id}: {response}")
        except Exception as e:
            logger.error(f"❌ Ошибка Voice AI для звонка {call_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
    except Exception as e:
        logger.error(f"❌ Общая ошибка при ответе на звонок: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def _run_engine_for_call(call_data: Dict[str, Any]):
    """Запустить обработку звонка в VoiceAIEngine из синхронного контекста."""
    try:
        logger.info(f"🤖 Асинхронный запуск VoiceAIEngine: callId={call_data.get('callId')}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            normalized = dict(call_data)
            # Нормализуем ключи для engine
            if 'sessionId' not in normalized and 'telephonySessionId' in normalized:
                normalized['sessionId'] = normalized['telephonySessionId']
            loop.run_until_complete(voice_ai_engine.handle_incoming_call(normalized))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска VoiceAIEngine: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

@app.route('/calls', methods=['GET'])
def get_active_calls():
    """Получить список активных звонков"""
    try:
        with call_lock:
            calls_list = list(active_calls.values())
        return jsonify({
            "total": len(calls_list),
            "calls": calls_list
        }), 200
    except Exception as e:
        logger.error(f"Ошибка получения списка звонков: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/call/<call_id>/transfer', methods=['POST'])
def transfer_call(call_id: str):
    """
    Перевести звонок на другой номер
    
    Body:
        {
            "transferTo": "+1234567890",
            "transferType": "blind" // или "attended"
        }
    """
    try:
        data = request.get_json()
        transfer_to = data.get('transferTo')
        transfer_type = data.get('transferType', 'blind')
        
        if not transfer_to:
            return jsonify({"error": "transferTo is required"}), 400
        
        # Находим звонок
        with call_lock:
            call_data = active_calls.get(call_id)
        
        if not call_data:
            return jsonify({"error": "Call not found"}), 404
        
        # Переводим звонок через RingCentral API
        try:
            transfer_data = {
                "phoneNumber": transfer_to,
                "transferType": transfer_type
            }
            
            make_request(
                'POST',
                f'/restapi/v1.0/account/~/extension/~/telephony/sessions/{call_data["telephonySessionId"]}/parties/{call_data["partyId"]}/transfer',
                transfer_data
            )
            
            return jsonify({"status": "transferred"}), 200
            
        except Exception as e:
            logger.error(f"Ошибка перевода звонка: {e}")
            return jsonify({"error": "Transfer failed"}), 500
            
    except Exception as e:
        logger.error(f"Ошибка перевода звонка: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/call/<call_id>/hangup', methods=['DELETE'])
def hangup_call(call_id: str):
    """Завершить звонок"""
    try:
        # Находим звонок
        with call_lock:
            call_data = active_calls.get(call_id)
        
        if not call_data:
            return jsonify({"error": "Call not found"}), 404
        
        # Завершаем звонок через RingCentral API
        try:
            make_request(
                'DELETE',
                f'/restapi/v1.0/account/~/extension/~/telephony/sessions/{call_data["telephonySessionId"]}/parties/{call_data["partyId"]}'
            )
            
            # Удаляем из активных звонков
            with call_lock:
                if call_id in active_calls:
                    del active_calls[call_id]
            return jsonify({"status": "hangup"}), 200
            
        except Exception as e:
            logger.error(f"Ошибка завершения звонка: {e}")
            return jsonify({"error": "Hangup failed"}), 500
            
    except Exception as e:
        logger.error(f"Ошибка завершения звонка: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/subscription/create', methods=['POST'])
def create_subscription():
    """Создать webhook подписку вручную"""
    try:
        # Создаем подписку
        async def do_create_subscription():
            return await _create_webhook_subscription()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        subscription_info = loop.run_until_complete(do_create_subscription())
        loop.close()
        
        if subscription_info:
            global subscription_id
            subscription_id = subscription_info['id']
            return jsonify(subscription_info), 200
        else:
            return jsonify({"error": "Failed to create subscription"}), 500
            
    except Exception as e:
        logger.error(f"Ошибка создания подписки: {e}")
        return jsonify({"error": str(e)}), 500

async def _cleanup_old_subscriptions():
    """Очистка старых подписок на тот же webhook URL"""
    try:
        from ringcentral_auth import make_request
        
        # Получаем все подписки
        response = make_request('GET', '/restapi/v1.0/subscription')
        if not response:
            return
        
        subscriptions = response.get('records', [])
        target_url = Config.RINGCENTRAL['webhook_url']
        
        # Находим подписки на тот же URL
        old_subscriptions = []
        for sub in subscriptions:
            sub_url = sub.get('deliveryMode', {}).get('address')
            if sub_url == target_url:
                old_subscriptions.append(sub)
        
        if len(old_subscriptions) > 1:
            logger.info(f"🧹 Найдено {len(old_subscriptions)} старых подписок, удаляем...")
            
            # Сортируем по времени создания (новые первыми)
            old_subscriptions.sort(key=lambda x: x.get('creationTime', ''), reverse=True)
            
            # Удаляем все кроме самой новой
            for sub in old_subscriptions[1:]:
                sub_id = sub.get('id')
                logger.info(f"🗑️  Удаляем старую подписку: {sub_id}")
                try:
                    make_request('DELETE', f'/restapi/v1.0/subscription/{sub_id}')
                    logger.info(f"✅ Подписка {sub_id} удалена")
                except Exception as e:
                    logger.warning(f"⚠️  Не удалось удалить подписку {sub_id}: {e}")
        elif len(old_subscriptions) == 1:
            logger.info("✅ Найдена одна подписка, оставляем")
        else:
            logger.info("📋 Старых подписок не найдено")
            
    except Exception as e:
        logger.error(f"Ошибка очистки старых подписок: {e}")

async def _create_webhook_subscription():
    """Создать webhook подписку для telephony/sessions событий"""
    try:
        from ringcentral_auth import make_request
        
        # Сначала очищаем старые подписки
        await _cleanup_old_subscriptions()
        
        # Проверяем, есть ли уже активная подписка
        response = make_request('GET', '/restapi/v1.0/subscription')
        if response:
            subscriptions = response.get('records', [])
            target_url = Config.RINGCENTRAL['webhook_url']
            
            # Ищем активную подписку на тот же URL
            for sub in subscriptions:
                sub_url = sub.get('deliveryMode', {}).get('address')
                if sub_url == target_url and sub.get('status') == 'Active':
                    logger.info(f"✅ Найдена активная подписка: {sub.get('id')}")
                    return sub
        
        # Если активной подписки нет, создаем новую
        logger.info(f"Создаем новую webhook подписку на {Config.RINGCENTRAL['webhook_url']}")
        
        # ✅ Правильный фильтр событий согласно документации RingCentral
        # Wildcard фильтры не поддерживаются, используем только базовый
        event_filters = [
            '/restapi/v1.0/account/~/extension/~/telephony/sessions',
            '/restapi/v1.0/account/~/extension/~/presence'
        ]
        
        # ✅ Рекомендуемая структура delivery_mode для RingCentral
        delivery_mode = {
            'transportType': 'WebHook',
            'address': Config.RINGCENTRAL['webhook_url'],
            'encryption': False  # Или True с encryptionKey если нужна шифрация
        }
        
        # Подготавливаем данные для подписки
        subscription_data = {
            'eventFilters': event_filters,
            'deliveryMode': delivery_mode,
            'expiresIn': 86400  # 24 часа
        }
        
        logger.info(f"📋 Данные подписки: {json.dumps(subscription_data, indent=2)}")
        
        # Создаем подписку через новую систему авторизации
        subscription_info = make_request('POST', '/restapi/v1.0/subscription', subscription_data)
        
        logger.info(f"Webhook подписка создана: {subscription_info['id']}")
        return subscription_info
        
    except Exception as e:
        logger.error(f"Ошибка создания webhook подписки: {e}")
        return None

async def initialize_ringcentral():
    """Инициализация RingCentral и создание подписки"""
    global subscription_id
    
    try:
        logger.info("🚀 Starting Voice AI System...")
        
        # Инициализация RingCentral с новой системой авторизации
        from ringcentral_auth import authenticate, get_auth_status
        if authenticate():
            status = get_auth_status()
            logger.info(f"📞 RingCentral авторизован: {status['auth_method']}")
            logger.info("✅ RingCentral connection test passed")
        else:
            logger.warning("⚠️ RingCentral connection test failed")
        
        # Создаем webhook подписку
        subscription_info = await _create_webhook_subscription()
        if subscription_info:
            subscription_id = subscription_info['id']
            logger.info(f"Webhook подписка создана: {subscription_id}")
        else:
            logger.warning("Не удалось создать webhook подписку")
            
    except Exception as e:
        logger.error(f"💥 Application startup failed: {e}")
        raise

@app.route('/api/handle-webphone-call', methods=['POST'])
async def handle_webphone_call():
    """
    Обработка звонков от WebPhone Bridge
    
    Получает данные о новом звонке от JavaScript WebPhone
    и инициализирует AI обработку
    """
    try:
        logger.info("🌐 Получен запрос от WebPhone Bridge")
        
        # Получаем данные звонка
        call_data = request.get_json()
        if not call_data:
            logger.error("❌ Нет данных в запросе")
            return jsonify({"error": "No call data provided"}), 400
        
        logger.info(f"📞 Данные звонка от WebPhone:")
        logger.info(f"   Call ID: {call_data.get('callId')}")
        logger.info(f"   From: {call_data.get('from')}")
        logger.info(f"   To: {call_data.get('to')}")
        logger.info(f"   Session ID: {call_data.get('sessionId')}")
        
        # Обрабатываем звонок через audio stream handler
        response = await audio_stream_handler.handle_webphone_call(call_data)
        
        logger.info(f"✅ Звонок обработан: {response.get('status')}")
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки WebPhone звонка: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

@app.route('/api/webphone/status', methods=['GET'])
def webphone_status():
    """Получить статус WebPhone интеграции"""
    try:
        active_calls = audio_stream_handler.get_active_calls()
        
        return jsonify({
            "status": "operational",
            "websocket_running": audio_stream_handler.is_running,
            "active_calls": len(active_calls),
            "calls": active_calls
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статуса: {e}")
        return jsonify({"error": str(e)}), 500

def start_server():
    """Запуск webhook сервера"""
    try:
        logger.info(f"Запуск webhook сервера на {Config.WEBHOOK['host']}:{Config.WEBHOOK['port']}")
        
        # Инициализируем RingCentral в отдельном потоке
        def init_ringcentral():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(initialize_ringcentral())
            loop.close()
        
        init_thread = threading.Thread(target=init_ringcentral)
        init_thread.daemon = True
        init_thread.start()
        
        # Инициализируем Voice AI engine
        logger.info("Инициализация Voice AI engine...")
        
        # Запускаем WebSocket сервер для аудио стриминга
        def start_audio_ws_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(audio_stream_handler.start_websocket_server(8080))
            loop.run_forever()
        
        ws_thread = threading.Thread(target=start_audio_ws_server)
        ws_thread.daemon = True
        ws_thread.start()
        logger.info("✅ WebSocket сервер для аудио запущен")
        
        # Запускаем сервер
        app.run(
            host=Config.WEBHOOK["host"],
            port=Config.WEBHOOK["port"],
            debug=Config.WEBHOOK["debug"],
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"Ошибка запуска webhook сервера: {e}")
        raise

@app.errorhandler(404)
def not_found(error):
    """Обработка 404 ошибок"""
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Обработка 500 ошибок"""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

@app.route('/call', methods=['POST'])
def handle_incoming_call():
    """Обработка входящих звонков через переадресацию"""
    try:
        logger.info("📞 Получен входящий звонок через переадресацию")
        
        # Получаем данные звонка
        call_data = request.get_json()
        if not call_data:
            logger.error("Нет данных о звонке")
            return jsonify({"error": "No call data"}), 400
        
        logger.info(f"Данные звонка: {json.dumps(call_data, indent=2)}")
        
        # Извлекаем информацию о звонке
        from_number = call_data.get('from', {}).get('phoneNumber', 'Unknown')
        to_number = call_data.get('to', {}).get('phoneNumber', 'Unknown')
        
        logger.info(f"📞 Звонок от {from_number} на {to_number}")
        
        # Обрабатываем звонок в фоновом потоке
        thread = threading.Thread(target=process_call, args=(call_data,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "received",
            "message": "Call processed",
            "from": from_number,
            "to": to_number
        }), 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки входящего звонка: {e}")
        return jsonify({"error": str(e)}), 500

def answer_call_automatically(session_id: str, party_id: str, caller_info: Dict[str, Any]) -> bool:
    """
    Автоматически принять звонок через RingCentral Call Control API
    
    Args:
        session_id: ID телефонной сессии
        party_id: ID участника звонка
        caller_info: Информация о звонящем
        
    Returns:
        bool: True если звонок успешно принят
    """
    try:
        logger.info(f"🔄 Попытка автоматически ответить на звонок: session={session_id}, party={party_id}")
        
        # ✅ Правильный endpoint для ответа на звонок
        # Документация: https://developers.ringcentral.com/api-reference/Call-Control/answerCall
        response = make_request(
            'POST',
            f'/restapi/v1.0/account/~/extension/~/telephony/sessions/{session_id}/parties/{party_id}/answer'
        )
        
        logger.info(f"✅ Звонок успешно принят! Response: {response}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при автоматическом ответе на звонок: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def play_audio_to_call(session_id: str, party_id: str, audio_data: bytes) -> bool:
    """
    Воспроизвести audio в активном звонке через RingCentral Call Control API
    
    Args:
        session_id: ID телефонной сессии
        party_id: ID участника звонка
        audio_data: Аудио данные для воспроизведения
        
    Returns:
        bool: True если аудио успешно воспроизведено
    """
    try:
        logger.info(f"🔊 Попытка воспроизвести аудио в звонке: session={session_id}, party={party_id}")
        
        # ✅ Правильный endpoint для воспроизведения аудио
        # Документация: https://developers.ringcentral.com/api-reference/Call-Control/playAudio
        # RingCentral поддерживает только base64 encoded audio data
        
        import base64
        
        # Кодируем аудио в base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        # Воспроизводим аудио в звонке
        play_data = {
            'audioData': audio_base64,
            'playMode': 'play'
        }
        
        logger.info(f"📤 Отправляем аудио данные: {len(audio_base64)} символов base64")
        play_response = make_request(
            'POST',
            f'/restapi/v1.0/account/~/extension/~/telephony/sessions/{session_id}/parties/{party_id}/play',
            play_data
        )
        
        logger.info(f"✅ Аудио успешно воспроизведено в звонке!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при воспроизведении аудио: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def start_ai_conversation(call_data: Dict[str, Any]):
    """
    Запустить AI разговор с звонящим
    
    Args:
        call_data: Данные о звонке
    """
    try:
        session_id = call_data['telephonySessionId']
        party_id = call_data['partyId']
        caller_number = call_data.get('from', {}).get('phoneNumber', 'Unknown')
        
        logger.info(f"🤖 Запуск AI разговора с {caller_number}")
        
        # Генерируем приветствие
        greeting_text = "Hi there! Welcome to Prime Cargo Logistics! I'm your AI assistant, and I'm here to help you with tracking shipments, scheduling pickups, or any other logistics needs. How can I assist you today?"
        
        # ✅ Правильная обработка асинхронности в потоке
        def generate_and_play_audio():
            try:
                # Создаем новый event loop для этого потока
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Генерируем TTS аудио
                    audio_data = loop.run_until_complete(async_synthesize(greeting_text))
                    logger.info(f"✅ Приветствие сгенерировано: {len(audio_data)} байт")
                    
                    # Сохраняем аудио для отладки
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"recordings/greeting_{caller_number}_{timestamp}.wav"
                    os.makedirs("recordings", exist_ok=True)
                    with open(filename, "wb") as f:
                        f.write(audio_data)
                    logger.info(f"💾 Аудио сохранено в {filename}")
                    
                    # Воспроизводим аудио в звонке
                    if play_audio_to_call(session_id, party_id, audio_data):
                        logger.info("✅ Приветствие воспроизведено, ожидаем ответ пользователя...")
                        
                        # TODO: Здесь нужно реализовать:
                        # 1. Получение audio stream от пользователя
                        # 2. Распознавание речи (STT)
                        # 3. Обработка через LLM
                        # 4. Генерация ответа (TTS)
                        # 5. Воспроизведение ответа
                        
                    else:
                        logger.error("❌ Не удалось воспроизвести приветствие")
                        
                finally:
                    loop.close()
                    
            except Exception as e:
                logger.error(f"❌ Ошибка в generate_and_play_audio: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Запускаем в отдельном потоке
        import threading
        thread = threading.Thread(target=generate_and_play_audio)
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        logger.error(f"❌ Ошибка AI разговора: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def process_call(call_data: Dict[str, Any]):
    """
    Обработка входящего звонка
    
    Args:
        call_data: Данные о звонке (может быть от webhook или External App)
    """
    try:
        logger.info(f"📞 Начинаем обработку звонка: {call_data}")
        
        # Определяем источник звонка
        source = call_data.get('source', 'webhook')
        
        if source == 'external_app':
            # Звонок от External App (GET запрос с параметрами)
            caller = call_data.get('caller', 'Unknown')
            name = call_data.get('name', 'Unknown')
            called = call_data.get('called', 'Unknown')
            
            logger.info(f"📞 Звонок от External App:")
            logger.info(f"   Звонящий: {caller}")
            logger.info(f"   Имя: {name}")
            logger.info(f"   Вызываемый номер: {called}")
            
            # Для External App звонков мы не можем автоматически ответить
            # так как у нас нет telephony session ID
            logger.info("⚠️ External App звонок - автоматический ответ недоступен")
            
            # Генерируем приветствие для демонстрации
            greeting = f"Hi {name}! Welcome to Prime Cargo Logistics! I'm here to help you with anything you need today! How can I assist you?"
            
            # ✅ Правильная обработка асинхронности для External App
            def generate_external_audio():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        audio_file = loop.run_until_complete(async_synthesize(greeting))
                        logger.info(f"✅ Приветствие сгенерировано: {len(audio_file)} байт аудио")
                        
                        # Сохраняем аудио в файл для демонстрации
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"recordings/external_call_{timestamp}.wav"
                        os.makedirs("recordings", exist_ok=True)
                        with open(filename, "wb") as f:
                            f.write(audio_file)
                        logger.info(f"💾 Аудио сохранено в {filename}")
                        
                    finally:
                        loop.close()
                except Exception as e:
                    logger.error(f"❌ Ошибка генерации аудио для External App: {e}")
            
            # Запускаем в отдельном потоке
            import threading
            thread = threading.Thread(target=generate_external_audio)
            thread.daemon = True
            thread.start()
            
        else:
            # Звонок от webhook (есть telephony session ID)
            telephony_session_id = call_data.get('telephonySessionId')
            party_id = call_data.get('partyId')
            caller_info = call_data.get('from', {})
            
            logger.info(f"📞 Звонок от webhook:")
            logger.info(f"   Session ID: {telephony_session_id}")
            logger.info(f"   Party ID: {party_id}")
            logger.info(f"   От: {caller_info.get('phoneNumber', 'Unknown')}")
            
            # 1. Автоматически отвечаем на звонок
            if telephony_session_id and party_id:
                if answer_call_automatically(telephony_session_id, party_id, caller_info):
                    logger.info("✅ Звонок принят, запускаем AI разговор...")
                    
                    # 2. Запускаем AI разговор
                    start_ai_conversation(call_data)
                    return
                else:
                    logger.error("❌ Не удалось автоматически ответить на звонок")
            else:
                logger.error("❌ Отсутствуют telephonySessionId или partyId")
        
        logger.info("✅ Обработка звонка завершена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки звонка: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == '__main__':
    start_server()