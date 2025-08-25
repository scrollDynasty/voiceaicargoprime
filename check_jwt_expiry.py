#!/usr/bin/env python3
"""
Проверка срока действия JWT токена RingCentral
"""

import os
import jwt
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def decode_jwt_without_verification(token):
    """Декодируем JWT без проверки подписи (только для получения payload)"""
    try:
        # Разделяем токен на части
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        # Декодируем payload (вторая часть)
        import base64
        import json
        
        # Добавляем padding если нужно
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        # Декодируем base64
        decoded = base64.urlsafe_b64decode(payload)
        payload_data = json.loads(decoded.decode('utf-8'))
        
        return payload_data
    except Exception as e:
        print(f"❌ Ошибка декодирования JWT: {e}")
        return None

def check_jwt_expiry():
    """Проверяем срок действия JWT токена"""
    
    print("🔍 ПРОВЕРКА СРОКА ДЕЙСТВИЯ JWT ТОКЕНА")
    print("=" * 50)
    
    jwt_token = os.getenv('RINGCENTRAL_JWT_TOKEN')
    
    if not jwt_token:
        print("❌ JWT токен не найден в .env")
        return False
    
    print(f"📝 JWT Token: {jwt_token[:50]}...")
    print()
    
    # Декодируем JWT
    payload = decode_jwt_without_verification(jwt_token)
    
    if not payload:
        print("❌ Не удалось декодировать JWT токен")
        return False
    
    # Получаем время истечения
    exp_timestamp = payload.get('exp')
    iat_timestamp = payload.get('iat')
    
    if not exp_timestamp:
        print("❌ JWT токен не содержит время истечения")
        return False
    
    # Текущее время
    current_time = int(time.time())
    
    # Конвертируем timestamp в читаемый формат
    exp_date = datetime.fromtimestamp(exp_timestamp)
    iat_date = datetime.fromtimestamp(iat_timestamp) if iat_timestamp else None
    current_date = datetime.fromtimestamp(current_time)
    
    print(f"📅 Время создания: {iat_date}")
    print(f"📅 Время истечения: {exp_date}")
    print(f"📅 Текущее время: {current_date}")
    print()
    
    # Проверяем срок действия
    time_until_expiry = exp_timestamp - current_time
    
    if time_until_expiry <= 0:
        print("❌ JWT токен ИСТЕК!")
        print(f"   Токен истек {abs(time_until_expiry)} секунд назад")
        return False
    elif time_until_expiry < 3600:  # Меньше 1 часа
        print("⚠️ JWT токен истекает в течение часа!")
        print(f"   Осталось: {time_until_expiry} секунд ({time_until_expiry//3600} часов)")
        return False
    else:
        hours_remaining = time_until_expiry // 3600
        days_remaining = hours_remaining // 24
        print(f"✅ JWT токен действителен!")
        print(f"   Осталось: {time_until_expiry} секунд")
        print(f"   Это примерно: {hours_remaining} часов ({days_remaining} дней)")
        return True

def check_jwt_payload():
    """Проверяем содержимое JWT payload"""
    
    print("\n🔍 АНАЛИЗ JWT PAYLOAD")
    print("=" * 30)
    
    jwt_token = os.getenv('RINGCENTRAL_JWT_TOKEN')
    payload = decode_jwt_without_verification(jwt_token)
    
    if not payload:
        return
    
    print("📋 Содержимое JWT токена:")
    for key, value in payload.items():
        if key == 'exp':
            exp_date = datetime.fromtimestamp(value)
            print(f"   {key}: {value} ({exp_date})")
        elif key == 'iat':
            iat_date = datetime.fromtimestamp(value)
            print(f"   {key}: {value} ({iat_date})")
        else:
            print(f"   {key}: {value}")

if __name__ == "__main__":
    is_valid = check_jwt_expiry()
    check_jwt_payload()
    
    print("\n📋 РЕКОМЕНДАЦИИ:")
    if is_valid:
        print("✅ JWT токен действителен - проблема в разрешениях")
        print("1. Проверьте разрешения в Developer Console")
        print("2. Убедитесь что включены Webhook Subscriptions")
    else:
        print("❌ JWT токен истек - нужно создать новый")
        print("1. Перейдите в RingCentral Developer Console")
        print("2. Создайте новый JWT токен")
        print("3. Обновите RINGCENTRAL_JWT_TOKEN в .env")
