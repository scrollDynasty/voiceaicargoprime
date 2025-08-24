# 🚀 Quick Start Guide - Voice AI System

## PRIME CARGO LOGISTICS INC.

### ⚡ Installation in 3 Steps

#### 1. Download and Install
```bash
# Автоматическая установка одной командой
chmod +x install.sh && ./install.sh
```

#### 2. Configure ngrok
```bash
# Получите токен на https://ngrok.com
ngrok config add-authtoken YOUR_TOKEN

# Запустите туннель
ngrok http 5000
```

#### 3. Update Configuration & Start
```bash
# Скопируйте ngrok URL и обновите .env файл
cp .env.example .env
# Отредактируйте WEBHOOK_URL в .env

# Запустите систему
./start.sh
```

---

## 📞 Testing the System

1. **Health Check**
   ```bash
   curl http://localhost:5000/health
   ```

2. **Test Call**
   Call: **(513) 572-5833**
   
   Expected: "Welcome to Prime Cargo Logistics..."

3. **Check Logs**
   ```bash
   tail -f logs/voice_ai.log
   ```

---

## 🎯 Common Commands

```bash
# Start system
./start.sh

# Start in background
./start.sh --background

# Stop system
./stop.sh

# Restart system
./restart.sh

# Check status
./start.sh --status

# Test voices
./test_voices.py
```

---

## 🔧 Configuration Files

- **`.env`** - Environment variables
- **`config.py`** - Main configuration
- **`logs/voice_ai.log`** - System logs

---

## 🚨 Troubleshooting

### Problem: "Ollama not running"
```bash
ollama serve &
ollama pull llama3.1:70b-instruct-q4_0
```

### Problem: "GPU out of memory"
```bash
# Edit .env file
USE_GPU=False
```

### Problem: "Port already in use"
```bash
sudo lsof -i :5000
sudo kill -9 PID
```

---

## 📊 System Monitoring

- **Health**: http://localhost:5000/health
- **Metrics**: http://localhost:5000/metrics
- **Config**: http://localhost:5000/config
- **Logs**: `tail -f logs/voice_ai.log`

---

## 🎤 Voice AI Features

### Supported Logistics Queries:
- "What's the delivery address for load #12345?"
- "I'm having trouble finding the dock"
- "The customer is not available, what should I do?"
- "I need the contact number for the receiver"
- "There's a problem with the paperwork"

### AI Capabilities:
- ✅ Professional English responses
- ✅ Logistics terminology understanding
- ✅ Multiple concurrent calls
- ✅ Call recording and logging
- ✅ Automatic escalation for complex issues

---

## 🔄 System Updates

```bash
# Stop system
./stop.sh

# Update code
git pull

# Restart system
./start.sh
```

---

## 🆘 Support

1. Check **[INSTALL_GUIDE.md](INSTALL_GUIDE.md)** for detailed instructions
2. View logs: `tail -f logs/voice_ai.log`
3. Test individual components:
   ```bash
   python3 -c "import torch; print('PyTorch OK')"
   python3 -c "import whisper; print('Whisper OK')"
   python3 -c "from TTS.api import TTS; print('TTS OK')"
   curl http://localhost:11434/api/tags  # Ollama check
   ```

---

**🎉 Your Voice AI System is ready for Prime Cargo Logistics! 🚛**

For any issues, refer to the full documentation or contact support.