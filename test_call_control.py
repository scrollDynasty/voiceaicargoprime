#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Call Control API
"""

import asyncio
import logging
import json
from datetime import datetime

from ringcentral_auth import authenticate, make_request
from speech_processor import async_synthesize

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_auth():
    """Тест авторизации"""
    logger.info("🔐 Тестирование авторизации...")
    if authenticate():
        logger.info("✅ Авторизация успешна!")
        return True
    else:
        logger.error("❌ Ошибка авторизации!")
        return False

async def test_tts():
    """Тест генерации TTS"""
    logger.info("🎵 Тестирование TTS...")
    
    test_text = "Hello! This is a test of the text to speech system. Welcome to Prime Cargo Logistics!"
    
    try:
        audio_data = await async_synthesize(test_text)
        logger.info(f"✅ TTS успешно сгенерирован: {len(audio_data)} байт")
        
        # Сохраняем для проверки
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recordings/test_tts_{timestamp}.wav"
        
        with open(filename, "wb") as f:
            f.write(audio_data)
        
        logger.info(f"💾 Аудио сохранено в {filename}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка TTS: {str(e)}")
        return False

async def test_webhook_subscription():
    """Проверка webhook подписки"""
    logger.info("🔔 Проверка webhook подписки...")
    
    try:
        # Получаем список подписок
        response = make_request('GET', '/restapi/v1.0/subscription')
        
        if response and 'records' in response:
            logger.info(f"📋 Найдено подписок: {len(response['records'])}")
            
            for sub in response['records']:
                logger.info(f"  - ID: {sub['id']}")
                logger.info(f"    Status: {sub['status']}")
                logger.info(f"    Event filters: {sub.get('eventFilters', [])}")
                
            return True
        else:
            logger.warning("⚠️ Нет активных подписок")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки подписок: {str(e)}")
        return False

async def test_active_calls():
    """Проверка активных звонков"""
    logger.info("📞 Проверка активных звонков...")
    
    try:
        # Получаем активные сессии
        response = make_request('GET', '/restapi/v1.0/account/~/extension/~/telephony/sessions')
        
        if response and 'records' in response:
            logger.info(f"📋 Найдено активных сессий: {len(response['records'])}")
            
            for session in response['records']:
                logger.info(f"  - Session ID: {session.get('id')}")
                logger.info(f"    Parties: {len(session.get('parties', []))}")
                
                for party in session.get('parties', []):
                    logger.info(f"      - Party: {party.get('id')}")
                    logger.info(f"        Direction: {party.get('direction')}")
                    logger.info(f"        Status: {party.get('status', {}).get('code')}")
                    
            return True
        else:
            logger.info("📵 Нет активных звонков")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки звонков: {str(e)}")
        return False

async def test_media_upload():
    """Тест загрузки медиа файла"""
    logger.info("📤 Тестирование загрузки медиа...")
    
    try:
        # Генерируем тестовое аудио
        test_audio = await async_synthesize("This is a test media upload.")
        
        # Сохраняем во временный файл
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(test_audio)
            tmp_path = tmp.name
        
        # Загружаем на сервер
        import os
        with open(tmp_path, 'rb') as f:
            response = make_request(
                'POST',
                '/restapi/v1.0/account/~/media',
                data=None,
                files={'media': ('test.wav', f, 'audio/wav')}
            )
        
        os.unlink(tmp_path)
        
        if response and 'id' in response:
            logger.info(f"✅ Медиа загружено успешно! Media ID: {response['id']}")
            return True
        else:
            logger.error("❌ Ошибка загрузки медиа")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки медиа: {str(e)}")
        return False

async def run_all_tests():
    """Запустить все тесты"""
    logger.info("🚀 Запуск всех тестов Call Control API...")
    logger.info("=" * 60)
    
    tests = [
        ("Авторизация", test_auth),
        ("TTS генерация", test_tts),
        ("Webhook подписка", test_webhook_subscription),
        ("Активные звонки", test_active_calls),
        ("Загрузка медиа", test_media_upload)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Тест: {test_name}")
        logger.info("-" * 40)
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в тесте: {str(e)}")
            results.append((test_name, False))
        
        logger.info("")
    
    # Итоги
    logger.info("=" * 60)
    logger.info("📊 ИТОГИ ТЕСТИРОВАНИЯ:")
    logger.info("-" * 40)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name:<30} {status}")
    
    logger.info("-" * 40)
    logger.info(f"Всего тестов: {total}")
    logger.info(f"Успешно: {passed}")
    logger.info(f"Провалено: {total - passed}")
    logger.info(f"Успешность: {(passed/total)*100:.1f}%")
    
    return passed == total

if __name__ == "__main__":
    # Запускаем тесты
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)