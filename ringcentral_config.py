#!/usr/bin/env python3
"""
Конфигурация для интеграции с RingCentral
"""

# RingCentral SIP настройки
RINGCENTRAL_CONFIG = {
    # Основные настройки - ЗАПОЛНИТЕ СВОИМИ ДАННЫМИ
    'domain': 'sip.ringcentral.com',  # или sip-eu.ringcentral.com для Европы
    'username': '',  # Ваш extension номер
    'password': '',  # SIP пароль из RingCentral
    'extension': '',  # Ваш номер extension
    
    # Дополнительные настройки (обычно менять не нужно)
    'outbound_proxy': 'sip.ringcentral.com',
    'transport': 'UDP',
    'register_interval': 300,  # секунд
    'codec': 'PCMU',  # G.711 μ-law
    'auth_realm': 'ringcentral.com',
}

# Локальные настройки
LOCAL_CONFIG = {
    # ВАЖНО: Укажите ваш публичный IP или домен
    'public_ip': '',  # Ваш внешний IP (узнать можно на whatismyip.com)
    
    # Локальные настройки
    'local_ip': '0.0.0.0',  # слушать на всех интерфейсах
    'sip_port': 5060,
    'rtp_start_port': 10000,
    'rtp_end_port': 20000,
}

# Настройки AI
AI_CONFIG = {
    'ollama_url': 'http://localhost:11434',
    'ollama_model': 'llama3.1:8b-instruct-q4_0',
    'whisper_model': 'base',
    'tts_engine': 'pyttsx3',
    'language': 'ru',
}

# Настройки логирования
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'logs/ringcentral_sip.log',
}