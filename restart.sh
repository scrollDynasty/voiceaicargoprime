#!/bin/bash

#===============================================================================
# Voice AI System Restart Script for PRIME CARGO LOGISTICS INC.
# Скрипт перезапуска системы Voice AI
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
    echo "       Restarting Voice AI System for PRIME CARGO LOGISTICS INC."
    echo "============================================================================"
    echo -e "${NC}"
}

restart_system() {
    log "Restarting Voice AI System..."
    
    # Stop the system
    log "Stopping current instance..."
    ./stop.sh --cleanup
    
    # Wait a moment
    sleep 3
    
    # Check if stopped
    if pgrep -f "python3 main.py" > /dev/null; then
        error "Failed to stop the system. Please use './stop.sh --force' first."
    fi
    
    # Start the system
    log "Starting new instance..."
    ./start.sh "$@"
}

quick_restart() {
    log "Quick restart (no cleanup)..."
    
    # Stop without cleanup
    ./stop.sh
    sleep 2
    
    # Start again
    ./start.sh "$@"
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --quick      Quick restart without cleanup"
    echo "  --debug      Restart in debug mode"
    echo "  --background Restart in background mode"
    echo "  --help       Show this help message"
    echo ""
    echo "All start.sh options are also supported:"
    echo "  $0 --debug       Restart in debug mode"
    echo "  $0 --background  Restart in background"
}

# Main execution
case "$1" in
    --help|-h)
        show_help
        ;;
    --quick)
        print_banner
        quick_restart "${@:2}"
        ;;
    *)
        print_banner
        restart_system "$@"
        ;;
esac