"""
RingCentral API Client с JWT авторизацией
Обрабатывает авторизацию, refresh tokens и API вызовы
"""

import asyncio
import logging
import os
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json

from ringcentral import SDK
from ringcentral.http.api_exception import ApiException
import aiohttp
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class RingCentralClient:
    """
    Клиент для работы с RingCentral API
    Поддерживает JWT авторизацию и автоматическое обновление токенов
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация клиента
        
        Args:
            config: Конфигурация из Config.RINGCENTRAL
        """
        self.config = config
        self.sdk = SDK(
            config['client_id'],
            config['client_secret'],
            config['server']
        )
        self.platform = self.sdk.platform()
        self.token_expires_at = None
        self.subscription = None
        self._refresh_lock = asyncio.Lock()
        
        logger.info("RingCentral клиент инициализирован")
    
    async def authenticate(self) -> bool:
        """
        Аутентификация с использованием JWT токена
        
        Returns:
            bool: True если успешно, False если ошибка
        """
        try:
            # Получаем JWT токен из переменной окружения
            jwt_token = os.getenv('RINGCENTRAL_JWT_TOKEN')
            
            if not jwt_token:
                # Если нет JWT, пробуем логин/пароль (для обратной совместимости)
                logger.warning("JWT токен не найден, используем логин/пароль")
                self.platform.login(
                    username=self.config['username'],
                    password=self.config['password']
                )
            else:
                # Используем JWT для авторизации
                self.platform.login(jwt=jwt_token)
            
            # Получаем информацию о токене
            token_info = self.platform.auth().data()
            self.token_expires_at = time.time() + token_info.get('expires_in', 3600)
            
            logger.info("Успешная авторизация в RingCentral")
            return True
            
        except ApiException as e:
            logger.error(f"Ошибка авторизации RingCentral: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при авторизации: {e}")
            return False
    
    async def refresh_token(self) -> bool:
        """
        Обновление access токена используя refresh token
        
        Returns:
            bool: True если успешно обновлен
        """
        async with self._refresh_lock:
            try:
                # Проверяем, нужно ли обновлять токен
                if self.token_expires_at and time.time() < self.token_expires_at - 300:
                    return True
                
                logger.info("Обновляем access токен...")
                
                # Обновляем токен
                self.platform.refresh()
                
                # Обновляем время истечения
                token_info = self.platform.auth().data()
                self.token_expires_at = time.time() + token_info.get('expires_in', 3600)
                
                logger.info("Токен успешно обновлен")
                return True
                
            except ApiException as e:
                logger.error(f"Ошибка обновления токена: {e}")
                # Пробуем переавторизоваться
                return await self.authenticate()
            except Exception as e:
                logger.error(f"Неожиданная ошибка при обновлении токена: {e}")
                return False
    
    async def ensure_authenticated(self) -> bool:
        """
        Убедиться что клиент авторизован, обновить токен если нужно
        
        Returns:
            bool: True если авторизован
        """
        if not self.platform.logged_in():
            return await self.authenticate()
        
        # Проверяем срок действия токена
        if self.token_expires_at and time.time() >= self.token_expires_at - 300:
            return await self.refresh_token()
        
        return True
    
    async def create_webhook_subscription(self, event_filters: List[str], delivery_mode: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Создать webhook подписку для получения событий
        
        Args:
            event_filters: Список фильтров событий (например, ['/restapi/v1.0/account/~/extension/~/telephony/sessions'])
            delivery_mode: Настройки доставки webhook
            
        Returns:
            Dict с информацией о подписке или None при ошибке
        """
        try:
            await self.ensure_authenticated()
            
            # Подготавливаем данные для подписки
            subscription_data = {
                'eventFilters': event_filters,
                'deliveryMode': delivery_mode,
                'expiresIn': 86400  # 24 часа
            }
            
            logger.info(f"Создаем webhook подписку с фильтрами: {event_filters}")
            
            # Создаем подписку
            response = self.platform.post('/subscription', subscription_data)
            subscription_info = response.json()
            
            logger.info(f"Webhook подписка создана: {subscription_info['id']}")
            return subscription_info
            
        except ApiException as e:
            logger.error(f"Ошибка создания webhook подписки: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании подписки: {e}")
            return None
    
    async def get_call_session(self, telephony_session_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о звонковой сессии
        
        Args:
            telephony_session_id: ID телефонной сессии
            
        Returns:
            Информация о сессии или None
        """
        try:
            await self.ensure_authenticated()
            
            response = self.platform.get(
                f'/account/~/extension/~/telephony/sessions/{telephony_session_id}'
            )
            
            return response.json()
            
        except ApiException as e:
            logger.error(f"Ошибка получения информации о сессии {telephony_session_id}: {e}")
            return None
    
    async def answer_call(self, telephony_session_id: str, party_id: str) -> bool:
        """
        Ответить на входящий звонок
        
        Args:
            telephony_session_id: ID телефонной сессии
            party_id: ID участника звонка
            
        Returns:
            bool: True если успешно
        """
        try:
            await self.ensure_authenticated()
            
            response = self.platform.post(
                f'/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/answer'
            )
            
            logger.info(f"Звонок {telephony_session_id} принят")
            return True
            
        except ApiException as e:
            logger.error(f"Ошибка при ответе на звонок: {e}")
            return False
    
    async def transfer_call(self, telephony_session_id: str, party_id: str, 
                          transfer_to: str, transfer_type: str = 'blind') -> bool:
        """
        Перевести звонок на другой номер
        
        Args:
            telephony_session_id: ID телефонной сессии
            party_id: ID участника звонка
            transfer_to: Номер для перевода
            transfer_type: Тип перевода ('blind' или 'attended')
            
        Returns:
            bool: True если успешно
        """
        try:
            await self.ensure_authenticated()
            
            transfer_data = {
                'phoneNumber': transfer_to,
                'transferType': transfer_type
            }
            
            response = self.platform.post(
                f'/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/transfer',
                transfer_data
            )
            
            logger.info(f"Звонок {telephony_session_id} переведен на {transfer_to}")
            return True
            
        except ApiException as e:
            logger.error(f"Ошибка при переводе звонка: {e}")
            return False
    
    async def forward_call(self, telephony_session_id: str, party_id: str, forward_to: str) -> bool:
        """
        Переадресовать звонок
        
        Args:
            telephony_session_id: ID телефонной сессии
            party_id: ID участника звонка
            forward_to: Номер для переадресации
            
        Returns:
            bool: True если успешно
        """
        try:
            await self.ensure_authenticated()
            
            forward_data = {
                'phoneNumber': forward_to
            }
            
            response = self.platform.post(
                f'/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/forward',
                forward_data
            )
            
            logger.info(f"Звонок {telephony_session_id} переадресован на {forward_to}")
            return True
            
        except ApiException as e:
            logger.error(f"Ошибка при переадресации звонка: {e}")
            return False
    
    async def hangup_call(self, telephony_session_id: str, party_id: str) -> bool:
        """
        Завершить звонок
        
        Args:
            telephony_session_id: ID телефонной сессии
            party_id: ID участника звонка
            
        Returns:
            bool: True если успешно
        """
        try:
            await self.ensure_authenticated()
            
            response = self.platform.delete(
                f'/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}'
            )
            
            logger.info(f"Звонок {telephony_session_id} завершен")
            return True
            
        except ApiException as e:
            logger.error(f"Ошибка при завершении звонка: {e}")
            return False
    
    async def hold_call(self, telephony_session_id: str, party_id: str) -> bool:
        """
        Поставить звонок на удержание
        
        Args:
            telephony_session_id: ID телефонной сессии
            party_id: ID участника звонка
            
        Returns:
            bool: True если успешно
        """
        try:
            await self.ensure_authenticated()
            
            response = self.platform.post(
                f'/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/hold'
            )
            
            logger.info(f"Звонок {telephony_session_id} поставлен на удержание")
            return True
            
        except ApiException as e:
            logger.error(f"Ошибка при постановке звонка на удержание: {e}")
            return False
    
    async def unhold_call(self, telephony_session_id: str, party_id: str) -> bool:
        """
        Снять звонок с удержания
        
        Args:
            telephony_session_id: ID телефонной сессии
            party_id: ID участника звонка
            
        Returns:
            bool: True если успешно
        """
        try:
            await self.ensure_authenticated()
            
            response = self.platform.post(
                f'/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/unhold'
            )
            
            logger.info(f"Звонок {telephony_session_id} снят с удержания")
            return True
            
        except ApiException as e:
            logger.error(f"Ошибка при снятии звонка с удержания: {e}")
            return False
    
    async def send_dtmf(self, telephony_session_id: str, party_id: str, dtmf_string: str) -> bool:
        """
        Отправить DTMF тоны в звонок
        
        Args:
            telephony_session_id: ID телефонной сессии
            party_id: ID участника звонка
            dtmf_string: Строка DTMF тонов (0-9, *, #)
            
        Returns:
            bool: True если успешно
        """
        try:
            await self.ensure_authenticated()
            
            dtmf_data = {
                'dtmf': dtmf_string
            }
            
            response = self.platform.post(
                f'/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/send-dtmf',
                dtmf_data
            )
            
            logger.info(f"DTMF '{dtmf_string}' отправлен в звонок {telephony_session_id}")
            return True
            
        except ApiException as e:
            logger.error(f"Ошибка при отправке DTMF: {e}")
            return False
    
    async def get_extension_info(self) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о текущем extension
        
        Returns:
            Информация об extension или None
        """
        try:
            await self.ensure_authenticated()
            
            response = self.platform.get('/account/~/extension/~')
            return response.json()
            
        except ApiException as e:
            logger.error(f"Ошибка получения информации об extension: {e}")
            return None
    
    async def validate_webhook_token(self, validation_token: str, webhook_secret: str) -> str:
        """
        Валидировать webhook token при установке подписки
        
        Args:
            validation_token: Токен валидации от RingCentral
            webhook_secret: Секрет webhook из конфигурации
            
        Returns:
            Ответ для валидации
        """
        import hashlib
        import hmac
        
        # Создаем HMAC подпись
        signature = hmac.new(
            webhook_secret.encode('utf-8'),
            validation_token.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def close(self):
        """Закрыть соединения и очистить ресурсы"""
        try:
            if self.subscription:
                self.subscription.cancel()
            logger.info("RingCentral клиент закрыт")
        except Exception as e:
            logger.error(f"Ошибка при закрытии клиента: {e}")


# Глобальный экземпляр клиента
_client_instance = None


def get_ringcentral_client(config: Dict[str, Any]) -> RingCentralClient:
    """
    Получить или создать экземпляр RingCentral клиента
    
    Args:
        config: Конфигурация из Config.RINGCENTRAL
        
    Returns:
        RingCentralClient: Экземпляр клиента
    """
    global _client_instance
    
    if _client_instance is None:
        _client_instance = RingCentralClient(config)
    
    return _client_instance