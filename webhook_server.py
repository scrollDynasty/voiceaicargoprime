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
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import threading
import time

from voice_ai_engine import voice_ai_engine
from config import Config
from ringcentral_auth import make_request

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

# Глобальные переменные
active_calls = {}
call_lock = threading.Lock()
subscription_id = None

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

@app.route('/webhook', methods=['GET', 'POST'])
def ringcentral_webhook():
    # Отключаем автоматический парсинг JSON для этого endpoint
    if request.method == 'POST':
        # Проверяем есть ли данные
        if not request.get_data():
            logger.info("Получен пустой POST запрос для валидации webhook")
            return jsonify({"status": "ok"}), 200
        
        # Если есть данные, обрабатываем их вручную
        try:
            raw_data = request.get_data(as_text=True)
            if raw_data:
                webhook_data = json.loads(raw_data)
            else:
                return jsonify({"status": "ok"}), 200
        except json.JSONDecodeError:
            logger.error("Ошибка парсинга JSON данных")
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Проверка подписи webhook
        if not _verify_webhook_signature(request):
            logger.warning("Неверная подпись webhook")
            return jsonify({"error": "Invalid signature"}), 401
        
        logger.info(f"Получено webhook событие: {json.dumps(webhook_data, indent=2)}")
        
        # Извлекаем body из webhook payload
        body = webhook_data.get('body', {})
        
        # Проверяем наличие telephonySessionId для telephony событий
        if body.get('telephonySessionId'):
            return _handle_telephony_session(body)
        else:
            logger.info(f"Не telephony событие: {webhook_data.get('uuid', 'unknown')}")
            return jsonify({"status": "received"}), 200
        # Обработка GET запросов для валидации
        if request.method == 'GET':
            challenge = request.args.get('hub.challenge')
            if challenge:
                logger.info(f"Получен validation challenge: {challenge}")
                return Response(challenge, content_type='text/plain')
            else:
                logger.warning("GET запрос без hub.challenge параметра")
                return jsonify({"error": "Missing hub.challenge"}), 400

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
        bool: True если подпись валидна
    """
    # Получаем подпись из заголовка RingCentral
    signature = request.headers.get('X-RC-Signature')
    if not signature:
        # Если подпись не требуется или не настроена
        logger.info("Подпись webhook не найдена, пропускаем проверку")
        return True
    
    # Получаем секрет из конфигурации
    webhook_secret = Config.RINGCENTRAL.get('webhook_secret')
    if not webhook_secret:
        logger.warning("Webhook secret не настроен")
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
        return hmac.compare_digest(signature, expected)
        
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
            
            # Проверяем входящий звонок в состоянии "Proceeding"
            if direction == 'Inbound' and status.get('code') == 'Proceeding':
                logger.info(f"Обнаружен входящий звонок: session={telephony_session_id}, party={party_id}")
                
                # Подготавливаем данные звонка
                call_data = {
                    "callId": f"{telephony_session_id}_{party_id}",
                    "telephonySessionId": telephony_session_id,
                    "partyId": party_id,
                    "from": party.get('from', {}),
                    "to": party.get('to', {}),
                    "direction": direction,
                    "status": status,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Сохраняем информацию о звонке
                with call_lock:
                    active_calls[call_data["callId"]] = call_data
                
                # Обрабатываем звонок асинхронно
                def process_incoming_call():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        # Автоматически отвечаем на звонок
                        loop.run_until_complete(
                            _answer_and_process_call(call_data)
                        )
                    except Exception as e:
                        logger.error(f"Ошибка обработки входящего звонка: {e}")
                    finally:
                        loop.close()
                
                # Запускаем обработку в фоновом потоке
                thread = threading.Thread(target=process_incoming_call)
                thread.daemon = True
                thread.start()
                
            # Обрабатываем изменения статуса
            elif party_id:
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
        
        # Отвечаем на звонок через RingCentral API
        try:
            make_request(
                'POST',
                f'/restapi/v1.0/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/answer'
            )
            logger.info(f"Успешно ответили на звонок {call_data['callId']}")
        except Exception as e:
            logger.error(f"Ошибка при ответе на звонок: {e}")
            
            # Передаем звонок в Voice AI Engine для обработки
            response = await voice_ai_engine.handle_incoming_call(call_data)
            logger.info(f"Voice AI обработал звонок: {response}")
            
    except Exception as e:
        logger.error(f"Ошибка при ответе на звонок: {e}")

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
            make_ringcentral_request(
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

async def _create_webhook_subscription():
    """Создать webhook подписку для telephony/sessions событий"""
    try:
        # Фильтры событий для telephony sessions
        event_filters = [
            '/restapi/v1.0/account/~/extension/~/telephony/sessions'
        ]
        
        # ✅ Рекомендуемая структура delivery_mode для RingCentral
        delivery_mode = {
            'transportType': 'WebHook',
            'address': Config.RINGCENTRAL['webhook_url'],
            'encryption': False  # Или True с encryptionKey если нужна шифрация
        }
        
        logger.info(f"Создаем webhook подписку на {Config.RINGCENTRAL['webhook_url']}")
        
        # Подготавливаем данные для подписки
        subscription_data = {
            'eventFilters': event_filters,
            'deliveryMode': delivery_mode,
            'expiresIn': 86400  # 24 часа
        }
        
        # Создаем подписку через новую систему авторизации
        from ringcentral_auth import make_request
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

if __name__ == '__main__':
    start_server()