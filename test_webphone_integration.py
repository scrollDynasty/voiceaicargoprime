#!/usr/bin/env python3
"""
Тест интеграции WebPhone + Python AI
Проверяет все компоненты системы
"""

import asyncio
import aiohttp
import json
import logging
import time
import websockets
from datetime import datetime
import subprocess
import requests
import sys
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebPhoneIntegrationTest:
    """Класс для тестирования интеграции WebPhone + Python AI"""
    
    def __init__(self):
        self.python_server = "http://localhost:5000"
        self.websocket_server = "ws://localhost:8080"
        self.test_results = {}
        
    def print_banner(self):
        """Печать баннера теста"""
        print("=" * 60)
        print("🧪 ТЕСТ ИНТЕГРАЦИИ WEBPHONE + PYTHON AI")
        print("Prime Cargo Logistics Voice AI System")
        print("=" * 60)
        print()
    
    def check_process_running(self, process_name: str) -> bool:
        """Проверка запущен ли процесс"""
        try:
            # Проверяем через PID файл
            pid_file = f"logs/{process_name}.pid"
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # Проверяем что процесс активен
                try:
                    os.kill(pid, 0)
                    return True
                except OSError:
                    return False
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки процесса {process_name}: {e}")
            return False
    
    def test_python_server_health(self) -> bool:
        """Тест здоровья Python сервера"""
        logger.info("🐍 Тестирование Python AI сервера...")
        
        try:
            response = requests.get(f"{self.python_server}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Python сервер здоров: {data.get('status')}")
                logger.info(f"   LLM: {'✅' if data.get('llm_healthy') else '❌'}")
                logger.info(f"   Speech Processor: {'✅' if data.get('speech_processor_initialized') else '❌'}")
                return True
            else:
                logger.error(f"❌ Python сервер вернул код: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Python серверу: {e}")
            return False
    
    def test_webphone_endpoint(self) -> bool:
        """Тест WebPhone endpoint"""
        logger.info("📞 Тестирование WebPhone endpoint...")
        
        test_call_data = {
            "callId": "test-call-" + str(int(time.time())),
            "sessionId": "test-session-123",
            "from": "+15139283626",
            "to": "+12345678901",
            "timestamp": datetime.now().isoformat(),
            "source": "webphone"
        }
        
        try:
            response = requests.post(
                f"{self.python_server}/api/handle-webphone-call",
                json=test_call_data,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ WebPhone endpoint отвечает: {data.get('status')}")
                logger.info(f"   Call ID: {data.get('call_id')}")
                logger.info(f"   Greeting: {data.get('greeting', 'N/A')[:50]}...")
                return True
            else:
                logger.error(f"❌ WebPhone endpoint вернул код: {response.status_code}")
                logger.error(f"   Ответ: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка тестирования WebPhone endpoint: {e}")
            return False
    
    async def test_websocket_connection(self) -> bool:
        """Тест WebSocket соединения для аудио"""
        logger.info("🔌 Тестирование WebSocket соединения...")
        
        test_call_id = "test-ws-" + str(int(time.time()))
        ws_url = f"{self.websocket_server}/audio/{test_call_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                logger.info("✅ WebSocket соединение установлено")
                
                # Отправляем тестовое сообщение
                test_message = {
                    "type": "audio",
                    "call_id": test_call_id,
                    "data": "dGVzdCBhdWRpbyBkYXRh"  # "test audio data" в base64
                }
                
                await websocket.send(json.dumps(test_message))
                logger.info("📤 Тестовое аудио сообщение отправлено")
                
                # Ждем ответ
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    response_data = json.loads(response)
                    logger.info(f"📥 Получен ответ: {response_data.get('type')}")
                    return True
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Таймаут ожидания ответа от WebSocket")
                    return True  # Соединение работает, просто нет ответа
                
        except Exception as e:
            logger.error(f"❌ Ошибка WebSocket соединения: {e}")
            return False
    
    def test_webphone_status(self) -> bool:
        """Тест статуса WebPhone"""
        logger.info("📊 Проверка статуса WebPhone...")
        
        try:
            response = requests.get(f"{self.python_server}/api/webphone/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ WebPhone статус: {data.get('status')}")
                logger.info(f"   WebSocket: {'✅' if data.get('websocket_running') else '❌'}")
                logger.info(f"   Активных звонков: {data.get('active_calls', 0)}")
                return True
            else:
                logger.error(f"❌ Ошибка получения статуса: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса: {e}")
            return False
    
    def test_dependencies(self) -> bool:
        """Тест зависимостей"""
        logger.info("📦 Проверка зависимостей...")
        
        dependencies = {
            "Python AI Server": self.check_process_running("python-server"),
            "WebPhone Bridge": self.check_process_running("webphone-bridge")
        }
        
        all_running = True
        for name, running in dependencies.items():
            status = "✅" if running else "❌"
            logger.info(f"   {name}: {status}")
            if not running:
                all_running = False
        
        return all_running
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        self.print_banner()
        
        tests = [
            ("Dependencies Check", self.test_dependencies),
            ("Python Server Health", self.test_python_server_health),
            ("WebPhone Endpoint", self.test_webphone_endpoint),
            ("WebPhone Status", self.test_webphone_status),
            ("WebSocket Connection", self.test_websocket_connection)
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            logger.info(f"\n🧪 Запуск теста: {test_name}")
            logger.info("-" * 40)
            
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                
                results[test_name] = result
                status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
                logger.info(f"Результат: {status}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка теста {test_name}: {e}")
                results[test_name] = False
        
        # Итоговый отчет
        self.print_summary(results)
    
    def print_summary(self, results: dict):
        """Печать итогового отчета"""
        print("\n" + "=" * 60)
        print("📋 ИТОГОВЫЙ ОТЧЕТ ТЕСТИРОВАНИЯ")
        print("=" * 60)
        
        passed = sum(1 for r in results.values() if r)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
            print(f"   {test_name:<30} {status}")
        
        print("-" * 60)
        print(f"📊 СТАТИСТИКА: {passed}/{total} тестов пройдено")
        
        if passed == total:
            print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система готова к работе!")
        else:
            print("⚠️  НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ. Проверьте логи.")
            print("\n🔧 РЕКОМЕНДАЦИИ:")
            if not results.get("Dependencies Check"):
                print("   • Запустите ./start_system.sh для старта компонентов")
            if not results.get("Python Server Health"):
                print("   • Проверьте логи Python сервера: tail -f logs/python-server.log")
            if not results.get("WebPhone Status"):
                print("   • Проверьте логи WebPhone: tail -f logs/webphone-bridge.log")
        
        print("=" * 60)

async def main():
    """Главная функция"""
    tester = WebPhoneIntegrationTest()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())