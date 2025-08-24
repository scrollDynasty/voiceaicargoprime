#!/bin/bash

#===============================================================================
# Voice AI System Stop Script for PRIME CARGO LOGISTICS INC.
# Скрипт остановки системы Voice AI
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
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

print_banner() {
    echo -e "${BLUE}"
    echo "============================================================================"
    echo "        Stopping Voice AI System for PRIME CARGO LOGISTICS INC."
    echo "============================================================================"
    echo -e "${NC}"
}

stop_system() {
    log "Stopping Voice AI System..."
    
    # Check if system is running
    if ! pgrep -f "python3 main.py" > /dev/null; then
        warn "Voice AI System is not running"
        return 0
    fi
    
    # Try graceful shutdown first
    log "Attempting graceful shutdown..."
    pkill -TERM -f "python3 main.py"
    
    # Wait for graceful shutdown
    sleep 5
    
    # Check if still running
    if pgrep -f "python3 main.py" > /dev/null; then
        warn "Graceful shutdown failed, forcing termination..."
        pkill -KILL -f "python3 main.py"
        sleep 2
    fi
    
    # Clean up PID file if exists
    if [[ -f "voice_ai.pid" ]]; then
        rm -f voice_ai.pid
        log "Cleaned up PID file"
    fi
    
    # Verify shutdown
    if ! pgrep -f "python3 main.py" > /dev/null; then
        log "Voice AI System stopped successfully"
    else
        error "Failed to stop Voice AI System"
    fi
}

force_stop() {
    log "Force stopping all Voice AI processes..."
    
    # Kill all related processes
    pkill -9 -f "python3 main.py" 2>/dev/null || true
    pkill -9 -f "voice_ai" 2>/dev/null || true
    pkill -9 -f "webhook_server" 2>/dev/null || true
    
    # Clean up files
    rm -f voice_ai.pid
    
    log "Force stop completed"
}

cleanup_resources() {
    log "Cleaning up temporary resources..."
    
    # Clean up temporary files
    if [[ -d "temp" ]]; then
        find temp -type f -name "*.wav" -mtime +1 -delete 2>/dev/null || true
        find temp -type f -name "*.tmp" -delete 2>/dev/null || true
    fi
    
    # Rotate logs if they're too large
    if [[ -f "logs/voice_ai.log" ]] && [[ $(stat -c%s "logs/voice_ai.log") -gt 50000000 ]]; then # 50MB
        mv logs/voice_ai.log logs/voice_ai.log.old
        log "Log file rotated"
    fi
    
    log "Cleanup completed"
}

show_status() {
    if pgrep -f "python3 main.py" > /dev/null; then
        echo -e "${GREEN}Voice AI System is RUNNING${NC}"
        echo "PIDs: $(pgrep -f 'python3 main.py' | tr '\n' ' ')"
    else
        echo -e "${YELLOW}Voice AI System is STOPPED${NC}"
    fi
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --force      Force stop (kill -9)"
    echo "  --cleanup    Clean up temporary files after stop"
    echo "  --status     Show running status"
    echo "  --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0           Normal stop"
    echo "  $0 --force   Force stop all processes"
    echo "  $0 --cleanup Stop and clean up files"
}

# Main execution
case "$1" in
    --help|-h)
        show_help
        ;;
    --force)
        print_banner
        force_stop
        ;;
    --cleanup)
        print_banner
        stop_system
        cleanup_resources
        ;;
    --status)
        show_status
        ;;
    *)
        print_banner
        stop_system
        ;;
esac