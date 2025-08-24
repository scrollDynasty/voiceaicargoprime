#!/bin/bash

#===============================================================================
# Voice AI System Startup Script for PRIME CARGO LOGISTICS INC.
# Скрипт запуска системы Voice AI
#===============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
    echo "        Starting Voice AI System for PRIME CARGO LOGISTICS INC."
    echo "============================================================================"
    echo -e "${NC}"
}

check_dependencies() {
    log "Checking dependencies..."
    
    # Check if virtual environment exists
    if [[ ! -d "venv" ]]; then
        error "Virtual environment not found. Please run ./install.sh first."
    fi
    
    # Check if Ollama is running
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        warn "Ollama service not detected. Starting Ollama..."
        if command -v ollama &> /dev/null; then
            ollama serve &
            sleep 5
            if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                error "Failed to start Ollama service"
            fi
            log "Ollama service started"
        else
            error "Ollama not installed. Please run ./install.sh first."
        fi
    else
        log "Ollama service is running"
    fi
    
    # Check if required model is available
    if ! ollama list | grep -q "llama3.1:70b-instruct-q4_0"; then
        warn "Required model not found. Downloading..."
        ollama pull llama3.1:70b-instruct-q4_0
    fi
    
    log "Dependencies check completed"
}

start_system() {
    log "Starting Voice AI System..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Create necessary directories
    mkdir -p logs recordings temp
    
    # Check for existing process
    if pgrep -f "python3 main.py" > /dev/null; then
        warn "Voice AI System is already running"
        info "Use './stop.sh' to stop the current instance first"
        exit 1
    fi
    
    # Set environment variables
    export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
    
    # Ollama GPU optimization for RTX 4060 8GB
    export OLLAMA_NUM_PARALLEL=2
    export OLLAMA_MAX_LOADED_MODELS=1
    export OLLAMA_GPU_MEMORY_FRACTION=0.7
    
    # Start the system
    log "Launching Voice AI System..."
    if [[ "$1" == "--debug" ]]; then
        python3 main.py --debug "$@"
    elif [[ "$1" == "--background" ]]; then
        nohup python3 main.py > logs/voice_ai.log 2>&1 &
        echo $! > voice_ai.pid
        log "Voice AI System started in background (PID: $(cat voice_ai.pid))"
        log "Check logs with: tail -f logs/voice_ai.log"
    else
        python3 main.py "$@"
    fi
}

show_status() {
    log "Checking system status..."
    
    # Check if process is running
    if pgrep -f "python3 main.py" > /dev/null; then
        log "Voice AI System is running"
        
        # Check health endpoint
        if curl -s http://localhost:5000/health > /dev/null 2>&1; then
            log "Health check: PASSED"
            curl -s http://localhost:5000/health | python3 -m json.tool
        else
            warn "Health check: FAILED"
        fi
    else
        warn "Voice AI System is not running"
    fi
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --debug      Start in debug mode"
    echo "  --background Start in background mode"
    echo "  --status     Show system status"
    echo "  --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                Start normally"
    echo "  $0 --debug       Start with debug logging"
    echo "  $0 --background  Start in background"
    echo "  $0 --status      Check if system is running"
}

# Main execution
case "$1" in
    --help|-h)
        show_help
        ;;
    --status)
        show_status
        ;;
    *)
        print_banner
        check_dependencies
        start_system "$@"
        ;;
esac