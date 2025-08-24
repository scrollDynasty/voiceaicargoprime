#!/bin/bash

#===============================================================================
# Voice AI System Installation Script for PRIME CARGO LOGISTICS INC.
# Автоматическая установка всех компонентов системы
#===============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

print_banner() {
    echo -e "${BLUE}"
    echo "============================================================================"
    echo "   Voice AI System Installation for PRIME CARGO LOGISTICS INC."
    echo "============================================================================"
    echo -e "${NC}"
}

# Check system requirements
check_system() {
    log "Checking system requirements..."
    
    # Check OS
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        error "This script only supports Linux systems"
    fi
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed"
    fi
    
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    log "Python version: $python_version"
    
    # Check if Python version is >= 3.8
    python_major=$(python3 -c "import sys; print(sys.version_info.major)")
    python_minor=$(python3 -c "import sys; print(sys.version_info.minor)")
    
    if [[ $python_major -lt 3 ]] || [[ $python_major -eq 3 && $python_minor -lt 8 ]]; then
        error "Python 3.8 or higher is required. Current version: $python_version"
    fi
    
    # Check available memory
    total_mem=$(free -g | awk 'NR==2{print $2}')
    if [[ $total_mem -lt 8 ]]; then
        warn "Less than 8GB RAM detected. System may run slower."
    else
        log "Memory check passed: ${total_mem}GB available"
    fi
    
    # Check disk space (need at least 10GB)
    available_space=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $available_space -lt 10 ]]; then
        error "Insufficient disk space. Need at least 10GB, available: ${available_space}GB"
    fi
    
    log "System requirements check completed successfully"
}

# Install system dependencies
install_system_deps() {
    log "Installing system dependencies..."
    
    # Update package list
    sudo apt-get update -qq
    
    # Install essential packages
    sudo apt-get install -y \
        curl \
        wget \
        git \
        build-essential \
        python3-dev \
        python3-pip \
        python3-venv \
        ffmpeg \
        portaudio19-dev \
        libasound2-dev \
        libsndfile1-dev \
        libssl-dev \
        libffi-dev \
        pkg-config \
        nvidia-cuda-toolkit \
        || warn "Some packages might not be available on your system"
    
    log "System dependencies installed"
}

# Create virtual environment
setup_venv() {
    log "Setting up Python virtual environment..."
    
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        log "Virtual environment created"
    else
        log "Virtual environment already exists"
    fi
    
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    
    log "Virtual environment setup completed"
}

# Install Python dependencies
install_python_deps() {
    log "Installing Python dependencies..."
    
    source venv/bin/activate
    
    # Install PyTorch with CUDA support
    log "Installing PyTorch with CUDA support..."
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118 || {
        warn "CUDA version of PyTorch failed to install, installing CPU version..."
        pip install torch torchaudio
    }
    
    # Install other dependencies
    log "Installing other Python packages..."
    pip install -r requirements.txt
    
    log "Python dependencies installed"
}

# Install and configure Ollama
install_ollama() {
    log "Installing Ollama..."
    
    if ! command -v ollama &> /dev/null; then
        curl -fsSL https://ollama.ai/install.sh | sh
        log "Ollama installed"
    else
        log "Ollama is already installed"
    fi
    
    # Start Ollama service
    log "Starting Ollama service..."
    sudo systemctl enable ollama || true
    sudo systemctl start ollama || {
        # If systemd service doesn't exist, start manually
        ollama serve &
        sleep 5
    }
    
    # Wait for Ollama to be ready
    log "Waiting for Ollama to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            log "Ollama is ready"
            break
        fi
        sleep 2
    done
    
    # Pull Llama model
    log "Downloading Llama 3.1 70B model (this may take a while)..."
    ollama pull llama3.1:70b-instruct-q4_0 || error "Failed to download Llama model"
    
    log "Ollama setup completed"
}

# Set up ngrok for webhook
setup_ngrok() {
    log "Setting up ngrok for webhook tunneling..."
    
    if ! command -v ngrok &> /dev/null; then
        # Download and install ngrok
        wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
        tar xzf ngrok-v3-stable-linux-amd64.tgz
        sudo mv ngrok /usr/local/bin/
        rm ngrok-v3-stable-linux-amd64.tgz
        log "ngrok installed"
    else
        log "ngrok is already installed"
    fi
    
    warn "Please configure ngrok with your auth token:"
    warn "1. Sign up at https://ngrok.com"
    warn "2. Get your auth token from dashboard"
    warn "3. Run: ngrok config add-authtoken YOUR_TOKEN"
    warn "4. Update config.py with your ngrok tunnel URL"
}

# Create directories
create_directories() {
    log "Creating necessary directories..."
    
    mkdir -p logs recordings temp docs
    
    log "Directories created"
}

# Set permissions
set_permissions() {
    log "Setting file permissions..."
    
    chmod +x main.py
    chmod +x install.sh
    chmod 755 .
    
    log "Permissions set"
}

# Create startup scripts
create_startup_scripts() {
    log "Creating startup scripts..."
    
    # Create start script
    cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 main.py "$@"
EOF
    
    # Create stop script
    cat > stop.sh << 'EOF'
#!/bin/bash
pkill -f "python3 main.py"
pkill -f "voice_ai"
echo "Voice AI System stopped"
EOF
    
    # Create restart script
    cat > restart.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./stop.sh
sleep 2
./start.sh
EOF
    
    chmod +x start.sh stop.sh restart.sh
    
    log "Startup scripts created"
}

# Create systemd service
create_systemd_service() {
    log "Creating systemd service..."
    
    current_dir=$(pwd)
    current_user=$(whoami)
    
    sudo tee /etc/systemd/system/voiceai.service > /dev/null << EOF
[Unit]
Description=Voice AI System for PRIME CARGO LOGISTICS INC.
After=network.target
Wants=network.target

[Service]
Type=simple
User=$current_user
WorkingDirectory=$current_dir
Environment=PATH=$current_dir/venv/bin
ExecStart=$current_dir/venv/bin/python $current_dir/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable voiceai
    
    log "Systemd service created and enabled"
}

# Test installation
test_installation() {
    log "Testing installation..."
    
    source venv/bin/activate
    
    # Test Python imports
    python3 -c "
import torch
import whisper
import TTS
import ollama
import flask
import ringcentral
print('All required packages imported successfully')
"
    
    # Test Ollama connection
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log "Ollama connection test passed"
    else
        warn "Ollama connection test failed - service may not be running"
    fi
    
    log "Installation test completed"
}

# Create .env file
create_env_file() {
    log "Creating environment configuration file..."
    
    if [[ ! -f ".env" ]]; then
        cat > .env << 'EOF'
# RingCentral API Configuration
RINGCENTRAL_CLIENT_ID=dxyRUshmpEBeycpG7qfdti
RINGCENTRAL_CLIENT_SECRET=8eviWNljyqecloFZ5F18jT9MKfuXpxLTPcukwUvuh3j2
RINGCENTRAL_SERVER=https://platform.ringcentral.com
RINGCENTRAL_USERNAME=Primecargo07@gmail.com
RINGCENTRAL_PASSWORD=Pcl2024$!
RINGCENTRAL_MAIN_NUMBER=(513) 572-5833

# Webhook Configuration (Update with your ngrok URL)
WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app/webhook
WEBHOOK_SECRET=c828fad557ae2bb7e6ea8488b5a764124e1c7d619187b46f80d83a7541ea0f6a

# System Configuration
USE_GPU=True
LOG_LEVEL=INFO
MAX_CONCURRENT_CALLS=10

# LLM Configuration
LLM_MODEL=llama3.1:70b-instruct-q4_0
OLLAMA_URL=http://localhost:11434

# Speech Configuration
WHISPER_MODEL=base
TTS_MODEL=tts_models/en/vctk/vits
EOF
        log "Environment file created"
        warn "Please update .env file with your actual ngrok URL"
    else
        log "Environment file already exists"
    fi
}

# Print final instructions
print_final_instructions() {
    echo -e "${GREEN}"
    echo "============================================================================"
    echo "                    INSTALLATION COMPLETED SUCCESSFULLY!"
    echo "============================================================================"
    echo -e "${NC}"
    
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Configure ngrok:"
    echo "   - Sign up at https://ngrok.com"
    echo "   - Get your auth token"
    echo "   - Run: ngrok config add-authtoken YOUR_TOKEN"
    echo ""
    echo "2. Start ngrok tunnel:"
    echo "   - Run: ngrok http 5000"
    echo "   - Copy the https URL (e.g., https://abc123.ngrok-free.app)"
    echo ""
    echo "3. Update configuration:"
    echo "   - Edit .env file and update WEBHOOK_URL with your ngrok URL"
    echo ""
    echo "4. Start the system:"
    echo "   - Run: ./start.sh"
    echo "   - Or use systemd: sudo systemctl start voiceai"
    echo ""
    echo "5. Test the system:"
    echo "   - Check health: curl http://localhost:5000/health"
    echo "   - Call the number: (513) 572-5833"
    echo ""
    echo -e "${YELLOW}Configuration files:${NC}"
    echo "   - config.py - Main configuration"
    echo "   - .env - Environment variables"
    echo "   - logs/ - Log files"
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo "   - Start: ./start.sh"
    echo "   - Stop: ./stop.sh"
    echo "   - Restart: ./restart.sh"
    echo "   - Status: sudo systemctl status voiceai"
    echo "   - Logs: tail -f logs/voice_ai.log"
    echo ""
    echo -e "${GREEN}PRIME CARGO LOGISTICS INC. - Voice AI System Ready! 🚛${NC}"
}

# Main installation function
main() {
    print_banner
    
    log "Starting Voice AI System installation..."
    
    check_system
    install_system_deps
    setup_venv
    install_python_deps
    install_ollama
    setup_ngrok
    create_directories
    create_env_file
    set_permissions
    create_startup_scripts
    create_systemd_service
    test_installation
    
    print_final_instructions
    
    log "Installation completed successfully!"
}

# Run main function
main "$@"