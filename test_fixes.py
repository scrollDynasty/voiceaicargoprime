#!/usr/bin/env python3
"""
Простой тест для проверки исправлений webhook сервера
"""

import requests
import json
import time

def test_webhook_health():
    """Тест здоровья webhook сервера"""
    try:
        response = requests.get('http://localhost:5000/health', timeout=5)
        if response.status_code == 200:
            print("✅ Webhook сервер работает")
            return True
        else:
            print(f"❌ Webhook сервер вернул статус {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка подключения к webhook серверу: {e}")
        return False

def test_js_bridge_health():
    """Тест здоровья JS bridge"""
    try:
        response = requests.get('http://localhost:8081/health', timeout=5)
        if response.status_code == 200:
            print("✅ JS Bridge работает")
            return True
        else:
            print(f"❌ JS Bridge вернул статус {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка подключения к JS Bridge: {e}")
        return False

def test_webhook_endpoint():
    """Тест webhook endpoint с симуляцией звонка в состоянии Ringing"""
    webhook_data = {
        "uuid": "test-uuid-123",
        "event": "/restapi/v1.0/account/1861766019/extension/2069909019/telephony/sessions",
        "timestamp": "2025-08-26T20:00:00.000Z",
        "subscriptionId": "test-subscription",
        "ownerId": "2069909019",
        "body": {
            "sequence": 1,
            "sessionId": "test-session-123",
            "telephonySessionId": "s-test-session-123",
            "serverId": "test-server",
            "eventTime": "2025-08-26T20:00:00.000Z",
            "parties": [
                {
                    "accountId": "1861766019",
                    "extensionId": "2069909019",
                    "id": "p-test-party-123",
                    "direction": "Inbound",
                    "to": {
                        "phoneNumber": "+15139283626",
                        "name": "Test User",
                        "extensionId": "2069909019",
                        "deviceId": "805313637019"
                    },
                    "from": {
                        "phoneNumber": "101",
                        "name": "Test Caller",
                        "extensionId": "1861766019"
                    },
                    "status": {
                        "code": "Ringing",
                        "rcc": False
                    },
                    "missedCall": False,
                    "standAlone": False,
                    "muted": False
                }
            ],
            "origin": {
                "type": "Call"
            }
        }
    }
    
    try:
        response = requests.post(
            'http://localhost:5000/webhook',
            json=webhook_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Webhook endpoint обработал тестовый звонок")
            return True
        else:
            print(f"❌ Webhook endpoint вернул статус {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании webhook endpoint: {e}")
        return False

def main():
    print("🧪 Запуск тестов исправлений...")
    print("=" * 50)
    
    # Тест здоровья серверов
    webhook_ok = test_webhook_health()
    js_ok = test_js_bridge_health()
    
    if not webhook_ok:
        print("❌ Webhook сервер недоступен, тесты пропущены")
        return
    
    print("=" * 50)
    
    # Тест обработки webhook события
    webhook_test_ok = test_webhook_endpoint()
    
    print("=" * 50)
    print("📋 Результаты тестов:")
    print(f"  - Webhook Server: {'✅' if webhook_ok else '❌'}")
    print(f"  - JS Bridge: {'✅' if js_ok else '❌'}")
    print(f"  - Webhook Processing: {'✅' if webhook_test_ok else '❌'}")
    
    if webhook_ok and webhook_test_ok:
        print("🎉 Все основные тесты прошли успешно!")
    else:
        print("⚠️ Некоторые тесты не прошли, проверьте логи серверов")

if __name__ == "__main__":
    main()