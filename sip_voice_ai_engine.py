"""
Voice AI Engine для SIP/RTP системы
Обрабатывает голосовые запросы без веб-интерфейса
"""

import logging
import time
from typing import List, Dict
import openai
import os

logger = logging.getLogger(__name__)

class VoiceAIEngine:
    """AI движок для обработки голосовых запросов"""
    
    def __init__(self):
        self.conversation_history = []
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
            logger.info("✅ OpenAI API ключ загружен")
        else:
            logger.warning("⚠️ OpenAI API ключ не найден в переменных окружения")
            
    def process_request(self, text: str) -> str:
        """
        Обработка текстового запроса и генерация ответа
        
        Args:
            text: Распознанный текст от абонента
            
        Returns:
            Текстовый ответ от AI
        """
        try:
            # Добавляем в историю
            self.conversation_history.append({"role": "user", "content": text})
            
            # Системный промпт
            system_prompt = """Вы - вежливый и профессиональный голосовой ассистент компании Prime Cargo Logistics.
Ваша задача - помогать клиентам с вопросами о доставке, отслеживании груза и других услугах компании.
Отвечайте кратко и по существу, помните что это телефонный разговор."""
            
            # Формируем сообщения для API
            messages = [
                {"role": "system", "content": system_prompt}
            ] + self.conversation_history[-10:]  # Последние 10 сообщений
            
            # Запрос к OpenAI
            if self.openai_api_key:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=150  # Короткие ответы для телефона
                )
                
                ai_response = response.choices[0].message.content
            else:
                # Заглушка если нет API ключа
                ai_response = "Здравствуйте! Это тестовый режим голосового ассистента. Пожалуйста, настройте OpenAI API ключ."
            
            # Добавляем ответ в историю
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            
            logger.info(f"🤖 AI ответ: {ai_response}")
            return ai_response
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации ответа: {e}")
            return "Извините, произошла ошибка. Пожалуйста, повторите ваш вопрос."
            
    def reset_conversation(self):
        """Сброс истории разговора"""
        self.conversation_history = []
        logger.info("🔄 История разговора сброшена")