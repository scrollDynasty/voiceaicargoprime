# Voice AI System Installation Guide
## PRIME CARGO LOGISTICS INC.

### 🚀 Automated Installation (Recommended)

The easiest way to install and set up the Voice AI system is using our automated installation script:

```bash
# Make the script executable
chmod +x install.sh

# Run the installation
./install.sh
```

The script will automatically:
- ✅ Check system requirements
- ✅ Install system dependencies
- ✅ Set up Python virtual environment
- ✅ Install all Python packages
- ✅ Download and configure Ollama
- ✅ Pull Llama 3.1 70B model
- ✅ Set up ngrok for webhooks
- ✅ Create all necessary directories
- ✅ Set up systemd service
- ✅ Create startup scripts

---

## 📋 System Requirements

### Hardware Requirements
- **CPU**: AMD Ryzen 9 or equivalent (multi-core recommended)
- **RAM**: 16GB minimum (32GB recommended for optimal performance)
- **GPU**: RTX 4060 8GB VRAM or better (CUDA support)
- **Storage**: 50GB+ free space for models and recordings
- **Network**: Stable internet connection for RingCentral API

### Software Requirements
- **OS**: Ubuntu 22.04 LTS / Kali Linux (other Linux distributions may work)
- **Python**: 3.8+ (tested with 3.11.2)
- **CUDA**: 11.8+ for GPU acceleration (optional but recommended)

---

## 🛠️ Manual Installation Steps

If you prefer manual installation or need to troubleshoot:

### 1. Update System Packages

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install System Dependencies

```bash
sudo apt install -y \
    curl wget git build-essential \
    python3-dev python3-pip python3-venv \
    ffmpeg portaudio19-dev libasound2-dev \
    libsndfile1-dev libssl-dev libffi-dev \
    pkg-config nvidia-cuda-toolkit
```

### 3. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

### 4. Install PyTorch with CUDA Support

```bash
# For CUDA 11.8
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Or for CPU-only (if no GPU)
pip install torch torchaudio
```

### 5. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 6. Install Ollama

```bash
# Download and install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
sudo systemctl enable ollama
sudo systemctl start ollama

# Wait for service to be ready
sleep 10

# Download Llama 3.1 70B model (this takes time!)
ollama pull llama3.1:70b-instruct-q4_0
```

### 7. Install ngrok for Webhooks

```bash
# Download ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# Configure ngrok (you'll need an account)
ngrok config add-authtoken YOUR_NGROK_TOKEN
```

### 8. Create Directories

```bash
mkdir -p logs recordings temp docs
```

### 9. Set Permissions

```bash
chmod +x *.sh main.py
```

---

## 🔧 Configuration

### 1. ngrok Setup

1. Sign up at [ngrok.com](https://ngrok.com)
2. Get your auth token from the dashboard
3. Configure ngrok:
   ```bash
   ngrok config add-authtoken YOUR_TOKEN
   ```

### 2. Start ngrok Tunnel

```bash
# Start tunnel for webhook
ngrok http 5000
```

Copy the https URL (e.g., `https://abc123.ngrok-free.app`)

### 3. Update Configuration

Edit the `.env` file and update the webhook URL:

```bash
WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app/webhook
```

### 4. RingCentral Webhook Configuration

1. Log into your RingCentral account
2. Go to Developer Console
3. Set webhook URL to: `https://your-ngrok-url.ngrok-free.app/webhook`
4. Enable telephony events

---

## 🚀 Starting the System

### Quick Start

```bash
./start.sh
```

### Background Mode

```bash
./start.sh --background
```

### Debug Mode

```bash
./start.sh --debug
```

### Using Systemd

```bash
# Start service
sudo systemctl start voiceai

# Enable auto-start
sudo systemctl enable voiceai

# Check status
sudo systemctl status voiceai
```

---

## 🔍 Verification

### 1. Check System Health

```bash
curl http://localhost:5000/health
```

Expected response:
```json
{
  "status": "healthy",
  "active_calls": 0,
  "llm_healthy": true,
  "speech_processor_initialized": true,
  "timestamp": "2024-01-01T12:00:00"
}
```

### 2. Check Ollama

```bash
ollama list
```

Should show `llama3.1:70b-instruct-q4_0` model.

### 3. Test Call

Call the number: **(513) 572-5833**

You should hear: "Welcome to Prime Cargo Logistics. I'm your AI assistant. How can I help you with your delivery today?"

---

## 📊 Monitoring

### View Logs

```bash
# Real-time logs
tail -f logs/voice_ai.log

# System service logs
sudo journalctl -u voiceai -f
```

### System Metrics

```bash
curl http://localhost:5000/metrics
```

### Active Calls

```bash
curl http://localhost:5000/api/calls
```

---

## 🛑 Stopping the System

### Normal Stop

```bash
./stop.sh
```

### Force Stop

```bash
./stop.sh --force
```

### Stop with Cleanup

```bash
./stop.sh --cleanup
```

---

## 🔄 Restart

```bash
# Normal restart
./restart.sh

# Quick restart
./restart.sh --quick

# Restart in debug mode
./restart.sh --debug
```

---

## 🚨 Troubleshooting

### Common Issues

#### 1. "Ollama service not available"

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve &

# Or use systemd
sudo systemctl start ollama
```

#### 2. "Model not found"

```bash
# Pull the model again
ollama pull llama3.1:70b-instruct-q4_0

# List available models
ollama list
```

#### 3. "CUDA out of memory"

Edit `config.py` and set:
```python
PERFORMANCE = {
    "use_gpu": False,  # Use CPU instead
    # ... other settings
}
```

#### 4. "Permission denied"

```bash
# Fix permissions
chmod +x *.sh
sudo chown -R $USER:$USER .
```

#### 5. "Port already in use"

```bash
# Find process using port 5000
sudo lsof -i :5000

# Kill the process
sudo kill -9 PID
```

### Getting Help

1. Check logs: `tail -f logs/voice_ai.log`
2. Check system status: `./start.sh --status`
3. Verify configuration: `python3 -c "from config import Config; print('Config OK')"`
4. Test components individually:
   ```bash
   python3 -c "import torch; print('PyTorch:', torch.__version__)"
   python3 -c "import whisper; print('Whisper: OK')"
   python3 -c "from TTS.api import TTS; print('TTS: OK')"
   ```

---

## 📈 Performance Optimization

### GPU Memory Management

For systems with limited VRAM:

```python
# In config.py
PERFORMANCE = {
    "gpu_memory_fraction": 0.6,  # Use 60% of GPU memory
    "use_gpu": True
}
```

### Model Selection

For faster responses but lower quality:

```python
# In config.py
SPEECH = {
    "whisper_model": "base",  # Instead of "large"
}

LLM = {
    "model": "llama3.1:8b-instruct-q4_0",  # Smaller model
}
```

### Concurrent Calls

```python
# In config.py
PERFORMANCE = {
    "max_concurrent_calls": 5,  # Reduce for limited resources
}
```

---

## 🔒 Security Considerations

1. **Firewall**: Only expose port 5000 to trusted networks
2. **ngrok**: Use auth tokens and restrict access
3. **Logs**: Regularly rotate and backup logs
4. **Updates**: Keep system and dependencies updated
5. **SSL**: Enable HTTPS in production

---

## 📝 Next Steps

After successful installation:

1. ✅ Test the system with a phone call
2. ✅ Configure RingCentral webhooks
3. ✅ Set up monitoring and alerts
4. ✅ Train staff on system usage
5. ✅ Plan backup and disaster recovery

---

**🎉 Congratulations! Your Voice AI System is ready for production use!**

For support, please refer to the troubleshooting section or contact the development team.

**PRIME CARGO LOGISTICS INC.** - Your reliable partner in logistics! 🚛