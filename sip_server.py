#!/usr/bin/env python3
"""
SIP сервер для прямого перехвата звонков
Использует SIP/RTP для телефонии без веб-интерфейса
"""

import socket
import threading
import struct
import hashlib
import time
import re
from datetime import datetime
import logging
from sip_voice_ai_engine import VoiceAIEngine
from sip_speech_processor import SpeechProcessor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SIPServer:
    def __init__(self, local_ip='0.0.0.0', sip_port=5060, rtp_port=10000):
        self.local_ip = local_ip
        self.sip_port = sip_port
        self.rtp_port = rtp_port
        self.calls = {}
        self.registered_users = {}
        
        # AI компоненты
        self.ai_engine = VoiceAIEngine()
        self.speech_processor = SpeechProcessor()
        
        # SIP сокет
        self.sip_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sip_socket.bind((self.local_ip, self.sip_port))
        
        logger.info(f"🚀 SIP сервер запущен на {local_ip}:{sip_port}")
        
    def run(self):
        """Запуск SIP сервера"""
        while True:
            try:
                data, addr = self.sip_socket.recvfrom(65535)
                message = data.decode('utf-8')
                logger.info(f"📨 Получено SIP сообщение от {addr}")
                logger.debug(f"Сообщение:\n{message}")
                
                # Обработка SIP сообщения в отдельном потоке
                thread = threading.Thread(target=self.handle_sip_message, args=(message, addr))
                thread.start()
                
            except Exception as e:
                logger.error(f"❌ Ошибка в SIP сервере: {e}")
                
    def handle_sip_message(self, message, addr):
        """Обработка SIP сообщения"""
        try:
            # Парсинг SIP заголовков
            lines = message.split('\r\n')
            method = lines[0].split()[0]
            
            headers = {}
            for line in lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            logger.info(f"📞 SIP метод: {method}")
            
            if method == 'REGISTER':
                self.handle_register(message, headers, addr)
            elif method == 'INVITE':
                self.handle_invite(message, headers, addr)
            elif method == 'ACK':
                self.handle_ack(message, headers, addr)
            elif method == 'BYE':
                self.handle_bye(message, headers, addr)
            elif method == 'OPTIONS':
                self.handle_options(message, headers, addr)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки SIP: {e}")
            
    def handle_register(self, message, headers, addr):
        """Обработка REGISTER запроса"""
        logger.info(f"📝 Обработка REGISTER от {addr}")
        
        # Простая регистрация без аутентификации для демо
        from_header = headers.get('From', '')
        to_header = headers.get('To', '')
        call_id = headers.get('Call-ID', '')
        
        # Извлекаем SIP URI
        sip_uri_match = re.search(r'<sip:(.+?)>', from_header)
        if sip_uri_match:
            sip_uri = sip_uri_match.group(1)
            self.registered_users[sip_uri] = addr
            logger.info(f"✅ Пользователь {sip_uri} зарегистрирован")
        
        # Отправляем 200 OK
        response = self.create_response(message, headers, 200, 'OK')
        self.sip_socket.sendto(response.encode(), addr)
        
    def handle_invite(self, message, headers, addr):
        """Обработка INVITE запроса (входящий звонок)"""
        logger.info(f"📞 Входящий звонок от {addr}")
        
        call_id = headers.get('Call-ID', '')
        from_header = headers.get('From', '')
        to_header = headers.get('To', '')
        
        # Сохраняем информацию о звонке
        self.calls[call_id] = {
            'from': from_header,
            'to': to_header,
            'addr': addr,
            'state': 'ringing',
            'rtp_port': self.rtp_port + len(self.calls)
        }
        
        # Отправляем 100 Trying
        trying_response = self.create_response(message, headers, 100, 'Trying')
        self.sip_socket.sendto(trying_response.encode(), addr)
        
        # Отправляем 180 Ringing
        time.sleep(0.1)
        ringing_response = self.create_response(message, headers, 180, 'Ringing')
        self.sip_socket.sendto(ringing_response.encode(), addr)
        
        # Автоматически принимаем звонок через 1 секунду
        time.sleep(1)
        
        # Извлекаем SDP из INVITE
        sdp_start = message.find('\r\n\r\n') + 4
        sdp_data = message[sdp_start:] if sdp_start > 3 else ''
        
        # Создаем ответ 200 OK с SDP
        ok_response = self.create_200_ok_with_sdp(message, headers, self.calls[call_id]['rtp_port'])
        self.sip_socket.sendto(ok_response.encode(), addr)
        
        self.calls[call_id]['state'] = 'answered'
        logger.info(f"✅ Звонок {call_id} принят, RTP порт: {self.calls[call_id]['rtp_port']}")
        
        # Запускаем RTP обработчик для этого звонка
        rtp_thread = threading.Thread(target=self.handle_rtp_stream, args=(call_id,))
        rtp_thread.start()
        
    def handle_ack(self, message, headers, addr):
        """Обработка ACK"""
        call_id = headers.get('Call-ID', '')
        logger.info(f"✅ ACK получен для звонка {call_id}")
        
        if call_id in self.calls:
            self.calls[call_id]['state'] = 'active'
            
    def handle_bye(self, message, headers, addr):
        """Обработка BYE (завершение звонка)"""
        call_id = headers.get('Call-ID', '')
        logger.info(f"📞 Завершение звонка {call_id}")
        
        # Отправляем 200 OK
        response = self.create_response(message, headers, 200, 'OK')
        self.sip_socket.sendto(response.encode(), addr)
        
        # Удаляем информацию о звонке
        if call_id in self.calls:
            del self.calls[call_id]
            
    def handle_options(self, message, headers, addr):
        """Обработка OPTIONS (проверка доступности)"""
        response = self.create_response(message, headers, 200, 'OK')
        self.sip_socket.sendto(response.encode(), addr)
        
    def create_response(self, request, headers, code, reason):
        """Создание SIP ответа"""
        lines = request.split('\r\n')
        request_line = lines[0]
        
        response = f"SIP/2.0 {code} {reason}\r\n"
        
        # Копируем важные заголовки
        for header in ['Via', 'From', 'To', 'Call-ID', 'CSeq']:
            if header in headers:
                response += f"{header}: {headers[header]}\r\n"
                
        response += f"Content-Length: 0\r\n"
        response += "\r\n"
        
        return response
        
    def create_200_ok_with_sdp(self, request, headers, rtp_port):
        """Создание 200 OK ответа с SDP"""
        response = f"SIP/2.0 200 OK\r\n"
        
        # Копируем заголовки
        for header in ['Via', 'From', 'To', 'Call-ID', 'CSeq']:
            if header in headers:
                response += f"{header}: {headers[header]}\r\n"
                
        # SDP тело
        sdp = f"""v=0
o=- 0 0 IN IP4 {self.get_local_ip()}
s=-
c=IN IP4 {self.get_local_ip()}
t=0 0
m=audio {rtp_port} RTP/AVP 0 8 101
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
a=rtpmap:101 telephone-event/8000
a=sendrecv
"""
        
        response += f"Content-Type: application/sdp\r\n"
        response += f"Content-Length: {len(sdp)}\r\n"
        response += "\r\n"
        response += sdp
        
        return response
        
    def get_local_ip(self):
        """Получение локального IP адреса"""
        try:
            # Создаем UDP сокет для определения локального IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
            
    def handle_rtp_stream(self, call_id):
        """Обработка RTP потока для звонка"""
        if call_id not in self.calls:
            return
            
        rtp_port = self.calls[call_id]['rtp_port']
        logger.info(f"🎤 Запуск RTP обработчика на порту {rtp_port}")
        
        # Создаем RTP сокет
        rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rtp_socket.bind(('0.0.0.0', rtp_port))
        rtp_socket.settimeout(1.0)
        
        audio_buffer = b''
        
        try:
            while call_id in self.calls and self.calls[call_id]['state'] == 'active':
                try:
                    # Получаем RTP пакет
                    data, addr = rtp_socket.recvfrom(2048)
                    
                    if len(data) > 12:  # Минимальный размер RTP заголовка
                        # Парсим RTP заголовок
                        rtp_header = struct.unpack('!BBHII', data[:12])
                        payload = data[12:]
                        
                        # Добавляем аудио в буфер
                        audio_buffer += payload
                        
                        # Когда накопилось достаточно аудио (например, 1 секунда)
                        if len(audio_buffer) > 8000:  # 8kHz * 1 сек
                            # Обрабатываем через AI
                            self.process_audio_with_ai(audio_buffer, call_id, rtp_socket, addr)
                            audio_buffer = b''
                            
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"❌ Ошибка в RTP: {e}")
                    
        finally:
            rtp_socket.close()
            logger.info(f"🔚 RTP обработчик для звонка {call_id} завершен")
            
    def process_audio_with_ai(self, audio_data, call_id, rtp_socket, client_addr):
        """Обработка аудио через AI и отправка ответа"""
        try:
            logger.info(f"🤖 Обработка аудио через AI для звонка {call_id}")
            
            # Преобразуем аудио в текст
            text = self.speech_processor.audio_to_text(audio_data)
            logger.info(f"📝 Распознанный текст: {text}")
            
            if text:
                # Получаем ответ от AI
                ai_response = self.ai_engine.process_request(text)
                logger.info(f"🤖 AI ответ: {ai_response}")
                
                # Преобразуем ответ в аудио
                response_audio = self.speech_processor.text_to_audio(ai_response)
                
                # Отправляем аудио обратно через RTP
                self.send_rtp_audio(rtp_socket, client_addr, response_audio)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки AI: {e}")
            
    def send_rtp_audio(self, rtp_socket, addr, audio_data):
        """Отправка аудио через RTP"""
        # Простая отправка RTP пакетов
        # В реальности нужно правильно формировать RTP пакеты с timestamp и sequence
        chunk_size = 160  # 20ms при 8kHz
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            if chunk:
                # Простой RTP заголовок (в реальности нужно больше полей)
                rtp_header = struct.pack('!BBHII', 0x80, 0, i//chunk_size, int(time.time()), 0)
                rtp_packet = rtp_header + chunk
                rtp_socket.sendto(rtp_packet, addr)
                time.sleep(0.02)  # 20ms между пакетами

if __name__ == "__main__":
    import sys
    
    # Проверяем аргументы командной строки
    local_ip = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    sip_port = int(sys.argv[2]) if len(sys.argv) > 2 else 5060
    
    # Создаем и запускаем SIP сервер
    server = SIPServer(local_ip, sip_port)
    
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("🛑 Остановка SIP сервера...")
        sys.exit(0)