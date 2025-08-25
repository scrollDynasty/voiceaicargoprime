#!/bin/bash

# Быстрый тест webhook endpoints
# Использование: ./quick_test_webhook.sh

WEBHOOK_URL="http://localhost:5000/webhook"
WEBHOOK_SECRET="1Z7ztKD0I1gBu1QscmOBkonCn1tXG7LN"

echo "🔧 БЫСТРЫЙ ТЕСТ WEBHOOK ENDPOINTS"
echo "================================="

# Тест 1: Пустой POST
echo -e "\n1️⃣ Тест: Пустой POST запрос"
curl -X POST $WEBHOOK_URL \
  -H "Content-Length: 0" \
  -w "\nHTTP Status: %{http_code}\n"

# Тест 2: GET с challenge
echo -e "\n2️⃣ Тест: GET с hub.challenge"
curl -X GET "$WEBHOOK_URL?hub.challenge=test123" \
  -w "\nHTTP Status: %{http_code}\n"

# Тест 3: POST с JSON
echo -e "\n3️⃣ Тест: POST с JSON данными"
JSON_DATA='{"test":"data","uuid":"123"}'
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d "$JSON_DATA" \
  -w "\nHTTP Status: %{http_code}\n"

echo -e "\n✅ Тесты завершены!"
echo "Проверьте логи сервера для деталей."