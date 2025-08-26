"""
WebRTC Integration for RingCentral Voice AI
Обеспечивает real-time audio streaming для AI взаимодействия
"""

import logging
import asyncio
import json
import websockets
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import threading
import queue
import time

from config import Config
from ringcentral_auth import make_request

logger = logging.getLogger(__name__)

class WebRTCState(Enum):
    """Состояния WebRTC соединения"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"
    CLOSED = "closed"

@dataclass
class WebRTCSession:
    """WebRTC сессия"""
    session_id: str
    telephony_session_id: str
    party_id: str
    websocket_url: Optional[str] = None
    state: WebRTCState = WebRTCState.DISCONNECTED
    audio_in_queue: queue.Queue = None
    audio_out_queue: queue.Queue = None
    
    def __post_init__(self):
        self.audio_in_queue = queue.Queue()
        self.audio_out_queue = queue.Queue()

class WebRTCManager:
    """Менеджер WebRTC соединений для RingCentral"""
    
    def __init__(self):
        self.sessions: Dict[str, WebRTCSession] = {}
        self.ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.audio_callback: Optional[Callable] = None
        
    async def create_webrtc_session(self, telephony_session_id: str, party_id: str) -> WebRTCSession:
        """
        Создать новую WebRTC сессию для звонка
        
        Args:
            telephony_session_id: ID телефонной сессии
            party_id: ID участника
            
        Returns:
            WebRTCSession: Созданная сессия
        """
        try:
            logger.info(f"🌐 Создание WebRTC сессии для звонка {telephony_session_id}")
            
            # Запрос на создание WebRTC сессии через RingCentral API
            response = make_request(
                'POST',
                f'/restapi/v1.0/account/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/webrtc',
                {
                    'audio': {
                        'mode': 'bidirectional',  # Двусторонняя передача аудио
                        'codecs': ['PCMU', 'PCMA', 'opus']  # Поддерживаемые кодеки
                    }
                }
            )
            
            # Извлекаем данные подключения
            session_id = response.get('id')
            websocket_url = response.get('websocketUrl')
            
            # Создаем сессию
            session = WebRTCSession(
                session_id=session_id,
                telephony_session_id=telephony_session_id,
                party_id=party_id,
                websocket_url=websocket_url
            )
            
            self.sessions[session_id] = session
            
            logger.info(f"✅ WebRTC сессия создана: {session_id}")
            return session
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания WebRTC сессии: {str(e)}")
            raise
    
    async def connect_session(self, session: WebRTCSession) -> bool:
        """
        Подключиться к WebRTC сессии
        
        Args:
            session: WebRTC сессия
            
        Returns:
            bool: True если подключение успешно
        """
        try:
            if not session.websocket_url:
                logger.error("❌ Нет WebSocket URL для подключения")
                return False
                
            logger.info(f"🔌 Подключение к WebSocket: {session.websocket_url}")
            
            session.state = WebRTCState.CONNECTING
            
            # Подключаемся к WebSocket
            ws = await websockets.connect(session.websocket_url)
            self.ws_connections[session.session_id] = ws
            
            session.state = WebRTCState.CONNECTED
            logger.info(f"✅ WebSocket подключен для сессии {session.session_id}")
            
            # Запускаем обработку сообщений
            asyncio.create_task(self._handle_websocket_messages(session, ws))
            
            # Запускаем отправку аудио
            asyncio.create_task(self._send_audio_stream(session, ws))
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения WebSocket: {str(e)}")
            session.state = WebRTCState.FAILED
            return False
    
    async def _handle_websocket_messages(self, session: WebRTCSession, ws: websockets.WebSocketClientProtocol):
        """Обработка входящих сообщений WebSocket"""
        try:
            async for message in ws:
                try:
                    # Парсим сообщение
                    if isinstance(message, bytes):
                        # Это аудио данные
                        session.audio_in_queue.put(message)
                        
                        # Вызываем callback если установлен
                        if self.audio_callback:
                            self.audio_callback(session.session_id, message)
                    else:
                        # Это JSON сообщение
                        data = json.loads(message)
                        await self._handle_control_message(session, data)
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки сообщения: {str(e)}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 WebSocket соединение закрыто для сессии {session.session_id}")
            session.state = WebRTCState.CLOSED
        except Exception as e:
            logger.error(f"❌ Ошибка в обработчике WebSocket: {str(e)}")
            session.state = WebRTCState.FAILED
    
    async def _send_audio_stream(self, session: WebRTCSession, ws: websockets.WebSocketClientProtocol):
        """Отправка аудио потока через WebSocket"""
        try:
            while session.state == WebRTCState.CONNECTED:
                try:
                    # Получаем аудио из очереди (с таймаутом)
                    audio_data = await asyncio.get_event_loop().run_in_executor(
                        None, session.audio_out_queue.get, True, 0.1
                    )
                    
                    # Отправляем аудио
                    await ws.send(audio_data)
                    
                except queue.Empty:
                    # Нет данных для отправки
                    await asyncio.sleep(0.01)
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки аудио: {str(e)}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в потоке отправки аудио: {str(e)}")
    
    async def _handle_control_message(self, session: WebRTCSession, message: Dict[str, Any]):
        """Обработка управляющих сообщений"""
        msg_type = message.get('type')
        
        if msg_type == 'connected':
            logger.info(f"✅ WebRTC соединение установлено для сессии {session.session_id}")
        elif msg_type == 'disconnected':
            logger.info(f"🔌 WebRTC соединение разорвано для сессии {session.session_id}")
            session.state = WebRTCState.DISCONNECTED
        elif msg_type == 'error':
            logger.error(f"❌ WebRTC ошибка: {message.get('error')}")
            session.state = WebRTCState.FAILED
        else:
            logger.debug(f"📨 Получено сообщение: {message}")
    
    def send_audio(self, session_id: str, audio_data: bytes) -> bool:
        """
        Отправить аудио в сессию
        
        Args:
            session_id: ID сессии
            audio_data: Аудио данные для отправки
            
        Returns:
            bool: True если данные добавлены в очередь
        """
        session = self.sessions.get(session_id)
        if not session or session.state != WebRTCState.CONNECTED:
            logger.warning(f"⚠️ Сессия {session_id} не найдена или не подключена")
            return False
            
        try:
            session.audio_out_queue.put(audio_data)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления аудио в очередь: {str(e)}")
            return False
    
    def get_audio(self, session_id: str, timeout: float = 0.1) -> Optional[bytes]:
        """
        Получить аудио из сессии
        
        Args:
            session_id: ID сессии
            timeout: Таймаут ожидания данных
            
        Returns:
            Optional[bytes]: Аудио данные или None
        """
        session = self.sessions.get(session_id)
        if not session:
            return None
            
        try:
            return session.audio_in_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def set_audio_callback(self, callback: Callable[[str, bytes], None]):
        """
        Установить callback для обработки входящего аудио
        
        Args:
            callback: Функция callback(session_id, audio_data)
        """
        self.audio_callback = callback
    
    async def disconnect_session(self, session_id: str):
        """
        Отключить WebRTC сессию
        
        Args:
            session_id: ID сессии
        """
        session = self.sessions.get(session_id)
        if not session:
            return
            
        logger.info(f"🔌 Отключение WebRTC сессии {session_id}")
        
        # Закрываем WebSocket
        ws = self.ws_connections.get(session_id)
        if ws:
            await ws.close()
            del self.ws_connections[session_id]
        
        # Обновляем состояние
        session.state = WebRTCState.DISCONNECTED
        
        # Удаляем сессию
        del self.sessions[session_id]

# Глобальный экземпляр менеджера
webrtc_manager = WebRTCManager()

async def setup_webrtc_for_call(telephony_session_id: str, party_id: str) -> Optional[str]:
    """
    Настроить WebRTC для звонка
    
    Args:
        telephony_session_id: ID телефонной сессии
        party_id: ID участника
        
    Returns:
        Optional[str]: ID WebRTC сессии или None
    """
    try:
        # Создаем WebRTC сессию
        session = await webrtc_manager.create_webrtc_session(telephony_session_id, party_id)
        
        # Подключаемся
        if await webrtc_manager.connect_session(session):
            return session.session_id
        else:
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка настройки WebRTC: {str(e)}")
        return None

def send_audio_to_webrtc(session_id: str, audio_data: bytes) -> bool:
    """
    Отправить аудио через WebRTC
    
    Args:
        session_id: ID WebRTC сессии
        audio_data: Аудио данные
        
    Returns:
        bool: True если успешно
    """
    return webrtc_manager.send_audio(session_id, audio_data)

def get_audio_from_webrtc(session_id: str, timeout: float = 0.1) -> Optional[bytes]:
    """
    Получить аудио из WebRTC
    
    Args:
        session_id: ID WebRTC сессии
        timeout: Таймаут ожидания
        
    Returns:
        Optional[bytes]: Аудио данные или None
    """
    return webrtc_manager.get_audio(session_id, timeout)

def set_webrtc_audio_callback(callback: Callable[[str, bytes], None]):
    """
    Установить callback для обработки входящего аудио
    
    Args:
        callback: Функция callback(session_id, audio_data)
    """
    webrtc_manager.set_audio_callback(callback)