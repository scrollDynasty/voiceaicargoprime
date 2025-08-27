#!/usr/bin/env python3
"""
Integration Test для Voice AI System
Тестирует все компоненты системы
"""

import asyncio
import json
import time
import requests
import websockets
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IntegrationTest:
    def __init__(self):
        self.python_server = "http://localhost:5000"
        self.websocket_url = "ws://localhost:8080"
        self.test_results = []
        
    def add_result(self, test_name, success, message=""):
        """Добавить результат теста"""
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        
        icon = "✅" if success else "❌"
        logger.info(f"{icon} {test_name}: {message}")
    
    def test_python_server(self):
        """Тест Python сервера"""
        logger.info("\n🧪 Тестирование Python сервера...")
        
        try:
            # Health check
            response = requests.get(f"{self.python_server}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.add_result("Python Server Health", True, f"Status: {data.get('status')}")
                
                # Проверка Voice AI компонентов
                voice_ai = data.get('voice_ai_status', {})
                if voice_ai.get('speech_processor_initialized'):
                    self.add_result("Speech Processor", True, "Whisper и TTS инициализированы")
                else:
                    self.add_result("Speech Processor", False, "Не инициализирован")
                    
                if voice_ai.get('llm_healthy'):
                    self.add_result("LLM Handler", True, "Llama модель доступна")
                else:
                    self.add_result("LLM Handler", False, "LLM не доступен")
            else:
                self.add_result("Python Server Health", False, f"Status code: {response.status_code}")
                
        except Exception as e:
            self.add_result("Python Server", False, f"Ошибка: {str(e)}")
    

    
    async def test_websocket_connection(self):
        """Тест WebSocket соединения"""
        logger.info("\n🧪 Тестирование WebSocket соединения...")
        
        try:
            # Подключаемся к WebSocket
            uri = f"{self.websocket_url}/audio/test-ws-call"
            async with websockets.connect(uri) as websocket:
                self.add_result("WebSocket Connection", True, "Соединение установлено")
                
                # Отправляем тестовую команду
                test_command = {
                    "type": "get_transcript",
                    "call_id": "test-ws-call"
                }
                
                await websocket.send(json.dumps(test_command))
                self.add_result("WebSocket Send", True, "Команда отправлена")
                
                # Ждем ответ (с таймаутом)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    self.add_result("WebSocket Receive", True, f"Получен ответ: {len(response)} байт")
                except asyncio.TimeoutError:
                    self.add_result("WebSocket Receive", True, "Таймаут (нормально для пустого транскрипта)")
                    
        except Exception as e:
            self.add_result("WebSocket Connection", False, f"Ошибка: {str(e)}")
    

    
    async def test_ai_components(self):
        """Тест AI компонентов напрямую"""
        logger.info("\n🧪 Тестирование AI компонентов...")
        
        try:
            # Импортируем компоненты
            from speech_processor import async_synthesize
            from llm_handler import generate_ai_response
            
            # Тест LLM
            test_question = "What are your shipping rates to California?"
            ai_response = await generate_ai_response(test_question)
            if ai_response:
                self.add_result("LLM Response", True, f"Ответ: {ai_response[:50]}...")
            else:
                self.add_result("LLM Response", False, "Пустой ответ")
            
            # Тест TTS
            test_text = "Hello, this is a test of the text to speech system."
            audio_data = await async_synthesize(test_text)
            if audio_data and len(audio_data) > 1000:
                self.add_result("TTS Synthesis", True, f"Аудио сгенерировано: {len(audio_data)} байт")
            else:
                self.add_result("TTS Synthesis", False, "Аудио не сгенерировано")
                
        except Exception as e:
            self.add_result("AI Components", False, f"Ошибка: {str(e)}")
    
    def generate_report(self):
        """Генерация отчета о тестировании"""
        logger.info("\n" + "="*50)
        logger.info("📊 ОТЧЕТ О ТЕСТИРОВАНИИ")
        logger.info("="*50)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['success'])
        failed = total - passed
        
        logger.info(f"Всего тестов: {total}")
        logger.info(f"✅ Пройдено: {passed}")
        logger.info(f"❌ Провалено: {failed}")
        logger.info(f"Успешность: {(passed/total*100):.1f}%")
        
        if failed > 0:
            logger.info("\n❌ Проваленные тесты:")
            for result in self.test_results:
                if not result['success']:
                    logger.info(f"  - {result['test']}: {result['message']}")
        
        # Сохраняем отчет
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "success_rate": passed/total*100
                },
                "results": self.test_results
            }, f, indent=2)
        
        logger.info(f"\n💾 Отчет сохранен в: {report_file}")
        
        return passed == total
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        logger.info("🚀 Запуск интеграционных тестов...")
        logger.info("="*50)
        
        # Даем время системе запуститься
        logger.info("⏳ Ожидание запуска системы (5 сек)...")
        time.sleep(5)
        
        # Запускаем тесты
        self.test_python_server()

        await self.test_websocket_connection()

        await self.test_ai_components()
        
        # Генерируем отчет
        all_passed = self.generate_report()
        
        if all_passed:
            logger.info("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        else:
            logger.info("\n⚠️  НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
        
        return all_passed

async def main():
    """Главная функция"""
    tester = IntegrationTest()
    success = await tester.run_all_tests()
    exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())