import os
import logging
from ringcentral_auth import make_request, authenticate, get_auth_status

logger = logging.getLogger(__name__)

class RingCentralClient:
    def __init__(self):
        self._initialize()
    
    def _initialize(self):
        """Initialize RingCentral with universal authentication"""
        try:
            logger.info("🔐 Initializing RingCentral client...")
            
            # Авторизуемся
            if not authenticate():
                raise Exception("Failed to authenticate with RingCentral")
            
            # Получаем статус
            status = get_auth_status()
            logger.info(f"✅ RingCentral client ready - Auth method: {status['auth_method']}")
            
        except Exception as e:
            logger.error(f"❌ RingCentral initialization failed: {e}")
            raise Exception(f"RingCentral initialization error: {e}")
    
    def make_authenticated_request(self, method, endpoint, data=None):
        """Make authenticated request using universal auth system"""
        return make_request(method, endpoint, data)

# Глобальный экземпляр
_ringcentral_client = None

def get_ringcentral_client():
    """Get RingCentral client instance"""
    global _ringcentral_client
    if _ringcentral_client is None:
        _ringcentral_client = RingCentralClient()
    return _ringcentral_client

def get_ringcentral_platform():
    """Get RingCentral platform instance - DEPRECATED, use get_ringcentral_client()"""
    return get_ringcentral_client()

def make_ringcentral_request(method, endpoint, data=None):
    """Make authenticated RingCentral API request"""
    client = get_ringcentral_client()
    return client.make_authenticated_request(method, endpoint, data)

def test_ringcentral_connection():
    """Test RingCentral connection without requiring special permissions"""
    try:
        # Простой тест - получение информации о сервисе (не требует особых разрешений)
        response = make_ringcentral_request('GET', '/restapi/v1.0')
        logger.info(f"✅ RingCentral connection test successful: {response.get('serverVersion', 'Unknown')}")
        return True
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        return False