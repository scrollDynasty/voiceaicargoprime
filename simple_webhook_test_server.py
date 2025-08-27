#!/usr/bin/env python3
"""
Упрощенный webhook сервер для тестирования входящих звонков
"""

import json
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Настройки
JS_SERVER_URL = "http://localhost:8081"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка webhook событий от RingCentral"""
    try:
        data = request.get_json()
        logger.info(f"📞 Получено webhook событие: {json.dumps(data, indent=2)}")
        
        # Обрабатываем webhook событие
        try:
            response = requests.post(
                f"{JS_SERVER_URL}/webhook",
                json=data,
                timeout=5
            )
            logger.info(f"✅ Webhook переслан в JS сервер: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Ошибка пересылки в JS сервер: {e}")
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья сервера"""
    return jsonify({"status": "ok", "message": "Webhook server is running"}), 200



if __name__ == '__main__':
    logger.info("🚀 Запуск упрощенного webhook сервера...")
    logger.info(f"🔗 JS Server URL: {JS_SERVER_URL}")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False
    )