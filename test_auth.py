#!/usr/bin/env python3
"""
Быстрый тест RingCentral JWT авторизации
Запуск: python test_auth.py
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

async def main():
    """Основная функция теста"""
    print("=" * 60)
    print("🧪 RingCentral JWT Authentication Test")
    print("=" * 60)
    
    # Проверяем наличие JWT токена
    jwt_token = os.getenv('RINGCENTRAL_JWT_TOKEN')
    if jwt_token:
        print(f"✅ JWT Token found (length: {len(jwt_token)} chars)")
    else:
        print("❌ JWT Token NOT found in environment")
    
    print(f"📋 Auth Method: {os.getenv('RINGCENTRAL_AUTH_METHOD', 'jwt')}")
    print("=" * 60)
    
    # Импортируем и запускаем тест
    try:
        from ringcentral_client import test_ringcentral_auth
        result = await test_ringcentral_auth()
        
        print("=" * 60)
        if result:
            print("✅ TEST PASSED - Authentication successful!")
        else:
            print("❌ TEST FAILED - Authentication failed!")
        print("=" * 60)
        
        return result
        
    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
        print("=" * 60)
        return False

if __name__ == "__main__":
    # Запускаем тест
    success = asyncio.run(main())
    
    # Возвращаем код выхода
    sys.exit(0 if success else 1)