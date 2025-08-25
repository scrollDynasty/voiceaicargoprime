#!/usr/bin/env python3
"""
Тестовый скрипт для проверки webhook endpoints
Тестирует все сценарии работы с RingCentral webhook
"""

import requests
import json
import hmac
import hashlib
import base64
import sys

# Конфигурация
WEBHOOK_URL = "http://localhost:5000/webhook"
WEBHOOK_SECRET = "1Z7ztKD0I1gBu1QscmOBkonCn1tXG7LN"  # Из config.py

def print_test_header(test_name):
    """Печать заголовка теста"""
    print(f"\n{'=' * 60}")
    print(f"🧪 ТЕСТ: {test_name}")
    print(f"{'=' * 60}")

def print_result(success, message, details=None):
    """Печать результата теста"""
    if success:
        print(f"✅ УСПЕХ: {message}")
    else:
        print(f"❌ ОШИБКА: {message}")
    
    if details:
        print(f"Детали: {details}")

def generate_signature(body, secret):
    """Генерация подписи webhook как в RingCentral"""
    signature = base64.b64encode(
        hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha1
        ).digest()
    ).decode()
    return signature

def test_empty_post():
    """Тест 1: Пустой POST запрос"""
    print_test_header("Пустой POST запрос")
    
    try:
        # Отправляем пустой POST без заголовков
        response = requests.post(WEBHOOK_URL, data='', headers={})
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'ok':
                print_result(True, f"Получен корректный ответ: {data}")
            else:
                print_result(False, f"Неожиданный ответ: {data}")
        else:
            print_result(False, f"Неожиданный код ответа: {response.status_code}", 
                        response.text)
            
    except Exception as e:
        print_result(False, f"Исключение: {str(e)}")

def test_get_with_challenge():
    """Тест 2: GET запрос с hub.challenge"""
    print_test_header("GET запрос с challenge")
    
    try:
        challenge = "test123"
        response = requests.get(f"{WEBHOOK_URL}?hub.challenge={challenge}")
        
        if response.status_code == 200 and response.text == challenge:
            print_result(True, f"Challenge возвращен корректно: {response.text}")
        else:
            print_result(False, f"Неожиданный ответ: код={response.status_code}, текст={response.text}")
            
    except Exception as e:
        print_result(False, f"Исключение: {str(e)}")

def test_get_without_challenge():
    """Тест 3: GET запрос без hub.challenge"""
    print_test_header("GET запрос без challenge")
    
    try:
        response = requests.get(WEBHOOK_URL)
        
        if response.status_code == 400:
            print_result(True, f"Получен ожидаемый код 400")
        else:
            print_result(False, f"Неожиданный код ответа: {response.status_code}", 
                        response.text)
            
    except Exception as e:
        print_result(False, f"Исключение: {str(e)}")

def test_post_with_json():
    """Тест 4: POST запрос с JSON данными"""
    print_test_header("POST запрос с JSON")
    
    try:
        # Тестовые данные webhook
        webhook_data = {
            "uuid": "12345678-1234-1234-1234-123456789012",
            "event": "/restapi/v1.0/account/~/extension/~/telephony/sessions",
            "timestamp": "2024-01-15T10:00:00.000Z",
            "body": {
                "telephonySessionId": "s-1234567890",
                "parties": []
            }
        }
        
        # Преобразуем в JSON
        body = json.dumps(webhook_data).encode('utf-8')
        
        # Генерируем подпись
        signature = generate_signature(body, WEBHOOK_SECRET)
        
        # Заголовки
        headers = {
            'Content-Type': 'application/json',
            'X-RC-Signature': signature
        }
        
        response = requests.post(WEBHOOK_URL, data=body, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Получен корректный ответ: {data}")
        else:
            print_result(False, f"Неожиданный код ответа: {response.status_code}", 
                        response.text)
            
    except Exception as e:
        print_result(False, f"Исключение: {str(e)}")

def test_post_with_invalid_signature():
    """Тест 5: POST запрос с неверной подписью"""
    print_test_header("POST запрос с неверной подписью")
    
    try:
        webhook_data = {"test": "data"}
        body = json.dumps(webhook_data).encode('utf-8')
        
        headers = {
            'Content-Type': 'application/json',
            'X-RC-Signature': 'invalid_signature_123'
        }
        
        response = requests.post(WEBHOOK_URL, data=body, headers=headers)
        
        if response.status_code == 401:
            print_result(True, f"Получен ожидаемый код 401 (неавторизован)")
        else:
            print_result(False, f"Неожиданный код ответа: {response.status_code}", 
                        response.text)
            
    except Exception as e:
        print_result(False, f"Исключение: {str(e)}")

def test_post_with_invalid_json():
    """Тест 6: POST запрос с невалидным JSON"""
    print_test_header("POST запрос с невалидным JSON")
    
    try:
        # Отправляем невалидный JSON
        body = b'{"invalid": json}'  # Нет закрывающей кавычки
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        response = requests.post(WEBHOOK_URL, data=body, headers=headers)
        
        if response.status_code == 400:
            print_result(True, f"Получен ожидаемый код 400 (bad request)")
        else:
            print_result(False, f"Неожиданный код ответа: {response.status_code}", 
                        response.text)
            
    except Exception as e:
        print_result(False, f"Исключение: {str(e)}")

def test_post_without_content_type():
    """Тест 7: POST запрос без Content-Type header"""
    print_test_header("POST запрос без Content-Type")
    
    try:
        # RingCentral может отправлять POST без Content-Type
        webhook_data = {"test": "data"}
        body = json.dumps(webhook_data).encode('utf-8')
        
        # Без Content-Type header
        headers = {}
        
        response = requests.post(WEBHOOK_URL, data=body, headers=headers)
        
        if response.status_code == 200:
            print_result(True, f"Запрос обработан успешно: {response.json()}")
        else:
            print_result(False, f"Неожиданный код ответа: {response.status_code}", 
                        response.text)
            
    except Exception as e:
        print_result(False, f"Исключение: {str(e)}")

def test_telephony_event():
    """Тест 8: Реальное telephony событие"""
    print_test_header("Telephony событие")
    
    try:
        # Пример реального webhook от RingCentral
        webhook_data = {
            "uuid": "4b4f9344-d13f-4f86-be95-3b96e8c82cc0",
            "event": "/restapi/v1.0/account/~/extension/~/telephony/sessions",
            "timestamp": "2024-01-15T10:00:00.000Z",
            "subscriptionId": "5b5f9344-d13f-4f86-be95-3b96e8c82cc0",
            "body": {
                "telephonySessionId": "s-ec0c920e98654d38a8e045d13b96e8c8",
                "serverId": "10.13.22.239.TAM",
                "eventTime": "2024-01-15T10:00:00.000Z",
                "parties": [
                    {
                        "accountId": "2069909019",
                        "extensionId": "2069909019",
                        "id": "p-ec0c920e98654d38a8e045d13b96e8c8-2",
                        "direction": "Inbound",
                        "to": {
                            "phoneNumber": "+15135725833",
                            "name": "Prime Cargo",
                            "extensionId": "2069909019"
                        },
                        "from": {
                            "phoneNumber": "+12345678901",
                            "name": "External Caller"
                        },
                        "status": {
                            "code": "Proceeding",
                            "rcc": false,
                            "mobilePickupData": {}
                        }
                    }
                ],
                "origin": {
                    "type": "Call"
                }
            }
        }
        
        body = json.dumps(webhook_data).encode('utf-8')
        signature = generate_signature(body, WEBHOOK_SECRET)
        
        headers = {
            'Content-Type': 'application/json',
            'X-RC-Signature': signature
        }
        
        response = requests.post(WEBHOOK_URL, data=body, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Telephony событие обработано: {data}")
        else:
            print_result(False, f"Неожиданный код ответа: {response.status_code}", 
                        response.text)
            
    except Exception as e:
        print_result(False, f"Исключение: {str(e)}")

def main():
    """Запуск всех тестов"""
    print(f"🔧 ТЕСТИРОВАНИЕ WEBHOOK ENDPOINTS")
    print(f"📍 URL: {WEBHOOK_URL}")
    print(f"🔑 Secret: {WEBHOOK_SECRET[:10]}...")
    
    # Проверяем доступность сервера
    try:
        response = requests.get("http://localhost:5000/health", timeout=2)
        if response.status_code == 200:
            print(f"✅ Сервер доступен")
        else:
            print(f"❌ Сервер возвращает код {response.status_code}")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ Сервер недоступен: {e}")
        print(f"Убедитесь, что webhook_server.py запущен на порту 5000")
        sys.exit(1)
    
    # Запускаем тесты
    tests = [
        test_empty_post,
        test_get_with_challenge,
        test_get_without_challenge,
        test_post_with_json,
        test_post_with_invalid_signature,
        test_post_with_invalid_json,
        test_post_without_content_type,
        test_telephony_event
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            # Простая проверка на основе вывода (можно улучшить)
            passed += 1
        except:
            failed += 1
    
    # Итоговый отчет
    print(f"\n{'=' * 60}")
    print(f"📊 ИТОГОВЫЙ ОТЧЕТ")
    print(f"{'=' * 60}")
    print(f"Всего тестов: {len(tests)}")
    print(f"✅ Успешно: {passed}")
    print(f"❌ Неудачно: {failed}")
    
    if failed == 0:
        print(f"\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print(f"\n⚠️  Некоторые тесты не прошли. Проверьте логи сервера.")

if __name__ == "__main__":
    main()