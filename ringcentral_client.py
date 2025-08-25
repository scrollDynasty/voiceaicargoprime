import os
import logging
from ringcentral import SDK

logger = logging.getLogger(__name__)

class RingCentralClient:
    def __init__(self):
        self.platform = None
        self._initialize()
    
    def _initialize(self):
        """Initialize RingCentral with JWT authentication ONLY"""
        try:
            # Загружаем конфигурацию
            client_id = os.getenv('RINGCENTRAL_CLIENT_ID')
            client_secret = os.getenv('RINGCENTRAL_CLIENT_SECRET')
            server = os.getenv('RINGCENTRAL_SERVER', 'https://platform.ringcentral.com')
            jwt_token = os.getenv('RINGCENTRAL_JWT_TOKEN')
            
            # Проверяем обязательные параметры
            if not client_id:
                raise Exception("RINGCENTRAL_CLIENT_ID not found in .env")
            if not client_secret:
                raise Exception("RINGCENTRAL_CLIENT_SECRET not found in .env")
            if not jwt_token:
                raise Exception("RINGCENTRAL_JWT_TOKEN not found in .env")
            
            logger.info("🔐 Initializing RingCentral SDK...")
            
            # Инициализация SDK
            rcsdk = SDK(client_id, client_secret, server)
            self.platform = rcsdk.platform()
            
            # ТОЛЬКО JWT авторизация - НЕТ НИКАКИХ ТЕСТОВЫХ ВЫЗОВОВ
            logger.info("🔑 Authenticating with JWT token...")
            self.platform.login({'jwt': jwt_token})
            
            logger.info("✅ RingCentral JWT authentication successful!")
            logger.info("🎯 Platform ready for webhook operations")
            
        except Exception as e:
            logger.error(f"❌ RingCentral initialization failed: {e}")
            raise Exception(f"RingCentral authentication error: {e}")
    
    def get_platform(self):
        """Get authenticated platform instance"""
        if not self.platform:
            raise Exception("RingCentral not initialized")
        return self.platform

# Глобальный экземпляр
_ringcentral_client = None

def get_ringcentral_platform():
    """Get RingCentral platform instance - создается только один раз"""
    global _ringcentral_client
    if _ringcentral_client is None:
        _ringcentral_client = RingCentralClient()
    return _ringcentral_client.get_platform()

# УДАЛИ ВСЕ СТАРЫЕ ФУНКЦИИ:
# - authenticate_ringcentral_jwt()
# - authenticate_ringcentral_fallback()
# - init_ringcentral()
# - test_ringcentral_auth()