#!/usr/bin/env python3
"""
SIP сервер для интеграции с RingCentral
Принимает входящие звонки и обрабатывает их через AI
"""

import socket
import threading
import hashlib
import time
import re
import base64
from datetime import datetime
import logging
from sip_voice_ai_engine import VoiceAIEngine
from sip_speech_processor import SpeechProcessor

# Импортируем конфигурацию
try:
    from ringcentral_config import RINGCENTRAL_CONFIG, LOCAL_CONFIG, AI_CONFIG
except ImportError:
    print("❌ Ошибка: создайте файл ringcentral_config.py с вашими настройками!")
    print("   Используйте ringcentral_config.py как шаблон")
    exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RingCentralSIPServer:
    def __init__(self):
        # Проверяем конфигурацию
        if not LOCAL_CONFIG.get('public_ip'):
            logger.error("❌ Не указан публичный IP в конфигурации!")
            logger.info("💡 Узнайте ваш IP на https://whatismyip.com")
            exit(1)
            
        if not RINGCENTRAL_CONFIG.get('username') or not RINGCENTRAL_CONFIG.get('password'):
            logger.error("❌ Не указаны RingCentral credentials!")
            logger.info("💡 Заполните username и password в ringcentral_config.py")
            exit(1)
        
        self.config = RINGCENTRAL_CONFIG
        self.local_config = LOCAL_CONFIG
        self.ai_engine = VoiceAIEngine()
        self.speech_processor = SpeechProcessor()
        
        # Состояние
        self.registered = False
        self.register_call_id = None
        self.cseq = 1
        self.active_calls = {}
        
        # SIP socket
        self.sip_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sip_socket.bind((self.local_config['local_ip'], self.local_config['sip_port']))
        
        logger.info(f"🚀 RingCentral SIP сервер запущен")
        logger.info(f"📍 Локальный адрес: {self.local_config['local_ip']}:{self.local_config['sip_port']}")
        logger.info(f"🌐 Публичный IP: {self.local_config['public_ip']}")
        
    def calculate_digest_response(self, username, realm, password, method, uri, nonce):
        """Вычисление MD5 digest для аутентификации"""
        ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        return response
        
    def register_with_ringcentral(self, auth_header=None):
        """Регистрация на RingCentral SIP сервере"""
        from_uri = f"sip:{self.config['username']}@{self.config['domain']}"
        to_uri = from_uri
        contact_uri = f"sip:{self.config['username']}@{self.local_config['public_ip']}:{self.local_config['sip_port']}"
        
        if not self.register_call_id:
            self.register_call_id = f"{int(time.time())}{self.config['username']}@{self.local_config['public_ip']}"
        
        branch = f"z9hG4bK{int(time.time() * 1000)}"
        tag = f"{int(time.time() * 1000)}"
        
        request = f"REGISTER sip:{self.config['domain']} SIP/2.0\r\n"
        request += f"Via: SIP/2.0/UDP {self.local_config['public_ip']}:{self.local_config['sip_port']};branch={branch};rport\r\n"
        request += f"Max-Forwards: 70\r\n"
        request += f"From: <{from_uri}>;tag={tag}\r\n"
        request += f"To: <{to_uri}>\r\n"
        request += f"Call-ID: {self.register_call_id}\r\n"
        request += f"CSeq: {self.cseq} REGISTER\r\n"
        request += f"Contact: <{contact_uri}>;expires={self.config['register_interval']}\r\n"
        request += f"Expires: {self.config['register_interval']}\r\n"
        request += f"User-Agent: VoiceAI-RingCentral/1.0\r\n"
        
        # Добавляем авторизацию если есть
        if auth_header:
            request += f"Authorization: {auth_header}\r\n"
            
        request += "Content-Length: 0\r\n"
        request += "\r\n"
        
        # Отправляем запрос
        try:
            server_addr = socket.gethostbyname(self.config['domain'])
            self.sip_socket.sendto(request.encode(), (server_addr, 5060))
            logger.info(f"📤 Отправлен REGISTER запрос на {self.config['domain']}")
            self.cseq += 1
        except Exception as e:
            logger.error(f"❌ Ошибка отправки REGISTER: {e}")
            
    def handle_auth_challenge(self, message, addr):
        """Обработка 401 Unauthorized"""
        # Извлекаем WWW-Authenticate заголовок
        www_auth_match = re.search(r'WWW-Authenticate: Digest (.+)', message)
        if not www_auth_match:
            logger.error("❌ Не найден WWW-Authenticate заголовок")
            return
            
        auth_params = {}
        for param in www_auth_match.group(1).split(','):
            key, value = param.strip().split('=', 1)
            auth_params[key] = value.strip('"')
            
        # Вычисляем digest response
        username = self.config['username']
        realm = auth_params.get('realm', self.config['auth_realm'])
        nonce = auth_params['nonce']
        uri = f"sip:{self.config['domain']}"
        
        response = self.calculate_digest_response(
            username, realm, self.config['password'], 
            'REGISTER', uri, nonce
        )
        
        # Формируем Authorization заголовок
        auth_header = f'Digest username="{username}", realm="{realm}", '
        auth_header += f'nonce="{nonce}", uri="{uri}", response="{response}", '
        auth_header += f'algorithm=MD5'
        
        # Переотправляем REGISTER с авторизацией
        self.register_with_ringcentral(auth_header)
        
    def handle_invite(self, message, addr):
        """Обработка входящего звонка"""
        logger.info("📞 ВХОДЯЩИЙ ЗВОНОК!")
        
        # Извлекаем Call-ID
        call_id_match = re.search(r'Call-ID: (.+)', message)
        if not call_id_match:
            return
            
        call_id = call_id_match.group(1).strip()
        
        # Извлекаем From
        from_match = re.search(r'From: .+<sip:(.+?)[@>]', message)
        caller = from_match.group(1) if from_match else "Unknown"
        
        logger.info(f"📱 Звонок от: {caller}")
        
        # Отправляем 180 Ringing
        self.send_ringing_response(message, addr)
        
        # Отправляем 200 OK и начинаем обработку
        threading.Thread(
            target=self.accept_call,
            args=(message, addr, call_id)
        ).start()
        
    def send_ringing_response(self, invite_message, addr):
        """Отправка 180 Ringing"""
        # Парсим необходимые поля из INVITE
        via_match = re.search(r'Via: (.+)', invite_message)
        from_match = re.search(r'From: (.+)', invite_message)
        to_match = re.search(r'To: (.+)', invite_message)
        call_id_match = re.search(r'Call-ID: (.+)', invite_message)
        cseq_match = re.search(r'CSeq: (.+)', invite_message)
        
        response = "SIP/2.0 180 Ringing\r\n"
        if via_match:
            response += f"Via: {via_match.group(1)}\r\n"
        if from_match:
            response += f"From: {from_match.group(1)}\r\n"
        if to_match:
            to_header = to_match.group(1)
            if 'tag=' not in to_header:
                to_header += f";tag={int(time.time() * 1000)}"
            response += f"To: {to_header}\r\n"
        if call_id_match:
            response += f"Call-ID: {call_id_match.group(1)}\r\n"
        if cseq_match:
            response += f"CSeq: {cseq_match.group(1)}\r\n"
        response += "Content-Length: 0\r\n"
        response += "\r\n"
        
        self.sip_socket.sendto(response.encode(), addr)
        logger.info("📤 Отправлен 180 Ringing")
        
    def accept_call(self, invite_message, addr, call_id):
        """Принятие звонка и начало RTP сессии"""
        time.sleep(1)  # Небольшая задержка перед ответом
        
        # Выбираем свободный RTP порт
        rtp_port = self.local_config['rtp_start_port']
        
        # Сохраняем информацию о звонке
        self.active_calls[call_id] = {
            'rtp_port': rtp_port,
            'remote_addr': addr,
            'start_time': datetime.now(),
            'state': 'active'
        }
        
        # Отправляем 200 OK с SDP
        self.send_ok_response(invite_message, addr, rtp_port)
        
        # Запускаем обработку RTP
        threading.Thread(
            target=self.handle_rtp_stream,
            args=(call_id,)
        ).start()
        
    def send_ok_response(self, invite_message, addr, rtp_port):
        """Отправка 200 OK с SDP"""
        # Парсим заголовки
        via_match = re.search(r'Via: (.+)', invite_message)
        from_match = re.search(r'From: (.+)', invite_message)
        to_match = re.search(r'To: (.+)', invite_message)
        call_id_match = re.search(r'Call-ID: (.+)', invite_message)
        cseq_match = re.search(r'CSeq: (.+)', invite_message)
        
        # Создаем SDP
        sdp = f"v=0\r\n"
        sdp += f"o=- {int(time.time())} {int(time.time())} IN IP4 {self.local_config['public_ip']}\r\n"
        sdp += f"s=VoiceAI Session\r\n"
        sdp += f"c=IN IP4 {self.local_config['public_ip']}\r\n"
        sdp += f"t=0 0\r\n"
        sdp += f"m=audio {rtp_port} RTP/AVP 0 8 101\r\n"
        sdp += f"a=rtpmap:0 PCMU/8000\r\n"
        sdp += f"a=rtpmap:8 PCMA/8000\r\n"
        sdp += f"a=rtpmap:101 telephone-event/8000\r\n"
        sdp += f"a=sendrecv\r\n"
        
        response = "SIP/2.0 200 OK\r\n"
        if via_match:
            response += f"Via: {via_match.group(1)}\r\n"
        if from_match:
            response += f"From: {from_match.group(1)}\r\n"
        if to_match:
            to_header = to_match.group(1)
            if 'tag=' not in to_header:
                to_header += f";tag={int(time.time() * 1000)}"
            response += f"To: {to_header}\r\n"
        if call_id_match:
            response += f"Call-ID: {call_id_match.group(1)}\r\n"
        if cseq_match:
            response += f"CSeq: {cseq_match.group(1)}\r\n"
        response += f"Contact: <sip:{self.config['username']}@{self.local_config['public_ip']}:{self.local_config['sip_port']}>\r\n"
        response += "Content-Type: application/sdp\r\n"
        response += f"Content-Length: {len(sdp)}\r\n"
        response += "\r\n"
        response += sdp
        
        self.sip_socket.sendto(response.encode(), addr)
        logger.info("📤 Отправлен 200 OK - звонок принят!")
        
    def handle_rtp_stream(self, call_id):
        """Обработка RTP аудио потока"""
        if call_id not in self.active_calls:
            return
            
        rtp_port = self.active_calls[call_id]['rtp_port']
        logger.info(f"🎤 Запуск RTP обработчика на порту {rtp_port}")
        
        # Создаем RTP сокет
        rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rtp_socket.bind(('0.0.0.0', rtp_port))
        rtp_socket.settimeout(1.0)
        
        # Приветственное сообщение
        welcome_text = "Здравствуйте! Я голосовой ассистент. Чем могу помочь?"
        self.send_tts_response(welcome_text, rtp_socket, call_id)
        
        audio_buffer = b''
        silence_duration = 0
        
        try:
            while call_id in self.active_calls and self.active_calls[call_id]['state'] == 'active':
                try:
                    # Получаем RTP пакет
                    data, remote_rtp_addr = rtp_socket.recvfrom(2048)
                    
                    if len(data) > 12:  # Минимальный размер RTP заголовка
                        # Парсим RTP заголовок
                        payload = data[12:]  # Пропускаем RTP заголовок
                        
                        # Добавляем аудио в буфер
                        audio_buffer += payload
                        
                        # Обрабатываем каждые 2 секунды аудио
                        if len(audio_buffer) > 16000:  # 8kHz * 2 сек
                            # Распознаем речь
                            text = self.speech_processor.process_audio(audio_buffer)
                            
                            if text:
                                logger.info(f"👤 Пользователь: {text}")
                                
                                # Получаем ответ от AI
                                ai_response = self.ai_engine.get_response(text)
                                logger.info(f"🤖 AI: {ai_response}")
                                
                                # Отправляем голосовой ответ
                                self.send_tts_response(ai_response, rtp_socket, call_id)
                                
                            audio_buffer = b''
                            
                except socket.timeout:
                    silence_duration += 1
                    if silence_duration > 30:  # 30 секунд тишины
                        logger.info("⏰ Тайм-аут из-за отсутствия активности")
                        break
                        
        except Exception as e:
            logger.error(f"❌ Ошибка в RTP обработчике: {e}")
            
        finally:
            rtp_socket.close()
            if call_id in self.active_calls:
                del self.active_calls[call_id]
            logger.info("📴 Звонок завершен")
            
    def send_tts_response(self, text, rtp_socket, call_id):
        """Синтез и отправка голосового ответа"""
        try:
            # Здесь должен быть код для TTS и отправки RTP пакетов
            # Пока просто логируем
            logger.info(f"🔊 Отправка TTS: {text}")
            
            # TODO: Реализовать отправку RTP пакетов с аудио
            
        except Exception as e:
            logger.error(f"❌ Ошибка TTS: {e}")
            
    def run(self):
        """Запуск сервера"""
        # Сначала регистрируемся
        self.register_with_ringcentral()
        
        # Запускаем поток для переregistрации
        threading.Thread(target=self.registration_loop, daemon=True).start()
        
        logger.info("🎧 Ожидание входящих звонков...")
        
        # Основной цикл обработки сообщений
        while True:
            try:
                data, addr = self.sip_socket.recvfrom(65535)
                message = data.decode('utf-8', errors='ignore')
                
                # Логируем для отладки
                logger.debug(f"📨 Получено от {addr}:\n{message[:200]}...")
                
                # Обрабатываем в отдельном потоке
                threading.Thread(
                    target=self.handle_sip_message, 
                    args=(message, addr)
                ).start()
                
            except Exception as e:
                logger.error(f"❌ Ошибка в основном цикле: {e}")
                
    def registration_loop(self):
        """Цикл переregistрации"""
        while True:
            time.sleep(self.config['register_interval'] - 30)  # За 30 секунд до истечения
            logger.info("🔄 Переregistрация...")
            self.register_with_ringcentral()
            
    def handle_sip_message(self, message, addr):
        """Обработка входящих SIP сообщений"""
        lines = message.split('\r\n')
        if not lines:
            return
            
        first_line = lines[0]
        
        if first_line.startswith('INVITE'):
            self.handle_invite(message, addr)
        elif first_line.startswith('SIP/2.0 200 OK'):
            if 'REGISTER' in message:
                logger.info("✅ Успешная регистрация на RingCentral!")
                self.registered = True
        elif first_line.startswith('SIP/2.0 401'):
            logger.info("🔐 Требуется аутентификация...")
            self.handle_auth_challenge(message, addr)
        elif first_line.startswith('BYE'):
            logger.info("📴 Получен BYE - завершение звонка")
            self.handle_bye(message, addr)
        elif first_line.startswith('ACK'):
            logger.debug("✓ Получен ACK")
        elif first_line.startswith('OPTIONS'):
            self.handle_options(message, addr)
            
    def handle_bye(self, message, addr):
        """Обработка завершения звонка"""
        call_id_match = re.search(r'Call-ID: (.+)', message)
        if call_id_match:
            call_id = call_id_match.group(1).strip()
            if call_id in self.active_calls:
                self.active_calls[call_id]['state'] = 'terminated'
                
        # Отправляем 200 OK на BYE
        self.send_bye_ok(message, addr)
        
    def send_bye_ok(self, bye_message, addr):
        """Отправка 200 OK на BYE"""
        via_match = re.search(r'Via: (.+)', bye_message)
        from_match = re.search(r'From: (.+)', bye_message)
        to_match = re.search(r'To: (.+)', bye_message)
        call_id_match = re.search(r'Call-ID: (.+)', bye_message)
        cseq_match = re.search(r'CSeq: (.+)', bye_message)
        
        response = "SIP/2.0 200 OK\r\n"
        if via_match:
            response += f"Via: {via_match.group(1)}\r\n"
        if from_match:
            response += f"From: {from_match.group(1)}\r\n"
        if to_match:
            response += f"To: {to_match.group(1)}\r\n"
        if call_id_match:
            response += f"Call-ID: {call_id_match.group(1)}\r\n"
        if cseq_match:
            response += f"CSeq: {cseq_match.group(1)}\r\n"
        response += "Content-Length: 0\r\n"
        response += "\r\n"
        
        self.sip_socket.sendto(response.encode(), addr)
        
    def handle_options(self, message, addr):
        """Обработка OPTIONS запроса (keep-alive)"""
        # Отправляем 200 OK
        via_match = re.search(r'Via: (.+)', message)
        from_match = re.search(r'From: (.+)', message)
        to_match = re.search(r'To: (.+)', message)
        call_id_match = re.search(r'Call-ID: (.+)', message)
        cseq_match = re.search(r'CSeq: (.+)', message)
        
        response = "SIP/2.0 200 OK\r\n"
        if via_match:
            response += f"Via: {via_match.group(1)}\r\n"
        if from_match:
            response += f"From: {from_match.group(1)}\r\n"
        if to_match:
            response += f"To: {to_match.group(1)}\r\n"
        if call_id_match:
            response += f"Call-ID: {call_id_match.group(1)}\r\n"
        if cseq_match:
            response += f"CSeq: {cseq_match.group(1)}\r\n"
        response += "Accept: application/sdp\r\n"
        response += "Content-Length: 0\r\n"
        response += "\r\n"
        
        self.sip_socket.sendto(response.encode(), addr)

if __name__ == "__main__":
    print("🚀 Запуск RingCentral Voice AI...")
    print("=" * 50)
    
    try:
        server = RingCentralSIPServer()
        server.run()
    except KeyboardInterrupt:
        print("\n👋 Остановка сервера...")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()