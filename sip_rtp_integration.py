#!/usr/bin/env python3
"""
SIP/RTP интеграция для RingCentral с real-time обработкой звонков
Использует pjsua2 для прямой работы с SIP и RTP потоками
"""

import os
import sys
import time
import logging
import threading
import queue
import numpy as np
from typing import Optional, Dict, Any, Callable
import pjsua2 as pj

from config import Config
from speech_processor import speech_processor
from llm_handler import llm_handler

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioProcessor(pj.AudioMediaPort):
    """
    Обработчик аудио потока в реальном времени
    Получает RTP пакеты и передает их в AI систему
    """
    
    def __init__(self, call_handler):
        pj.AudioMediaPort.__init__(self)
        self.call_handler = call_handler
        self.createPort("audio_processor", 16000)
        
        # Буферы для аудио
        self.incoming_buffer = bytearray()
        self.outgoing_queue = queue.Queue()
        
        # Параметры обработки
        self.chunk_size = 16000  # 1 секунда аудио при 16kHz
        self.processing = False
        
    def onFrameRequested(self, frame):
        """
        Callback для исходящего аудио (от AI к собеседнику)
        Вызывается когда SIP стек запрашивает аудио для отправки
        """
        try:
            # Получаем аудио из очереди AI ответов
            if not self.outgoing_queue.empty():
                audio_data = self.outgoing_queue.get_nowait()
                
                # Конвертируем в формат pjsua
                if len(audio_data) >= frame.size * 2:
                    frame.buf = audio_data[:frame.size * 2]
                else:
                    # Дополняем тишиной если данных недостаточно
                    frame.buf = audio_data + b'\x00' * (frame.size * 2 - len(audio_data))
            else:
                # Если нет данных - отправляем тишину
                frame.buf = b'\x00' * frame.size * 2
                
        except Exception as e:
            logger.error(f"Ошибка в onFrameRequested: {e}")
            frame.buf = b'\x00' * frame.size * 2
    
    def onFrameReceived(self, frame):
        """
        Callback для входящего аудио (от собеседника к AI)
        Вызывается когда получен RTP пакет с аудио
        """
        try:
            # Добавляем аудио в буфер
            self.incoming_buffer.extend(frame.buf)
            
            # Если накопилось достаточно данных - обрабатываем
            if len(self.incoming_buffer) >= self.chunk_size * 2 and not self.processing:
                self.processing = True
                
                # Копируем данные для обработки
                audio_chunk = bytes(self.incoming_buffer[:self.chunk_size * 2])
                self.incoming_buffer = self.incoming_buffer[self.chunk_size * 2:]
                
                # Запускаем обработку в отдельном потоке
                threading.Thread(
                    target=self._process_audio_chunk,
                    args=(audio_chunk,),
                    daemon=True
                ).start()
                
        except Exception as e:
            logger.error(f"Ошибка в onFrameReceived: {e}")
    
    def _process_audio_chunk(self, audio_data: bytes):
        """Обработка аудио чанка через AI"""
        try:
            # 1. Конвертируем байты в numpy array (16-bit PCM)
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # 2. Распознаем речь (STT)
            text = speech_processor.transcribe_audio(audio_array)
            
            if text and text.strip():
                logger.info(f"📝 Распознано: {text}")
                
                # 3. Получаем ответ от AI
                ai_response = llm_handler.get_response(text)
                logger.info(f"🤖 AI ответ: {ai_response}")
                
                # 4. Синтезируем речь (TTS)
                response_audio = speech_processor.synthesize_speech(ai_response)
                
                # 5. Добавляем в очередь для отправки
                if response_audio is not None:
                    # Конвертируем в байты для отправки
                    audio_bytes = response_audio.astype(np.int16).tobytes()
                    
                    # Разбиваем на небольшие чанки для плавной передачи
                    chunk_size = 320  # 20ms при 16kHz
                    for i in range(0, len(audio_bytes), chunk_size):
                        chunk = audio_bytes[i:i + chunk_size]
                        self.outgoing_queue.put(chunk)
                        
        except Exception as e:
            logger.error(f"Ошибка обработки аудио: {e}")
        finally:
            self.processing = False
    
    def send_audio(self, audio_data: bytes):
        """Отправить аудио в исходящий поток"""
        self.outgoing_queue.put(audio_data)


class AICallHandler(pj.Call):
    """
    Обработчик SIP звонков с AI интеграцией
    """
    
    def __init__(self, account, call_id=pj.PJSUA_INVALID_ID):
        pj.Call.__init__(self, account, call_id)
        self.audio_processor = None
        self.call_info = None
        
    def onCallState(self, prm):
        """Callback изменения состояния звонка"""
        ci = self.getInfo()
        self.call_info = ci
        
        logger.info(f"📞 Состояние звонка: {ci.stateText} ({ci.state})")
        
        if ci.state == pj.PJSIP_INV_STATE_CONFIRMED:
            # Звонок установлен - подключаем аудио обработку
            self._setup_audio_processing()
            
        elif ci.state == pj.PJSIP_INV_STATE_DISCONNECTED:
            # Звонок завершен
            logger.info(f"📞 Звонок завершен: {ci.lastReason}")
            
    def onCallMediaState(self, prm):
        """Callback изменения медиа состояния"""
        ci = self.getInfo()
        
        for mi in ci.media:
            if mi.type == pj.PJMEDIA_TYPE_AUDIO and mi.status == pj.PJSUA_CALL_MEDIA_ACTIVE:
                # Аудио канал активен
                logger.info("🔊 Аудио канал активен")
                
                # Получаем аудио медиа
                audio_media = self.getAudioMedia(mi.index)
                
                if self.audio_processor:
                    # Подключаем аудио процессор к звонку
                    audio_media.startTransmit(self.audio_processor)
                    self.audio_processor.startTransmit(audio_media)
                    
                    logger.info("✅ AI аудио процессор подключен к звонку")
    
    def _setup_audio_processing(self):
        """Настройка обработки аудио"""
        try:
            # Создаем аудио процессор
            self.audio_processor = AudioProcessor(self)
            
            # Отправляем приветствие
            greeting = self._generate_greeting()
            greeting_audio = speech_processor.synthesize_speech(greeting)
            
            if greeting_audio is not None:
                audio_bytes = greeting_audio.astype(np.int16).tobytes()
                self.audio_processor.send_audio(audio_bytes)
                
        except Exception as e:
            logger.error(f"Ошибка настройки аудио обработки: {e}")
    
    def _generate_greeting(self) -> str:
        """Генерация приветствия"""
        caller_number = self.call_info.remoteUri if self.call_info else "Unknown"
        
        return (
            "Hello! Thank you for calling Prime Cargo Logistics. "
            "I'm your AI assistant. How can I help you today?"
        )


class SIPServer:
    """
    SIP сервер для обработки звонков через RingCentral
    """
    
    def __init__(self):
        self.ep = None
        self.account = None
        self.transport = None
        
        # Конфигурация SIP
        self.sip_config = {
            'domain': 'sip.ringcentral.com',
            'username': Config.RINGCENTRAL.get('sip_username', ''),
            'password': Config.RINGCENTRAL.get('sip_password', ''),
            'port': 5060,
            'transport': 'UDP'
        }
        
    def start(self):
        """Запуск SIP сервера"""
        try:
            # Создаем endpoint
            self.ep = pj.Endpoint()
            self.ep.libCreate()
            
            # Конфигурация endpoint
            ep_cfg = pj.EpConfig()
            ep_cfg.logConfig.level = 3
            ep_cfg.logConfig.consoleLevel = 3
            
            self.ep.libInit(ep_cfg)
            
            # Создаем транспорт
            if self.sip_config['transport'] == 'UDP':
                self.transport = self.ep.transportCreate(
                    pj.PJSIP_TRANSPORT_UDP,
                    pj.TransportConfig()
                )
            else:
                tls_cfg = pj.TransportConfig()
                tls_cfg.port = 5061
                self.transport = self.ep.transportCreate(
                    pj.PJSIP_TRANSPORT_TLS,
                    tls_cfg
                )
            
            # Запускаем endpoint
            self.ep.libStart()
            logger.info("✅ SIP Endpoint запущен")
            
            # Создаем SIP аккаунт
            self._create_account()
            
            logger.info(f"✅ SIP сервер запущен на порту {self.sip_config['port']}")
            
        except Exception as e:
            logger.error(f"Ошибка запуска SIP сервера: {e}")
            raise
    
    def _create_account(self):
        """Создание SIP аккаунта для RingCentral"""
        try:
            # Конфигурация аккаунта
            acc_cfg = pj.AccountConfig()
            
            # SIP URI
            acc_cfg.idUri = f"sip:{self.sip_config['username']}@{self.sip_config['domain']}"
            
            # Регистрация
            acc_cfg.regConfig.registrarUri = f"sip:{self.sip_config['domain']}"
            acc_cfg.regConfig.registerOnAdd = True
            
            # Аутентификация
            if self.sip_config['username'] and self.sip_config['password']:
                cred = pj.AuthCredInfo()
                cred.scheme = "digest"
                cred.realm = "*"
                cred.username = self.sip_config['username']
                cred.data = self.sip_config['password']
                acc_cfg.sipConfig.authCreds.append(cred)
            
            # Создаем аккаунт с нашим обработчиком
            self.account = AIAccount()
            self.account.create(acc_cfg)
            
            logger.info(f"✅ SIP аккаунт создан: {acc_cfg.idUri}")
            
        except Exception as e:
            logger.error(f"Ошибка создания SIP аккаунта: {e}")
            raise
    
    def stop(self):
        """Остановка SIP сервера"""
        try:
            if self.account:
                self.account.shutdown()
                
            if self.ep:
                self.ep.libDestroy()
                
            logger.info("✅ SIP сервер остановлен")
            
        except Exception as e:
            logger.error(f"Ошибка остановки SIP сервера: {e}")


class AIAccount(pj.Account):
    """
    SIP аккаунт с AI обработкой входящих звонков
    """
    
    def onRegState(self, prm):
        """Callback состояния регистрации"""
        info = self.getInfo()
        logger.info(f"📝 Регистрация: {info.regStatus} {info.regStatusText}")
        
    def onIncomingCall(self, prm):
        """Callback входящего звонка"""
        call = AICallHandler(self, prm.callId)
        ci = call.getInfo()
        
        logger.info(f"📞 Входящий звонок от: {ci.remoteUri}")
        
        # Автоматически отвечаем на звонок
        op = pj.CallOpParam()
        op.statusCode = 200  # OK
        call.answer(op)
        
        logger.info("✅ Звонок принят автоматически")


# Глобальный экземпляр
sip_server = None


def start_sip_server():
    """Запустить SIP сервер"""
    global sip_server
    
    try:
        sip_server = SIPServer()
        sip_server.start()
        
        # Держим сервер активным
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Остановка SIP сервера...")
        if sip_server:
            sip_server.stop()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        if sip_server:
            sip_server.stop()


if __name__ == "__main__":
    # Запуск SIP сервера
    start_sip_server()