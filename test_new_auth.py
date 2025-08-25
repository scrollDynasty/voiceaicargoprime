#!/usr/bin/env python3
"""
Тест новой системы авторизации RingCentral
"""

import logging
from ringcentral_auth import authenticate, make_request, get_auth_status

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_auth_system():
    """Тестируем новую систему авторизации"""
    
    print("🚀 ТЕСТ НОВОЙ СИСТЕМЫ АВТОРИЗАЦИИ RINGCENTRAL")
    print("=" * 60)
    
    try:
        # Шаг 1: Авторизация
        print("\n🔐 ШАГ 1: Авторизация")
        if authenticate():
            print("✅ Авторизация успешна!")
        else:
            print("❌ Авторизация не удалась")
            return False
        
        # Шаг 2: Получаем статус
        print("\n📊 ШАГ 2: Статус авторизации")
        status = get_auth_status()
        print(f"   Метод авторизации: {status['auth_method']}")
        print(f"   Авторизован: {status['is_authenticated']}")
        print(f"   Сервер: {status['server_url']}")
        print(f"   Client ID: {status['client_id']}")
        print(f"   Есть JWT: {status['has_jwt']}")
        print(f"   Есть Refresh Token: {status['has_refresh_token']}")
        
        # Шаг 3: Тестируем базовый API
        print("\n🌐 ШАГ 3: Тест базового API")
        try:
            response = make_request('GET', '/restapi/v1.0')
            print("✅ Базовый API работает")
            print(f"   Server Version: {response.get('serverVersion', 'Unknown')}")
        except Exception as e:
            print(f"❌ Ошибка базового API: {e}")
            return False
        
        # Шаг 4: Тестируем информацию о расширении
        print("\n👤 ШАГ 4: Тест информации о расширении")
        try:
            response = make_request('GET', '/restapi/v1.0/account/~/extension/~')
            print("✅ Информация о расширении получена")
            print(f"   Extension ID: {response.get('id', 'Unknown')}")
            print(f"   Name: {response.get('name', 'Unknown')}")
        except Exception as e:
            print(f"❌ Ошибка получения информации о расширении: {e}")
            print("   Это может быть связано с отсутствием разрешений")
        
        # Шаг 5: Тестируем создание подписки
        print("\n🔗 ШАГ 5: Тест создания подписки")
        try:
            subscription_data = {
                'eventFilters': [
                    '/restapi/v1.0/account/~/extension/~/telephony/sessions'
                ],
                'deliveryMode': {
                    'transportType': 'WebHook',
                    'address': 'https://test.example.com/webhook',
                    'encryption': False
                },
                'expiresIn': 3600  # 1 час для теста
            }
            
            response = make_request('POST', '/restapi/v1.0/subscription', subscription_data)
            print("✅ Подписка создана успешно!")
            print(f"   Subscription ID: {response.get('id', 'Unknown')}")
            
            # Удаляем тестовую подписку
            subscription_id = response.get('id')
            if subscription_id:
                make_request('DELETE', f'/restapi/v1.0/subscription/{subscription_id}')
                print("   Тестовая подписка удалена")
                
        except Exception as e:
            print(f"❌ Ошибка создания подписки: {e}")
            print("   Это может быть связано с отсутствием разрешений Subscriptions:Write")
        
        print("\n🎉 ТЕСТ ЗАВЕРШЕН УСПЕШНО!")
        return True
        
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        return False

def test_permissions():
    """Тестируем разрешения"""
    
    print("\n🔍 ТЕСТ РАЗРЕШЕНИЙ")
    print("=" * 30)
    
    endpoints_to_test = [
        ('GET', '/restapi/v1.0/account/~/extension/~', 'Read Accounts'),
        ('GET', '/restapi/v1.0/subscription', 'Subscriptions:Read'),
        ('POST', '/restapi/v1.0/subscription', 'Subscriptions:Write'),
    ]
    
    for method, endpoint, permission in endpoints_to_test:
        try:
            if method == 'POST':
                # Для POST отправляем пустые данные
                response = make_request(method, endpoint, {})
            else:
                response = make_request(method, endpoint)
            
            print(f"✅ {permission}: РАБОТАЕТ")
            
        except Exception as e:
            if "401" in str(e):
                print(f"❌ {permission}: НЕТ РАЗРЕШЕНИЙ")
            elif "403" in str(e):
                print(f"🚫 {permission}: ЗАПРЕЩЕНО")
            else:
                print(f"❓ {permission}: ОШИБКА - {e}")

if __name__ == "__main__":
    success = test_auth_system()
    
    if success:
        test_permissions()
        
        print("\n📋 РЕКОМЕНДАЦИИ:")
        print("1. Если все тесты прошли - система работает отлично!")
        print("2. Если есть ошибки разрешений - включите их в Developer Console")
        print("3. Система автоматически обновляет токены при необходимости")
        print("4. Используйте только JWT и refresh token авторизацию")
    else:
        print("\n💥 СИСТЕМА НЕ РАБОТАЕТ!")
        print("1. Проверьте переменные окружения в .env")
        print("2. Убедитесь что JWT токен действителен")
        print("3. Проверьте client_id и client_secret")
        print("4. Password авторизация больше не поддерживается")
