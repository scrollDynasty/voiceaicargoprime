"""
Voice AI Engine для SIP/RTP системы
Обрабатывает голосовые запросы без веб-интерфейса
"""

import logging
import time
from typing import List, Dict
import requests
import json
import os

logger = logging.getLogger(__name__)

class VoiceAIEngine:
    """AI движок для обработки голосовых запросов"""
    
    def __init__(self):
        self.conversation_history = []
        self.ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.model_name = os.getenv('OLLAMA_MODEL', 'llama3.1:8b-instruct-q4_0')
        
        # Проверяем доступность Ollama
        try:
            response = requests.get(f"{self.ollama_url}/api/tags")
            if response.status_code == 200:
                logger.info("✅ Ollama сервер доступен")
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                if self.model_name in model_names:
                    logger.info(f"✅ Модель {self.model_name} найдена")
                else:
                    logger.warning(f"⚠️ Модель {self.model_name} не найдена. Доступные модели: {model_names}")
            else:
                logger.error("❌ Ollama сервер недоступен")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Ollama: {e}")
            
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
            
            # Запрос к Ollama
            try:
                # Формируем промпт из истории сообщений
                prompt = ""
                for msg in messages:
                    if msg["role"] == "system":
                        prompt += f"System: {msg['content']}\n\n"
                    elif msg["role"] == "user":
                        prompt += f"User: {msg['content']}\n"
                    elif msg["role"] == "assistant":
                        prompt += f"Assistant: {msg['content']}\n"
                
                prompt += "Assistant: "
                
                # Отправляем запрос к Ollama
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 150  # Максимум токенов для короткого ответа
                        }
                    }
                )
                
                if response.status_code == 200:
                    ai_response = response.json()['response'].strip()
                else:
                    logger.error(f"❌ Ошибка от Ollama: {response.status_code} - {response.text}")
                    ai_response = "Извините, произошла ошибка при обработке запроса."
                    
            except requests.exceptions.ConnectionError:
                logger.error("❌ Не удалось подключиться к Ollama. Убедитесь, что сервер запущен.")
                ai_response = "Извините, AI сервер временно недоступен."
            except Exception as e:
                logger.error(f"❌ Неожиданная ошибка при запросе к Ollama: {e}")
                ai_response = "Извините, произошла непредвиденная ошибка."
            
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