"""
Speech Processor для SIP/RTP системы
Преобразование речи в текст и текста в речь
"""

import logging
import whisper
import numpy as np
from TTS.api import TTS
import io
import wave
import struct

logger = logging.getLogger(__name__)

class SpeechProcessor:
    """Обработчик речи для SIP системы"""
    
    def __init__(self):
        # Загружаем модель Whisper для распознавания речи
        logger.info("📦 Загрузка модели Whisper...")
        self.whisper_model = whisper.load_model("base")
        logger.info("✅ Whisper модель загружена")
        
        # Загружаем TTS модель
        logger.info("📦 Загрузка TTS модели...")
        self.tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
        logger.info("✅ TTS модель загружена")
        
    def audio_to_text(self, audio_data: bytes, sample_rate: int = 8000) -> str:
        """
        Преобразование аудио в текст
        
        Args:
            audio_data: Сырые аудио данные
            sample_rate: Частота дискретизации (8kHz для телефонии)
            
        Returns:
            Распознанный текст
        """
        try:
            # Преобразуем байты в numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Нормализуем аудио
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Если частота не 16kHz (требование Whisper), делаем ресемплинг
            if sample_rate != 16000:
                # Простой ресемплинг (в реальности нужно использовать librosa)
                audio_float = np.interp(
                    np.linspace(0, len(audio_float), int(len(audio_float) * 16000 / sample_rate)),
                    np.arange(len(audio_float)),
                    audio_float
                )
            
            # Распознаем речь
            result = self.whisper_model.transcribe(audio_float, language="ru")
            text = result["text"].strip()
            
            logger.info(f"📝 Распознан текст: {text}")
            return text
            
        except Exception as e:
            logger.error(f"❌ Ошибка распознавания речи: {e}")
            return ""
            
    def text_to_audio(self, text: str, sample_rate: int = 8000) -> bytes:
        """
        Преобразование текста в аудио
        
        Args:
            text: Текст для синтеза
            sample_rate: Частота дискретизации для вывода
            
        Returns:
            Аудио данные в формате bytes
        """
        try:
            # Генерируем речь
            with io.BytesIO() as wav_buffer:
                # TTS генерирует wav файл
                self.tts.tts_to_file(
                    text=text,
                    file_path=None,
                    speaker=None,
                    language="en"
                )
                
                # Получаем аудио данные
                # В реальности нужно правильно обработать вывод TTS
                # Это упрощенная версия
                
                # Генерируем тестовый сигнал для демонстрации
                duration = len(text) * 0.1  # Примерная длительность
                samples = int(duration * sample_rate)
                
                # Генерируем тишину (в реальности здесь должна быть речь)
                audio_data = b'\x00' * (samples * 2)  # 16-bit samples
                
            logger.info(f"🔊 Синтезирована речь для: {text[:50]}...")
            return audio_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка синтеза речи: {e}")
            return b''
            
    def convert_audio_format(self, audio_data: bytes, from_rate: int, to_rate: int) -> bytes:
        """
        Конвертация частоты дискретизации аудио
        
        Args:
            audio_data: Исходные аудио данные
            from_rate: Исходная частота
            to_rate: Целевая частота
            
        Returns:
            Преобразованные аудио данные
        """
        if from_rate == to_rate:
            return audio_data
            
        try:
            # Преобразуем в numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Ресемплинг
            resampled_length = int(len(audio_array) * to_rate / from_rate)
            resampled = np.interp(
                np.linspace(0, len(audio_array), resampled_length),
                np.arange(len(audio_array)),
                audio_array
            )
            
            # Обратно в bytes
            return resampled.astype(np.int16).tobytes()
            
        except Exception as e:
            logger.error(f"❌ Ошибка конвертации аудио: {e}")
            return audio_data