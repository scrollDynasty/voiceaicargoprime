#!/usr/bin/env python3
"""
Тест разных голосов TTS для выбора лучшего
"""

import os
import sys
from TTS.api import TTS
from config import Config
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_voice_models():
    """Тестируем разные модели TTS"""
    
    print("🎤 ТЕСТ РАЗНЫХ ГОЛОСОВ TTS")
    print("=" * 60)
    
    # Список ПОЗИТИВНЫХ ЖЕНСКИХ голосов для тестирования
    voice_configs = [
        {
            "name": "😊 ПОЗИТИВНАЯ ДИСПЕТЧЕР",
            "speaker": "p225",  # Основной женский
            "speed": 1.2,       # Быстро и энергично
            "volume": 1.25,     # Громко и позитивно
            "description": "ПОЗИТИВНЫЙ и дружелюбный женский голос"
        },
        {
            "name": "🌟 ЭНЕРГИЧНАЯ И ВЕСЕЛАЯ",
            "speaker": "p226",  # Энергичный женский
            "speed": 1.3,       # Очень быстро
            "volume": 1.35,     # Очень громко
            "description": "Энергичная и веселая женская диспетчер"
        },
        {
            "name": "💖 ДРУЖЕЛЮБНАЯ И ТЕПЛАЯ",
            "speaker": "p227",  # Дружелюбный женский
            "speed": 1.15,      # Быстро
            "volume": 1.2,      # Громко
            "description": "Дружелюбная и теплая женская диспетчер"
        },
        {
            "name": "🎉 ПРАЗДНИЧНАЯ И РАДОСТНАЯ",
            "speaker": "p228",  # Радостный женский
            "speed": 1.25,      # Быстро
            "volume": 1.3,      # Громко
            "description": "Праздничная и радостная женская диспетчер"
        },
        {
            "name": "✨ БОДРАЯ И ОПТИМИСТИЧНАЯ",
            "speaker": "p229",  # Оптимистичный женский
            "speed": 1.2,       # Быстро
            "volume": 1.25,     # Громко
            "description": "Бодрая и оптимистичная женская диспетчер"
        },
        {
            "name": "🌈 СВЕТЛАЯ И ПОЗИТИВНАЯ",
            "speaker": "p230",  # Светлый женский
            "speed": 1.15,      # Быстро
            "volume": 1.2,      # Громко
            "description": "Светлая и позитивная женская диспетчер"
        }
    ]
    
    # Тестовый текст - ПОЗИТИВНЫЙ И ДРУЖЕЛЮБНЫЙ
    test_text = "Hi there! Welcome to Prime Cargo Logistics! I'm here to help you with anything you need today! How can I assist you?"
    
    print(f"📝 Тестовый текст: {test_text}")
    print()
    
    try:
        # Инициализируем TTS
        device = "cuda" if Config.PERFORMANCE["use_gpu"] else "cpu"
        tts = TTS(model_name=Config.TTS["model_name"], progress_bar=False).to(device)
        
        print(f"🔧 Используем модель: {Config.TTS['model_name']}")
        print(f"💻 Устройство: {device}")
        print()
        
        # Тестируем каждый голос
        for i, config in enumerate(voice_configs, 1):
            print(f"🎤 {i}. {config['name']}")
            print(f"   📋 {config['description']}")
            print(f"   ⚙️ Speaker: {config['speaker']}, Speed: {config['speed']}, Volume: {config['volume']}")
            
            try:
                # Генерируем аудио
                output_file = f"test_voice_{i}_{config['speaker']}.wav"
                
                tts.tts_to_file(
                    text=test_text,
                    speaker=config['speaker'],
                    file_path=output_file,
                    speed=config['speed']
                )
                
                print(f"   ✅ Создан файл: {output_file}")
                print(f"   🔊 Проиграйте файл для оценки голоса")
                print()
                
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                print()
        
        print("🎯 РЕКОМЕНДАЦИИ:")
        print("1. Проиграйте все созданные файлы")
        print("2. Выберите лучший голос")
        print("3. Обновите config.py с выбранными параметрами")
        print()
        print("📁 Файлы сохранены в текущей директории")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации TTS: {e}")
        print("Убедитесь что TTS установлен: pip install TTS")

def list_available_speakers():
    """Показываем доступных спикеров"""
    
    print("📋 ДОСТУПНЫЕ СПИКЕРЫ В VCTK МОДЕЛИ")
    print("=" * 50)
    
    try:
        device = "cuda" if Config.PERFORMANCE["use_gpu"] else "cpu"
        tts = TTS(model_name=Config.TTS["model_name"], progress_bar=False).to(device)
        
        speakers = tts.speakers
        if speakers:
            print(f"Всего доступно спикеров: {len(speakers)}")
            print()
            
            # Показываем первые 20 спикеров
            for i, speaker in enumerate(speakers[:20], 1):
                print(f"{i:2d}. {speaker}")
            
            if len(speakers) > 20:
                print(f"... и еще {len(speakers) - 20} спикеров")
        else:
            print("Спикеры не найдены")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        list_available_speakers()
    else:
        test_voice_models()
