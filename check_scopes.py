#!/usr/bin/env python3
"""
Быстрая проверка разрешений JWT токена
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def check_scopes():
    """Проверяем разрешения JWT токена"""
    
    jwt_token = os.getenv('RINGCENTRAL_JWT_TOKEN')
    server_url = os.getenv('RINGCENTRAL_SERVER', 'https://platform.ringcentral.com')
    
    print("🔍 Проверка разрешений JWT токена")
    print("=" * 50)
    
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Content-Type': 'application/json'
    }
    
    # Тестируем разные endpoints
    tests = [
        ('GET', '/restapi/v1.0', 'Service Info'),
        ('GET', '/restapi/v1.0/account/~/extension/~', 'Extension Info'),
        ('GET', '/restapi/v1.0/subscription', 'List Subscriptions'),
    ]
    
    for method, endpoint, name in tests:
        try:
            response = requests.get(f"{server_url}{endpoint}", headers=headers)
            status = response.status_code
            
            if status == 200:
                print(f"✅ {name}: {status} - РАБОТАЕТ")
            elif status == 401:
                print(f"❌ {name}: {status} - НЕТ РАЗРЕШЕНИЙ")
            elif status == 403:
                print(f"🚫 {name}: {status} - ЗАПРЕЩЕНО")
            else:
                print(f"❓ {name}: {status} - НЕИЗВЕСТНО")
                
        except Exception as e:
            print(f"💥 {name}: ОШИБКА - {e}")
    
    print("\n📋 РЕКОМЕНДАЦИИ:")
    print("1. Если 'List Subscriptions' показывает 401 - включите Webhook Subscriptions")
    print("2. Создайте новый JWT токен после включения разрешений")
    print("3. Обновите RINGCENTRAL_JWT_TOKEN в .env файле")

if __name__ == "__main__":
    check_scopes()
