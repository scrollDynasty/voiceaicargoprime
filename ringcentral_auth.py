#!/usr/bin/env python3
"""
Универсальная система авторизации RingCentral
Поддерживает JWT и автоматическое обновление токенов
"""

import os
import time
import requests
import logging
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

class RingCentralAuth:
    """Универсальная система авторизации RingCentral"""
    
    def __init__(self):
        self.client_id = os.getenv('RINGCENTRAL_CLIENT_ID')
        self.client_secret = os.getenv('RINGCENTRAL_CLIENT_SECRET')
        self.server_url = os.getenv('RINGCENTRAL_SERVER', 'https://platform.ringcentral.com')
        
        # Токены
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        # JWT токен (если есть)
        self.jwt_token = os.getenv('RINGCENTRAL_JWT_TOKEN')
        
        # Статус авторизации
        self.is_authenticated = False
        self.auth_method = None
        
        # Проверяем конфигурацию
        self._validate_config()
    
    def _validate_config(self):
        """Проверяем конфигурацию"""
        if not self.client_id or not self.client_secret:
            raise Exception("RINGCENTRAL_CLIENT_ID и RINGCENTRAL_CLIENT_SECRET обязательны")
        
        logger.info("🔐 RingCentral Auth initialized")
        logger.info(f"🌐 Server: {self.server_url}")
        logger.info(f"🔑 Client ID: {self.client_id[:10]}...")
    
    def authenticate(self):
        """Основная функция авторизации с fallback"""
        try:
            # Пробуем JWT авторизацию
            if self.jwt_token and self._try_jwt_auth():
                self.auth_method = "jwt"
                logger.info("✅ Авторизация через JWT успешна")
                return True
            
            # Fallback на OAuth с refresh token
            if self._try_refresh_token():
                self.auth_method = "refresh_token"
                logger.info("✅ Авторизация через refresh token успешна")
                return True
            
            logger.error("❌ JWT и refresh token авторизация не удались")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка авторизации: {e}")
            return False
    
    def _try_jwt_auth(self):
        """Пробуем JWT авторизацию согласно официальной документации"""
        try:
            logger.info("🔑 Пробуем JWT авторизацию...")
            
            # Проверяем JWT токен
            if not self._is_jwt_valid():
                logger.warning("⚠️ JWT токен недействителен или истек")
                return False
            
            # ✅ ПРАВИЛЬНЫЙ JWT FLOW согласно документации:
            # 1. Обмениваем JWT на access token через OAuth endpoint
            
            import base64
            
            # Создаем Basic Auth header
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {encoded_credentials}'
            }
            
            data = {
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion': self.jwt_token
            }
            
            logger.info("🔄 Обмениваем JWT на access token...")
            response = requests.post(
                f"{self.server_url}/restapi/oauth/token",
                headers=headers,
                data=data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                self.refresh_token = token_data.get('refresh_token')
                self.token_expires_at = time.time() + token_data['expires_in']
                self.is_authenticated = True
                
                logger.info("✅ JWT обмен на access token успешен")
                logger.info(f"📋 Scope: {token_data.get('scope', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ Ошибка обмена JWT: {response.status_code}")
                logger.error(f"Ответ: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка JWT авторизации: {e}")
            return False
    
    def _is_jwt_valid(self):
        """Проверяем валидность JWT токена"""
        try:
            import base64
            import json
            
            parts = self.jwt_token.split('.')
            if len(parts) != 3:
                return False
            
            # Декодируем payload
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            
            decoded = base64.urlsafe_b64decode(payload)
            payload_data = json.loads(decoded.decode('utf-8'))
            
            # Проверяем срок действия
            exp_timestamp = payload_data.get('exp')
            if not exp_timestamp:
                return False
            
            current_time = int(time.time())
            return exp_timestamp > current_time
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки JWT: {e}")
            return False
    
    def _try_refresh_token(self):
        """Пробуем обновить токен через refresh_token"""
        try:
            refresh_token = os.getenv('RINGCENTRAL_REFRESH_TOKEN')
            if not refresh_token:
                logger.info("📝 Refresh token не найден")
                return False
            
            logger.info("🔄 Пробуем обновить токен...")
            
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(f"{self.server_url}/restapi/oauth/token", data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                self.refresh_token = token_data.get('refresh_token', refresh_token)
                self.token_expires_at = time.time() + token_data['expires_in']
                self.is_authenticated = True
                
                # Сохраняем новый refresh token
                self._save_refresh_token(self.refresh_token)
                
                logger.info("✅ Токен успешно обновлен")
                return True
            else:
                logger.warning(f"⚠️ Не удалось обновить токен: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления токена: {e}")
            return False
    

    
    def _save_refresh_token(self, refresh_token):
        """Сохраняем refresh token в .env файл"""
        try:
            env_file = '.env'
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    lines = f.readlines()
                
                # Ищем строку с RINGCENTRAL_REFRESH_TOKEN
                found = False
                for i, line in enumerate(lines):
                    if line.startswith('RINGCENTRAL_REFRESH_TOKEN='):
                        lines[i] = f'RINGCENTRAL_REFRESH_TOKEN={refresh_token}\n'
                        found = True
                        break
                
                # Если не нашли, добавляем
                if not found:
                    lines.append(f'RINGCENTRAL_REFRESH_TOKEN={refresh_token}\n')
                
                with open(env_file, 'w') as f:
                    f.writelines(lines)
                
                logger.info("💾 Refresh token сохранен в .env")
                
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сохранить refresh token: {e}")
    
    def make_request(self, method, endpoint, data=None):
        """Выполняем авторизованный запрос"""
        if not self.is_authenticated:
            if not self.authenticate():
                raise Exception("Не удалось авторизоваться")
        
        # Проверяем, не истек ли токен
        if self.token_expires_at and time.time() > self.token_expires_at - 300:  # 5 минут до истечения
            logger.info("🔄 Токен скоро истечет, обновляем...")
            if not self._try_refresh_token():
                if not self.authenticate():
                    raise Exception("Не удалось обновить токен")
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.server_url}{endpoint}"
        
        logger.info(f"🌐 {method} {endpoint}")
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                raise Exception(f"Неподдерживаемый метод: {method}")
            
            response.raise_for_status()
            logger.info(f"✅ Запрос успешен: {response.status_code}")
            
            return response.json() if response.content else None
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка: {e}")
            if e.response is not None:
                logger.error(f"Ответ: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка запроса: {e}")
            raise
    
    def get_auth_status(self):
        """Получаем статус авторизации"""
        return {
            'is_authenticated': self.is_authenticated,
            'auth_method': self.auth_method,
            'server_url': self.server_url,
            'client_id': self.client_id[:10] + '...' if self.client_id else None,
            'token_expires_at': self.token_expires_at,
            'has_jwt': bool(self.jwt_token),
            'has_refresh_token': bool(self.refresh_token)
        }

# Глобальный экземпляр
_auth_instance = None

def get_auth():
    """Получаем экземпляр авторизации"""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = RingCentralAuth()
    return _auth_instance

def authenticate():
    """Авторизация"""
    auth = get_auth()
    return auth.authenticate()

def make_request(method, endpoint, data=None):
    """Выполняем авторизованный запрос"""
    auth = get_auth()
    return auth.make_request(method, endpoint, data)

def get_auth_status():
    """Получаем статус авторизации"""
    auth = get_auth()
    return auth.get_auth_status()
