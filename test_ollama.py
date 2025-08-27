#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы Ollama
"""

import requests
import json
import sys

def test_ollama():
    """Проверка подключения к Ollama"""
    ollama_url = "http://localhost:11434"
    model_name = "llama3.1:8b-instruct-q4_0"
    
    print("🔍 Проверка Ollama сервера...")
    
    # Проверяем доступность сервера
    try:
        response = requests.get(f"{ollama_url}/api/tags")
        if response.status_code == 200:
            print("✅ Ollama сервер доступен")
            
            # Получаем список моделей
            models = response.json().get('models', [])
            if models:
                print("\n📋 Доступные модели:")
                for model in models:
                    print(f"   - {model['name']} ({model['size']} bytes)")
                    
                # Проверяем нашу модель
                model_names = [m['name'] for m in models]
                if model_name in model_names:
                    print(f"\n✅ Модель {model_name} найдена")
                else:
                    print(f"\n⚠️  Модель {model_name} не найдена")
                    print(f"   Используйте: ollama pull {model_name}")
            else:
                print("\n⚠️  Нет загруженных моделей")
                print(f"   Используйте: ollama pull {model_name}")
                
        else:
            print(f"❌ Ошибка подключения: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Не удалось подключиться к Ollama")
        print("   Убедитесь, что сервер запущен: ollama serve")
        return False
        
    # Тестовый запрос
    print("\n🤖 Отправка тестового запроса...")
    try:
        test_prompt = "Привет! Ответь одним предложением."
        
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model_name,
                "prompt": test_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 50
                }
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Ответ получен: {result['response'].strip()}")
            print(f"   Время генерации: {result.get('total_duration', 0) / 1e9:.2f} сек")
            return True
        else:
            print(f"❌ Ошибка генерации: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при тестовом запросе: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Тестирование интеграции с Ollama\n")
    
    if test_ollama():
        print("\n✅ Все тесты пройдены успешно!")
        sys.exit(0)
    else:
        print("\n❌ Тесты не пройдены")
        sys.exit(1)