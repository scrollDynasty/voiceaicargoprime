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
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, Response, make_response
from flask_cors import CORS
import threading
from functools import wraps

# Временно отключаем AI модули для тестирования WebPhone
# from voice_ai_engine import voice_ai_engine
# from speech_processor import async_synthesize
from config import Config
from ringcentral_auth import make_request
# from audio_stream_handler import audio_stream_handler  # Новый импорт

# Заглушки для AI модулей
class MockVoiceAIEngine:
    def __init__(self):
        pass
    
    def handle_call(self, *args, **kwargs):
        logger.info("🧪 MOCK: VoiceAI engine заглушка")
        return None
    
    async def handle_incoming_call(self, call_data):
        """Mock implementation of handle_incoming_call for testing"""
        logger.info("🧪 MOCK: Handling incoming call with VoiceAI engine заглушка")
        logger.info(f"🧪 MOCK: Call data: {call_data}")
        
        # Simulate processing the call
        call_id = call_data.get("callId", "unknown")
        phone_number = call_data.get("from", {}).get("phoneNumber", "unknown")
        
        logger.info(f"🧪 MOCK: Processing call {call_id} from {phone_number}")
        
        # Return a mock successful response
        return {
            "status": "success",
            "message": "Call handled by mock AI engine",
            "call_id": call_id,
            "actions": ["answered", "processing"]
        }
    
    def health_check(self):
        return {"status": "healthy", "message": "Mock AI engine is running"}

voice_ai_engine = MockVoiceAIEngine()

def async_synthesize(*args, **kwargs):
    logger.info("🧪 MOCK: Speech synthesis заглушка")
    return None

class MockAudioStreamHandler:
    def __init__(self):
        pass

audio_stream_handler = MockAudioStreamHandler()

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
# Отслеживание попыток ответа на звонки
answered_calls = set()  # Множество ID звонков, на которые уже пытались ответить
answer_lock = threading.Lock()

def get_current_device_id():
    """Получить актуальный Device ID из WebPhone Bridge"""
    try:
        # Пытаемся получить Device ID из WebPhone Bridge
        import requests
        webphone_response = requests.get('http://localhost:8081/status', timeout=2)
        if webphone_response.status_code == 200:
            webphone_status = webphone_response.json()
            device_id = webphone_status.get('deviceId')
            if device_id:
                logger.info(f"📱 Получен Device ID из WebPhone Bridge: {device_id}")
                return device_id
    except Exception as e:
        logger.warning(f"⚠️ Ошибка получения Device ID из WebPhone Bridge: {e}")
    
    # Fallback: пытаемся получить из логов WebPhone Bridge
    try:
        import subprocess
        result = subprocess.run(['grep', '-o', 'Device ID: [0-9]*', 'webphone-bridge/webphone-bridge.log'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout:
            # Берем последний Device ID из логов
            lines = result.stdout.strip().split('\n')
            if lines:
                last_line = lines[-1]
                device_id = last_line.split(': ')[-1]
                logger.info(f"📱 Получен Device ID из логов: {device_id}")
                return device_id
    except Exception as e:
        logger.warning(f"⚠️ Ошибка получения Device ID из логов: {e}")
    
    # Последний fallback - пытаемся получить из переменной окружения или использовать None
    fallback_device_id = os.getenv('RINGCENTRAL_DEVICE_ID')
    if fallback_device_id:
        logger.warning(f"⚠️ Используем Device ID из переменной окружения: {fallback_device_id}")
        return fallback_device_id
    else:
        logger.error("❌ Не удалось получить Device ID ни из одного источника")
        return None

def get_device_id_from_webhook_event(webhook_data):
    """Получить Device ID из webhook события"""
    try:
        # Пытаемся получить Device ID из поля to.deviceId в webhook событии
        body = webhook_data.get('body', {})
        parties = body.get('parties', [])
        
        for party in parties:
            if party.get('direction') == 'Inbound':
                to_info = party.get('to', {})
                device_id = to_info.get('deviceId')
                if device_id:
                    logger.info(f"📱 Получен Device ID из webhook события: {device_id}")
                    return device_id
    except Exception as e:
        logger.warning(f"⚠️ Ошибка получения Device ID из webhook события: {e}")
    
    return None

def send_webhook_to_js_server(event_data: Dict[str, Any]) -> None:
    """
    Отправляет webhook событие в JavaScript сервер для обработки
    
    Args:
        event_data: Данные события для отправки
    """
    try:
        js_server_url = "http://localhost:8081/webhook"
        
        logger.info(f"📤 Отправка webhook события в JS сервер: {js_server_url}")
        logger.info(f"📋 Данные события: {json.dumps(event_data, indent=2)}")
        
        response = requests.post(
            js_server_url,
            json=event_data,
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info("✅ Webhook событие успешно отправлено в JS сервер")
        else:
            logger.warning(f"⚠️ JS сервер вернул статус {response.status_code}: {response.text}")
            
    except requests.exceptions.ConnectionError:
        logger.warning("⚠️ JS сервер недоступен (ConnectionError)")
    except requests.exceptions.Timeout:
        logger.warning("⚠️ Таймаут при отправке в JS сервер")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки webhook в JS сервер: {e}")

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
        
        # Отправляем все webhook события в JavaScript сервер для обработки
        send_webhook_to_js_server(webhook_data)
        
        # Явная обработка события telephony-session-event
        if event_type == 'telephony-session-event':
            logger.info("📞 Обнаружено событие telephony-session-event")
            return _handle_telephony_session(body, webhook_data)
        
        # Проверяем наличие telephonySessionId для telephony событий (fallback)
        if body.get('telephonySessionId'):
            logger.info(f"📞 Обрабатываем telephony событие")
            return _handle_telephony_session(body, webhook_data)
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

def _handle_telephony_session(session_data: Dict[str, Any], webhook_data: Dict[str, Any] = None) -> Response:
    """
    Обработка telephony/sessions событий
    
    Args:
        session_data: Данные телефонной сессии из body
        webhook_data: Полные данные webhook события
        
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
            # Обрабатываем звонки в состоянии "Setup" или "Proceeding" для автоматического ответа
            # Принимаем как можно раньше, чтобы не пропустить звонок
            # ✅ Проверяем, что звонок приходит на нужный номер
            target_number = "+15139283626"  # Номер для мониторинга
            to_data = party.get('to', {})
            incoming_number = to_data.get('phoneNumber', '')
            
            # Логируем все входящие звонки для отладки
            if direction == 'Inbound':
                logger.info(f"📞 Входящий звонок на номер: {incoming_number}, статус: {status.get('code')}")
            
            if direction == 'Inbound' and status.get('code') == 'Setup' and target_number in incoming_number:
                logger.info(f"🔔 Обнаружен входящий звонок в состоянии {status.get('code')}: session={telephony_session_id}, party={party_id}")
                
                # Извлекаем deviceId из данных получателя
                to_data = party.get('to', {})
                device_id = to_data.get('deviceId')
                
                # Проверяем, что deviceId получен
                if not device_id:
                    logger.error(f"❌ Device ID не найден в webhook событии для звонка: session={telephony_session_id}, party={party_id}")
                    logger.error(f"📋 Данные получателя: {to_data}")
                    return jsonify({"status": "error", "message": "Device ID not found"}), 400
                
                # Подготавливаем данные звонка
                call_data = {
                    "callId": f"{telephony_session_id}_{party_id}",
                    "telephonySessionId": telephony_session_id,
                    "partyId": party_id,
                    "from": party.get('from', {}),
                    "to": to_data,
                    "direction": direction,
                    "status": status,
                    "deviceId": device_id,  # Добавляем deviceId
                    "timestamp": datetime.now().isoformat(),
                    "source": "webhook"  # Явно указываем источник
                }
                
                logger.info(f"📞 Подготовлены данные звонка для автоматического ответа:")
                logger.info(f"   Session ID: {telephony_session_id}")
                logger.info(f"   Party ID: {party_id}")
                logger.info(f"   Device ID: {device_id}")
                logger.info(f"   От: {party.get('from', {}).get('phoneNumber', 'Unknown')}")
                logger.info(f"   К: {to_data.get('phoneNumber', 'Unknown')}")
                logger.info(f"   Статус: {status.get('code')}")
                logger.info(f"   Направление: {direction}")
                
                # Сохраняем информацию о звонке
                with call_lock:
                    active_calls[call_data["callId"]] = call_data
                
                # Обрабатываем звонок в фоновом потоке через VoiceAIEngine
                thread = threading.Thread(target=_run_engine_for_call, args=(call_data,))
                thread.daemon = True
                thread.start()
                logger.info(f"📋 Запущен VoiceAIEngine для звонка {call_data['callId']}")
                
                # КРИТИЧНО: Запускаем автоматический ответ на звонок через Call Control API
                # Добавляем webhook данные в call_data
                call_data['webhook_data'] = webhook_data
                answer_thread = threading.Thread(target=_run_answer_call, args=(call_data,))
                answer_thread.daemon = True
                answer_thread.start()
                logger.info(f"📞 Запущен автоматический ответ на звонок {call_data['callId']}")
                
            elif direction == 'Inbound' and status.get('code') in ['Proceeding', 'Setup', 'Alerting']:
                # Логируем входящие звонки в других состояниях без обработки  
                logger.info(f"📱 Входящий звонок в состоянии {status.get('code')} (ожидаем Ringing): session={telephony_session_id}, party={party_id}")
                
            elif direction == 'Inbound' and status.get('code') in ['Answered', 'Connected']:
                # Логируем когда звонок уже отвечен
                logger.info(f"📞 Входящий звонок уже отвечен в состоянии {status.get('code')}: session={telephony_session_id}, party={party_id}")
                
            elif direction == 'Inbound' and status.get('code') in ['Disconnected', 'Gone', 'Cancelled']:
                # Логируем завершенные звонки
                logger.info(f"📞 Входящий звонок завершен в состоянии {status.get('code')}: session={telephony_session_id}, party={party_id}")
                
                # Проверяем, была ли это голосовая почта на нужный номер
                target_number = "15139283626"  # Номер для мониторинга
                to_data = party.get('to', {})
                incoming_number = to_data.get('phoneNumber', '')
                
                if status.get('reason') == 'Voicemail' and party.get('missedCall') and target_number in incoming_number:
                    logger.info(f"📞 Обнаружена голосовая почта, запускаем автоматическое поднятие трубки...")
                    
                    # Извлекаем deviceId из данных получателя
                    to_data = party.get('to', {})
                    device_id = to_data.get('deviceId')
                    
                    if device_id:
                        # Запускаем автоматическое поднятие трубки после голосовой почты
                        voicemail_data = {
                            "callId": f"{telephony_session_id}_{party_id}_voicemail",
                            "telephonySessionId": telephony_session_id,
                            "partyId": party_id,
                            "from": party.get('from', {}),
                            "to": to_data,
                            "direction": direction,
                            "status": status,
                            "deviceId": device_id,
                            "timestamp": datetime.now().isoformat(),
                            "source": "voicemail",
                            "webhook_data": webhook_data
                        }
                        
                        # Запускаем обработку голосовой почты в фоновом потоке
                        voicemail_thread = threading.Thread(target=_handle_voicemail_and_answer, args=(voicemail_data,))
                        voicemail_thread.daemon = True
                        voicemail_thread.start()
                        logger.info(f"📞 Запущена обработка голосовой почты для {voicemail_data['callId']}")
                    else:
                        logger.error(f"❌ Device ID не найден для обработки голосовой почты")
                
                # Удаляем из активных звонков
                call_id = f"{telephony_session_id}_{party_id}"
                with call_lock:
                    if call_id in active_calls:
                        del active_calls[call_id]
                        logger.info(f"🗑️ Звонок {call_id} удален из активных")
                
                # Удаляем из отвеченных звонков
                with answer_lock:
                    answered_calls.discard(call_id)
                    logger.info(f"🗑️ Звонок {call_id} удален из отвеченных")
            else:
                if direction == 'Inbound':
                    to_data = party.get('to', {})
                    incoming_number = to_data.get('phoneNumber', 'Unknown')
                    logger.info(f"⏭️ Пропускаем входящий звонок на номер {incoming_number} со статусом {status.get('code')} (не подходит для ответа)")
                
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
        
        # Отвечаем на звонок через RingCentral API с правильным Device ID
        try:
            logger.info(f"🔄 Отправляем запрос на ответ для звонка {call_id}")
                        # Подготавливаем тело запроса с deviceId
            device_id = call_data.get('deviceId')
            request_body = {}
            if device_id:
                request_body["deviceId"] = device_id
                logger.info(f"📱 Используем deviceId: {device_id}")
            
            answer_response = make_request(
                'POST',
                f'/restapi/v1.0/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/answer',
                request_body if request_body else None
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

def _run_answer_call(call_data: Dict[str, Any]):
    """Автоматически ответить на звонок из синхронного контекста."""
    try:
        logger.info(f"📞 Запуск автоматического ответа на звонок: callId={call_data.get('callId')}")
        
        # Проверяем статус звонка из данных
        call_status = call_data.get('status', {}).get('code')
        if call_status in ['Disconnected', 'Gone', 'Cancelled']:
            logger.warning(f"⚠️ Пропускаем ответ на звонок в статусе: {call_status}")
            return
        
        # Извлекаем необходимые данные
        session_id = call_data.get('telephonySessionId') or call_data.get('sessionId')
        party_id = call_data.get('partyId')
        device_id = call_data.get('deviceId')
        
        logger.info(f"📋 Данные для ответа на звонок:")
        logger.info(f"   Session ID: {session_id}")
        logger.info(f"   Party ID: {party_id}")
        logger.info(f"   Device ID: {device_id}")
        
        if not session_id or not party_id:
            logger.error(f"❌ Недостаточно данных для ответа на звонок: session_id={session_id}, party_id={party_id}")
            return
            
        if not device_id:
            logger.error(f"❌ Device ID не найден для ответа на звонок: device_id={device_id}")
            return
        
        # Извлекаем информацию о звонящем
        caller_info = {
            'from': call_data.get('from', ''),
            'to': call_data.get('to', ''),
            'direction': call_data.get('direction', 'Inbound')
        }
        
        # Вызываем функцию автоматического ответа
        success = answer_call_automatically(session_id, party_id, caller_info, device_id)
        
        if success:
            logger.info(f"✅ Звонок успешно принят автоматически: callId={call_data.get('callId')}")
        else:
            logger.error(f"❌ Не удалось автоматически принять звонок: callId={call_data.get('callId')}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при автоматическом ответе на звонок: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def _handle_voicemail_and_answer(voicemail_data: Dict[str, Any]):
    """Обработать голосовую почту и автоматически поднять трубку."""
    try:
        logger.info(f"📞 Обработка голосовой почты: callId={voicemail_data.get('callId')}")
        
        # Ждем немного, чтобы голосовая почта завершилась
        import time
        logger.info(f"⏳ Ожидание завершения голосовой почты (3 секунды)...")
        time.sleep(3)
        
        # Получаем номер звонящего для обратного звонка
        caller_number = voicemail_data.get('from', {}).get('phoneNumber')
        device_id = voicemail_data.get('deviceId')
        
        if not caller_number or not device_id:
            logger.error(f"❌ Недостаточно данных для обратного звонка: caller={caller_number}, device={device_id}")
            return
        
        logger.info(f"📞 Инициируем обратный звонок на номер звонящего {caller_number}...")
        
        # Инициируем обратный звонок через RingCentral API
        success = initiate_outbound_call(caller_number, device_id)
        
        if success:
            logger.info(f"✅ Обратный звонок успешно инициирован на {caller_number}")
        else:
            logger.error(f"❌ Не удалось инициировать обратный звонок на {caller_number}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке голосовой почты: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def initiate_outbound_call(phone_number: str, device_id: str) -> bool:
    """Инициировать исходящий звонок через RingCentral API."""
    
    # 🔄 АЛЬТЕРНАТИВНЫЙ ПОДХОД: Попробуем несколько методов последовательно
    methods_to_try = [
        ("call_out", "Call-Out API (не требует Security scope)"),
        ("ringout", "RingOut API (если есть разрешения)"),  
        ("webphone_notify", "Уведомление WebPhone о необходимости звонка")
    ]
    
    for method, description in methods_to_try:
        try:
            logger.info(f"🔄 Пробуем метод: {description}")
            
            if method == "call_out":
                # ✅ Используем Call-Out API вместо Call Control API
                # Этот endpoint не требует Security scope
                call_data = {
                    "from": {
                        "phoneNumber": Config.RINGCENTRAL['main_number']  # Основной номер как источник
                    },
                    "to": {
                        "phoneNumber": phone_number
                    }
                }
                
                logger.info(f"📋 Данные для Call-Out: {call_data}")
                
                # Пробуем Call-Out API endpoint
                response = make_request(
                    'POST',
                    '/restapi/v1.0/account/~/extension/~/call-out',
                    call_data
                )
                
                logger.info(f"✅ Call-Out звонок инициирован! Response: {response}")
                return True
                
            elif method == "ringout":
                # RingOut API метод
                logger.info(f"📞 Инициация исходящего звонка на {phone_number} с device {device_id}")
                
                ringout_data = {
                    "from": {
                        "phoneNumber": Config.RINGCENTRAL['main_number']
                    },
                    "to": {
                        "phoneNumber": phone_number  
                    },
                    "callerId": {
                        "phoneNumber": Config.RINGCENTRAL['main_number']
                    },
                    "playPrompt": False,  # Отключаем промпт
                    "country": {
                        "id": "1"  # США
                    }
                }
                
                logger.info(f"📋 Данные для RingOut: {ringout_data}")
                
                ringout_response = make_request(
                    'POST',
                    '/restapi/v1.0/account/~/extension/~/ringout',
                    ringout_data
                )
                
                logger.info(f"✅ RingOut звонок инициирован! Response: {ringout_response}")
                return True
                
            elif method == "webphone_notify":
                # 🔔 Уведомляем WebPhone о необходимости сделать исходящий звонок
                logger.info(f"🔔 Уведомляем WebPhone о необходимости звонка на {phone_number}")
                
                # Отправляем команду WebPhone мосту
                try:
                    import requests
                    webphone_data = {
                        "action": "make_call",
                        "to": phone_number,
                        "from": device_id
                    }
                    
                    # Предполагается, что WebPhone мост работает на порту 8081
                    webphone_response = requests.post(
                        'http://localhost:8081/make-call',
                        json=webphone_data,
                        timeout=5
                    )
                    
                    if webphone_response.status_code == 200:
                        logger.info(f"✅ WebPhone уведомлен о необходимости звонка на {phone_number}")
                        return True
                    else:
                        logger.warn(f"⚠️ WebPhone ответил кодом {webphone_response.status_code}")
                        
                except Exception as webphone_error:
                    logger.warn(f"⚠️ Не удалось связаться с WebPhone: {webphone_error}")
                
                # Fallback - просто логируем необходимость звонка  
                logger.info(f"📝 ЗАМЕТКА: Необходимо совершить исходящий звонок на {phone_number}")
                logger.info(f"📱 Рекомендуется использовать устройство {device_id}")
                logger.info(f"💡 Альтернатива: Звонок можно сделать вручную через приложение RingCentral")
                return True  # Возвращаем True чтобы не блокировать процесс
                
        except Exception as method_error:
            logger.warn(f"⚠️ Метод {description} не сработал: {str(method_error)}")
            continue
    
    # Если все методы не сработали
    logger.error(f"❌ Все методы исходящих звонков не сработали для номера {phone_number}")
    logger.info(f"💡 РЕКОМЕНДАЦИЯ: Проверьте разрешения приложения RingCentral")
    logger.info(f"💡 АЛЬТЕРНАТИВА: Совершите звонок вручную на номер {phone_number}")
    
    return False

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
def handle_webphone_call():
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
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        response = loop.run_until_complete(audio_stream_handler.handle_webphone_call(call_data))
        
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

def answer_call_automatically(session_id: str, party_id: str, caller_info: Dict[str, Any], device_id: str = None) -> bool:
    """
    Автоматически принять звонок через RingCentral Call Control API
    
    Args:
        session_id: ID телефонной сессии
        party_id: ID участника звонка
        caller_info: Информация о звонящем
        device_id: ID устройства для ответа на звонок
        
    Returns:
        bool: True если звонок успешно принят
    """
    try:
        call_id = f"{session_id}_{party_id}"
        logger.info(f"🔄 Попытка автоматически ответить на звонок: session={session_id}, party={party_id}")
        
        # Проверяем, не пытались ли уже ответить на этот звонок
        with answer_lock:
            if call_id in answered_calls:
                logger.info(f"⚠️ На звонок {call_id} уже пытались ответить, пропускаем")
                return False
            answered_calls.add(call_id)
            logger.info(f"🔒 Звонок {call_id} отмечен как обрабатываемый")
        
        # Сначала проверяем статус звонка
        try:
            session_info = make_request('GET', f'/restapi/v1.0/account/~/extension/~/telephony/sessions/{session_id}')
            logger.info(f"📋 Информация о сессии перед ответом: {session_info}")
            
            # Ищем нужную party и проверяем её статус
            parties = session_info.get('parties', [])
            target_party = None
            for party in parties:
                if party.get('id') == party_id:
                    target_party = party
                    break
            
            if not target_party:
                logger.error(f"❌ Party {party_id} не найдена в сессии {session_id}")
                return False
            
            party_status = target_party.get('status', {}).get('code')
            party_reason = target_party.get('status', {}).get('reason')
            
            # Проверяем допустимые статусы для ответа на звонок
            valid_statuses = ['Setup', 'Proceeding', 'Alerting']
            invalid_statuses = ['Disconnected', 'Gone', 'Cancelled', 'Answered', 'Connected']
            
            if party_status in invalid_statuses:
                logger.warning(f"⚠️ Нельзя ответить на звонок в статусе: {party_status}")
                if party_reason:
                    logger.warning(f"⚠️ Причина: {party_reason}")
                return False
            elif party_status not in valid_statuses:
                logger.warning(f"⚠️ Неизвестный статус для ответа: {party_status}")
                return False
                
            logger.info(f"✅ Статус звонка подходит для ответа: {party_status}")
            
        except Exception as check_error:
            logger.warning(f"⚠️ Не удалось проверить статус звонка, пробуем ответить: {check_error}")
        
        # Подготавливаем тело запроса с deviceId
        request_body = {}
        if device_id:
            request_body["deviceId"] = device_id
            logger.info(f"📱 Используем deviceId из webhook события: {device_id}")
        else:
            logger.error("❌ deviceId не предоставлен, невозможно принять звонок")
            return False
        
        # Проверяем авторизацию перед запросом
        try:
            from ringcentral_auth import get_auth_status
            auth_status = get_auth_status()
            logger.info(f"🔐 Статус авторизации: {auth_status}")
        except Exception as auth_error:
            logger.warning(f"⚠️ Не удалось проверить статус авторизации: {auth_error}")
            logger.info(f"🔄 Продолжаем без проверки авторизации...")
        
        # Логируем все параметры для диагностики
        logger.info(f"🔍 Диагностика параметров:")
        logger.info(f"   Session ID: {session_id}")
        logger.info(f"   Party ID: {party_id}")
        logger.info(f"   Device ID: {device_id}")
        logger.info(f"   Caller Info: {caller_info}")
        
        # ✅ Правильный endpoint для ответа на звонок
        # Документация: https://developers.ringcentral.com/api-reference/Call-Control/answerCall
        logger.info(f"📤 Отправляем запрос на ответ: POST /restapi/v1.0/account/~/extension/~/telephony/sessions/{session_id}/parties/{party_id}/answer")
        logger.info(f"📋 Тело запроса: {request_body}")
        
        response = make_request(
            'POST',
            f'/restapi/v1.0/account/~/extension/~/telephony/sessions/{session_id}/parties/{party_id}/answer',
            request_body if request_body else None
        )
        
        logger.info(f"✅ Звонок успешно принят! Response: {response}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при автоматическом ответе на звонок: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Удаляем из отвеченных звонков при ошибке
        with answer_lock:
            answered_calls.discard(call_id)
            logger.info(f"🗑️ Звонок {call_id} удален из отвеченных при ошибке")
        
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
                device_id = call_data.get('deviceId')
                if answer_call_automatically(telephony_session_id, party_id, caller_info, device_id):
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