#!/usr/bin/env python3
"""
Упрощенный webhook сервер для тестирования приема звонков
"""

import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, Response
import requests
import os
from typing import Dict, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('webhook_test.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Имитация функции make_request из ringcentral_auth
def make_request(method: str, endpoint: str, data: Dict = None):
    """Имитация запроса к RingCentral API"""
    logger.info(f"🔄 Имитация {method} запроса к {endpoint}")
    logger.info(f"📋 Данные: {json.dumps(data, indent=2) if data else 'нет данных'}")
    
    # Возвращаем имитационный ответ
    return {"status": "simulated_success", "data": data}

def answer_call_automatically(session_id: str, party_id: str, caller_info: Dict[str, Any], device_id: str = None) -> bool:
    """
    Автоматически принять звонок через RingCentral Call Control API
    """
    try:
        logger.info(f"🔄 Попытка автоматически ответить на звонок: session={session_id}, party={party_id}")
        
        # Подготавливаем тело запроса с deviceId
        request_body = {}
        if device_id:
            request_body["deviceId"] = device_id
            logger.info(f"📱 Используем deviceId: {device_id}")
        else:
            logger.warning("⚠️ deviceId не предоставлен, пробуем без него")
        
        # ✅ Правильный endpoint для ответа на звонок
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
        return False

@app.route('/webhook', methods=['POST', 'GET'])
def handle_webhook():
    """Обработка webhook событий от RingCentral"""
    try:
        logger.info("📞 Получен POST запрос на /webhook")
        
        # Получаем данные
        webhook_data = request.get_json()
        if not webhook_data:
            logger.error("❌ Нет данных в webhook запросе")
            return jsonify({"error": "No data"}), 400
        
        logger.info(f"📋 Получено webhook событие: {json.dumps(webhook_data, indent=2)}")
        
        # Обрабатываем только telephony события
        event_type = webhook_data.get('event', '')
        if '/telephony/sessions' in event_type:
            logger.info("📞 Обнаружено telephony событие")
            return process_telephony_event(webhook_data.get('body', {}))
        else:
            logger.info(f"📋 Не telephony событие: {webhook_data.get('uuid', 'unknown')}")
            return jsonify({"status": "ignored"}), 200
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

def process_telephony_event(session_data: Dict) -> Response:
    """
    Обработка telephony/sessions событий
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
            # Обрабатываем звонки в состояниях "Ringing" или "Proceeding" для автоматического ответа
            if direction == 'Inbound' and status.get('code') in ['Ringing', 'Proceeding']:
                logger.info(f"🔔 Обнаружен входящий звонок в состоянии {status.get('code')}: session={telephony_session_id}, party={party_id}")
                
                # Извлекаем deviceId из данных получателя
                to_data = party.get('to', {})
                device_id = to_data.get('deviceId')
                
                logger.info(f"📞 Подготовлены данные звонка для автоматического ответа:")
                logger.info(f"   Session ID: {telephony_session_id}")
                logger.info(f"   Party ID: {party_id}")
                logger.info(f"   Device ID: {device_id}")
                logger.info(f"   От: {party.get('from', {}).get('phoneNumber', 'Unknown')}")
                logger.info(f"   К: {to_data.get('phoneNumber', 'Unknown')}")
                
                # Пытаемся ответить на звонок
                caller_info = party.get('from', {})
                if answer_call_automatically(telephony_session_id, party_id, caller_info, device_id):
                    logger.info("✅ Звонок принят!")
                else:
                    logger.error("❌ Не удалось принять звонок")
                
            elif direction == 'Inbound' and status.get('code') in ['Proceeding', 'Setup', 'Alerting']:
                # Логируем входящие звонки в других состояниях без обработки
                logger.info(f"📱 Входящий звонок в состоянии {status.get('code')} (ожидаем Ringing или Proceeding): session={telephony_session_id}, party={party_id}")
                
            elif direction == 'Inbound' and status.get('code') in ['Answered', 'Connected']:
                # Логируем когда звонок уже отвечен
                logger.info(f"📞 Входящий звонок уже отвечен в состоянии {status.get('code')}: session={telephony_session_id}, party={party_id}")
                
            elif direction == 'Inbound' and status.get('code') in ['Disconnected', 'Gone', 'Cancelled']:
                # Логируем завершенные звонки
                logger.info(f"📞 Входящий звонок завершен в состоянии {status.get('code')}: session={telephony_session_id}, party={party_id}")
        
        return jsonify({"status": "processed"}), 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки telephony события: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

if __name__ == '__main__':
    logger.info("🚀 Запуск упрощенного webhook тест сервера...")
    logger.info("📋 Сервер будет слушать на порту 5000")
    app.run(host='0.0.0.0', port=5000, debug=True)