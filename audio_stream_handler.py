"""
Audio Stream Handler
Обработка аудио потоков между WebPhone и Python Voice AI
"""

import asyncio
import json
import logging
import numpy as np
import websockets
from typing import Dict, Any, Optional, List
import threading
import queue
from datetime import datetime

from speech_processor import speech_processor, async_transcribe, async_synthesize
from llm_handler import generate_ai_response
from config import Config

logger = logging.getLogger(__name__)

class AudioStreamHandler:
    """Обработчик аудио потоков для WebPhone интеграции"""
    
    def __init__(self):
        """Инициализация обработчика аудио потоков"""
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.ws_server = None
        self.processing_queue = queue.Queue()
        self.is_running = False
        
        # Настройки аудио
        self.sample_rate = Config.SPEECH["sample_rate"]
        self.chunk_size = 1024
        self.silence_threshold = 0.01
        self.silence_duration = 1.5  # секунды тишины перед обработкой
        
    async def start_websocket_server(self, port: int = 8080):
        """Запуск WebSocket сервера для приема аудио от WebPhone"""
        logger.info(f"🌐 Запуск WebSocket сервера на порту {port}")
        
        async def handle_audio_stream(websocket, path):
            """Обработка входящего аудио потока"""
            # Извлекаем call_id из пути
            call_id = path.strip('/').split('/')[-1]
            logger.info(f"🔌 Новое WebSocket соединение для звонка {call_id}")
            
            # Создаем сессию для звонка
            stream_session = {
                'call_id': call_id,
                'websocket': websocket,
                'audio_buffer': bytearray(),
                'last_audio_time': datetime.now(),
                'conversation_history': [],
                'is_processing': False
            }
            
            self.active_streams[call_id] = stream_session
            
            try:
                async for message in websocket:
                    if isinstance(message, bytes):
                        # Добавляем аудио в буфер
                        stream_session['audio_buffer'].extend(message)
                        stream_session['last_audio_time'] = datetime.now()
                        
                        # Проверяем, достаточно ли аудио для обработки
                        if len(stream_session['audio_buffer']) >= self.sample_rate * 2:  # 2 секунды аудио
                            await self._process_audio_chunk(call_id)
                    else:
                        # Обработка текстовых команд
                        try:
                            data = json.loads(message)
                            await self._handle_command(call_id, data)
                        except json.JSONDecodeError:
                            logger.error(f"Неверный JSON: {message}")
                            
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"🔌 WebSocket соединение закрыто для звонка {call_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка в WebSocket для звонка {call_id}: {e}")
            finally:
                # Очистка ресурсов
                if call_id in self.active_streams:
                    del self.active_streams[call_id]
                logger.info(f"🧹 Ресурсы очищены для звонка {call_id}")
        
        # Запускаем сервер
        self.ws_server = await websockets.serve(
            handle_audio_stream,
            "localhost",
            port,
            ping_interval=20,
            ping_timeout=10
        )
        
        logger.info(f"✅ WebSocket сервер запущен на ws://localhost:{port}")
        self.is_running = True
        
    async def _process_audio_chunk(self, call_id: str):
        """Обработка аудио чанка"""
        session = self.active_streams.get(call_id)
        if not session or session['is_processing']:
            return
        
        session['is_processing'] = True
        
        try:
            # Извлекаем аудио из буфера
            audio_data = bytes(session['audio_buffer'])
            session['audio_buffer'].clear()
            
            if len(audio_data) < 1000:  # Слишком мало данных
                session['is_processing'] = False
                return
            
            logger.info(f"🎤 Обработка {len(audio_data)} байт аудио для звонка {call_id}")
            
            # 1. Распознавание речи (STT)
            user_text = await async_transcribe(audio_data)
            
            if user_text and user_text.strip():
                logger.info(f"💬 Распознано: {user_text}")
                
                # Добавляем в историю разговора
                session['conversation_history'].append({
                    'role': 'user',
                    'content': user_text,
                    'timestamp': datetime.now().isoformat()
                })
                
                # 2. Генерация ответа через LLM
                ai_response = await generate_ai_response(
                    user_text,
                    conversation_history=session['conversation_history']
                )
                
                logger.info(f"🤖 AI ответ: {ai_response}")
                
                # Добавляем ответ в историю
                session['conversation_history'].append({
                    'role': 'assistant',
                    'content': ai_response,
                    'timestamp': datetime.now().isoformat()
                })
                
                # 3. Синтез речи (TTS)
                audio_response = await async_synthesize(ai_response)
                
                # 4. Отправка аудио обратно через WebSocket
                if session['websocket'].open:
                    await session['websocket'].send(audio_response)
                    logger.info(f"🔊 Отправлено {len(audio_response)} байт аудио")
                else:
                    logger.warning(f"WebSocket закрыт для звонка {call_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки аудио для звонка {call_id}: {e}")
        finally:
            session['is_processing'] = False
    
    async def _handle_command(self, call_id: str, command: Dict[str, Any]):
        """Обработка команд от WebPhone"""
        cmd_type = command.get('type')
        
        if cmd_type == 'start_recording':
            logger.info(f"🔴 Начата запись для звонка {call_id}")
        elif cmd_type == 'stop_recording':
            logger.info(f"⏹️ Остановлена запись для звонка {call_id}")
        elif cmd_type == 'get_transcript':
            # Отправляем транскрипт разговора
            session = self.active_streams.get(call_id)
            if session:
                transcript = {
                    'type': 'transcript',
                    'call_id': call_id,
                    'history': session['conversation_history']
                }
                await session['websocket'].send(json.dumps(transcript))
        else:
            logger.warning(f"Неизвестная команда: {cmd_type}")
    
    async def handle_webphone_call(self, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка нового звонка от WebPhone (HTTP endpoint)
        
        Args:
            call_data: Данные о звонке от WebPhone
            
        Returns:
            Ответ для WebPhone
        """
        call_id = call_data.get('callId')
        from_number = call_data.get('from', 'Unknown')
        
        logger.info(f"📞 Новый звонок от WebPhone: {call_id} от {from_number}")
        
        # Генерируем приветствие
        greeting = self._generate_greeting(from_number)
        
        # Синтезируем приветствие
        try:
            greeting_audio = await async_synthesize(greeting)
            
            # Сохраняем для отладки
            import os
            os.makedirs("recordings", exist_ok=True)
            filename = f"recordings/greeting_{call_id}.wav"
            with open(filename, "wb") as f:
                f.write(greeting_audio)
            logger.info(f"💾 Приветствие сохранено в {filename}")
            
            return {
                'status': 'success',
                'call_id': call_id,
                'greeting': greeting,
                'audio_file': filename,
                'websocket_url': f'ws://localhost:8080/audio/{call_id}'
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации приветствия: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _generate_greeting(self, from_number: str) -> str:
        """Генерация приветствия для звонящего"""
        # Можно настроить разные приветствия в зависимости от номера
        if from_number == 'Unknown':
            return (
                "Hello! Thank you for calling Prime Cargo Logistics. "
                "I'm your AI assistant, and I'm here to help you with tracking shipments, "
                "scheduling pickups, or any other logistics needs. "
                "How can I assist you today?"
            )
        else:
            return (
                f"Hi there! Welcome back to Prime Cargo Logistics. "
                f"I see you're calling from {from_number}. "
                f"I'm here to help with any logistics questions or concerns you might have. "
                f"What can I do for you today?"
            )
    
    def get_active_calls(self) -> List[Dict[str, Any]]:
        """Получить список активных звонков"""
        return [
            {
                'call_id': call_id,
                'duration': (datetime.now() - session['last_audio_time']).total_seconds(),
                'messages': len(session['conversation_history'])
            }
            for call_id, session in self.active_streams.items()
        ]
    
    async def stop(self):
        """Остановка WebSocket сервера"""
        logger.info("🛑 Остановка Audio Stream Handler...")
        
        self.is_running = False
        
        # Закрываем все активные соединения
        for call_id, session in list(self.active_streams.items()):
            if session['websocket'].open:
                await session['websocket'].close()
        
        # Останавливаем сервер
        if self.ws_server:
            self.ws_server.close()
            await self.ws_server.wait_closed()
        
        logger.info("✅ Audio Stream Handler остановлен")

# Глобальный экземпляр
audio_stream_handler = AudioStreamHandler()