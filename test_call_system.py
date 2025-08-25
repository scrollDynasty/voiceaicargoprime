#!/usr/bin/env python3
"""
Test Call System
Тестирует систему звонков
"""

import requests
import json
import time

def test_webhook():
    """Test webhook endpoint"""
    print("🔍 Testing webhook system...")
    
    # Test health
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Webhook server is healthy")
            print(f"   Status: {response.json()}")
        else:
            print(f"❌ Webhook server error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to webhook server: {e}")
        return False
    
    # Test incoming call
    try:
        test_data = {
            "eventType": "IncomingCall",
            "callId": f"test_{int(time.time())}",
            "from": {"phoneNumber": "+1234567890"},
            "to": {"phoneNumber": "(513) 572-5833"},
            "direction": "inbound"
        }
        
        response = requests.post(
            "http://localhost:5000/webhook",
            json=test_data,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Test call processed successfully")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Test call failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Test call error: {e}")
        return False

def check_ngrok():
    """Check ngrok tunnel"""
    print("\n🔗 Checking ngrok tunnel...")
    
    try:
        response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
        if response.status_code == 200:
            tunnels = response.json().get("tunnels", [])
            if tunnels:
                public_url = tunnels[0].get("public_url", "")
                print(f"✅ Ngrok tunnel active: {public_url}")
                return public_url
            else:
                print("❌ No ngrok tunnels found")
                return None
        else:
            print(f"❌ Ngrok error: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Cannot connect to ngrok: {e}")
        return None

def check_ollama():
    """Check Ollama service"""
    print("\n🤖 Checking Ollama service...")
    
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            llama_models = [m for m in models if "llama" in m.get("name", "").lower()]
            print(f"✅ Ollama running, {len(llama_models)} Llama models found")
            return True
        else:
            print(f"❌ Ollama error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Voice AI System Test")
    print("=" * 50)
    
    # Check all components
    webhook_ok = test_webhook()
    ngrok_url = check_ngrok()
    ollama_ok = check_ollama()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"   Webhook Server: {'✅ OK' if webhook_ok else '❌ FAIL'}")
    print(f"   Ngrok Tunnel: {'✅ OK' if ngrok_url else '❌ FAIL'}")
    print(f"   Ollama Service: {'✅ OK' if ollama_ok else '❌ FAIL'}")
    
    if webhook_ok and ngrok_url and ollama_ok:
        print("\n🎉 All systems operational!")
        print(f"📞 Webhook URL: {ngrok_url}/webhook")
        print("🚀 System ready to receive calls!")
        
        print("\n📋 Next steps:")
        print("1. Configure RingCentral webhook to: " + ngrok_url + "/webhook")
        print("2. Set up call routing for number (513) 572-5833")
        print("3. Test with a real phone call")
    else:
        print("\n⚠️ Some components need attention:")
        if not webhook_ok:
            print("   - Start webhook server: python3.11 main.py")
        if not ngrok_url:
            print("   - Start ngrok: ngrok http 5000")
        if not ollama_ok:
            print("   - Start Ollama: ollama serve")

if __name__ == "__main__":
    main()
