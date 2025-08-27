#!/usr/bin/env python3
"""
Простое решение для AI ответа на звонки через RingCentral
Используя только REST API
"""

import os
import asyncio
import aiohttp
import logging
from flask import Flask, request, jsonify
from datetime import datetime
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Конфигурация RingCentral
RINGCENTRAL_CLIENT_ID = os.getenv('RINGCENTRAL_CLIENT_ID')
RINGCENTRAL_CLIENT_SECRET = os.getenv('RINGCENTRAL_CLIENT_SECRET')
RINGCENTRAL_JWT_TOKEN = os.getenv('RINGCENTRAL_JWT_TOKEN')
RINGCENTRAL_SERVER = 'https://platform.ringcentral.com'

# Глобальный токен доступа
access_token = None

async def get_access_token():
    """Получить токен доступа через JWT"""
    global access_token
    
    async with aiohttp.ClientSession() as session:
        data = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': RINGCENTRAL_JWT_TOKEN
        }
        
        async with session.post(
            f'{RINGCENTRAL_SERVER}/restapi/oauth/token',
            data=data,
            auth=aiohttp.BasicAuth(RINGCENTRAL_CLIENT_ID, RINGCENTRAL_CLIENT_SECRET)
        ) as response:
            result = await response.json()
            access_token = result['access_token']
            logger.info("✅ Получен токен доступа RingCentral")
            return access_token

async def answer_incoming_call(telephony_session_id, party_id):
    """
    Ответить на входящий звонок через Call Control API
    """
    if not access_token:
        await get_access_token()
    
    async with aiohttp.ClientSession() as session:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Ответить на звонок
        url = f'{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/answer'
        
        async with session.post(url, headers=headers) as response:
            if response.status == 200:
                logger.info(f"✅ Звонок принят: session={telephony_session_id}, party={party_id}")
                return True
            else:
                error = await response.text()
                logger.error(f"❌ Ошибка при ответе на звонок: {error}")
                return False

async def play_ai_message(telephony_session_id, party_id, message):
    """
    Воспроизвести AI сообщение в звонке
    Использует Text-to-Speech и проигрывает аудио
    """
    # Вариант 1: Использовать встроенный TTS RingCentral
    async with aiohttp.ClientSession() as session:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Проиграть текстовое сообщение
        url = f'{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/play'
        
        data = {
            'text': message,
            'voiceId': 'Joanna',  # Голос для TTS
            'languageId': 'en-US'
        }
        
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                logger.info(f"✅ AI сообщение воспроизведено: {message}")
            else:
                error = await response.text()
                logger.error(f"❌ Ошибка воспроизведения: {error}")

async def transfer_to_voicemail(telephony_session_id, party_id):
    """
    Перевести звонок на голосовую почту если AI не может помочь
    """
    async with aiohttp.ClientSession() as session:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        url = f'{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/transfer'
        
        data = {
            'voicemail': True
        }
        
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                logger.info("✅ Звонок переведен на голосовую почту")

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Обработчик webhook событий от RingCentral
    """
    try:
        data = request.json
        
        # Проверяем тип события
        if data.get('event') == '/restapi/v1.0/account/~/telephony/sessions':
            body = data.get('body', {})
            telephony_session_id = body.get('telephonySessionId')
            parties = body.get('parties', [])
            
            # Ищем входящий звонок
            for party in parties:
                if party.get('direction') == 'Inbound' and party.get('status', {}).get('code') == 'Setup':
                    party_id = party.get('id')
                    from_number = party.get('from', {}).get('phoneNumber', 'Unknown')
                    
                    logger.info(f"📞 Входящий звонок от {from_number}")
                    
                    # Запускаем обработку звонка асинхронно
                    asyncio.create_task(handle_incoming_call(telephony_session_id, party_id, from_number))
                    
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        return jsonify({'error': str(e)}), 500

async def handle_incoming_call(telephony_session_id, party_id, from_number):
    """
    Основная логика обработки входящего звонка AI системой
    """
    try:
        # 1. Отвечаем на звонок
        answered = await answer_incoming_call(telephony_session_id, party_id)
        if not answered:
            return
        
        # 2. Ждем 1 секунду
        await asyncio.sleep(1)
        
        # 3. Приветствуем звонящего
        greeting = f"Hello! This is AI assistant from Prime Cargo Logistics. How can I help you today?"
        await play_ai_message(telephony_session_id, party_id, greeting)
        
        # 4. Здесь должна быть логика:
        # - Распознавание речи звонящего
        # - Обработка запроса через AI
        # - Генерация и воспроизведение ответа
        
        # Пример простого сценария:
        await asyncio.sleep(3)  # Имитация ожидания ответа
        
        # 5. AI отвечает
        ai_response = "I understand you're calling about shipment tracking. Let me check that for you."
        await play_ai_message(telephony_session_id, party_id, ai_response)
        
        # 6. Завершение разговора
        await asyncio.sleep(2)
        closing = "Is there anything else I can help you with today?"
        await play_ai_message(telephony_session_id, party_id, closing)
        
    except Exception as e:
        logger.error(f"Ошибка обработки звонка: {e}")

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка состояния сервиса"""
    return jsonify({
        'status': 'healthy',
        'service': 'AI Phone Answer System',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Инициализация при запуске
    asyncio.run(get_access_token())
    
    # Запуск Flask сервера
    app.run(host='0.0.0.0', port=8000, debug=True)