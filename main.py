#!/usr/bin/env python3
"""
Main entry point for Voice AI System
PRIME CARGO LOGISTICS INC.
"""

import sys
import os
import logging
import signal
import time
import argparse
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from webhook_server import start_server
from voice_ai_engine import voice_ai_engine
from llm_handler import llm_handler
from speech_processor import speech_processor

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOGGING["level"]),
    format=Config.LOGGING["format"],
    handlers=[
        logging.FileHandler(Config.LOGGING["file"]),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class VoiceAISystem:
    """Main Voice AI System class"""
    
    def __init__(self):
        """Initialize the Voice AI system"""
        self.running = False
        self.start_time = None
        
    def start(self):
        """Start the Voice AI system"""
        try:
            logger.info("=" * 60)
            logger.info("Starting Voice AI System for PRIME CARGO LOGISTICS INC.")
            logger.info("=" * 60)
            
            # Check system requirements
            self._check_system_requirements()
            
            # Initialize components
            self._initialize_components()
            
            # Set up signal handlers
            self._setup_signal_handlers()
            
            # Mark as running
            self.running = True
            self.start_time = time.time()
            
            logger.info("Voice AI System started successfully!")
            logger.info(f"Webhook server will be available at: http://{Config.WEBHOOK['host']}:{Config.WEBHOOK['port']}")
            logger.info(f"Health check: http://{Config.WEBHOOK['host']}:{Config.WEBHOOK['port']}/health")
            logger.info(f"Metrics: http://{Config.WEBHOOK['host']}:{Config.WEBHOOK['port']}/metrics")
            logger.info("Press Ctrl+C to stop the system")
            
            # Start webhook server
            start_server()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            self.stop()
        except Exception as e:
            logger.error(f"Failed to start Voice AI system: {e}")
            self.stop()
            sys.exit(1)
    
    def stop(self):
        """Stop the Voice AI system"""
        if not self.running:
            return
            
        logger.info("Stopping Voice AI System...")
        
        try:
            # Clean up resources
            self._cleanup()
            
            # Calculate uptime
            if self.start_time:
                uptime = time.time() - self.start_time
                logger.info(f"System was running for {uptime:.1f} seconds")
            
            self.running = False
            logger.info("Voice AI System stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def _check_system_requirements(self):
        """Check if system meets requirements"""
        logger.info("Checking system requirements...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            raise RuntimeError("Python 3.8 or higher is required")
        
        # Check available memory
        try:
            import psutil
            memory = psutil.virtual_memory()
            if memory.total < 8 * 1024 * 1024 * 1024:  # 8GB
                logger.warning("Less than 8GB RAM available. Performance may be affected.")
        except ImportError:
            logger.warning("psutil not available, skipping memory check")
        
        # Check GPU availability
        if Config.PERFORMANCE["use_gpu"]:
            try:
                import torch
                if torch.cuda.is_available():
                    logger.info(f"GPU available: {torch.cuda.get_device_name(0)}")
                else:
                    logger.warning("GPU requested but not available. Falling back to CPU.")
                    Config.PERFORMANCE["use_gpu"] = False
            except ImportError:
                logger.warning("PyTorch not available, GPU check skipped")
        
        # Check required directories
        required_dirs = [
            Config.STORAGE["recordings_dir"],
            Config.STORAGE["logs_dir"],
            Config.STORAGE["temp_dir"]
        ]
        
        for directory in required_dirs:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.info(f"Directory ready: {directory}")
        
        logger.info("System requirements check completed")
    
    def _initialize_components(self):
        """Initialize all system components"""
        logger.info("Initializing system components...")
        
        try:
            # Initialize speech processor
            logger.info("Initializing speech processor...")
            speech_processor.initialize()
            
            # Check LLM service
            logger.info("Checking LLM service...")
            if not llm_handler.health_check():
                logger.warning("LLM service not available. Please ensure Ollama is running.")
            else:
                logger.info("LLM service is healthy")
            
            # Initialize Voice AI engine
            logger.info("Initializing Voice AI engine...")
            # Engine is already initialized when imported
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _cleanup(self):
        """Clean up system resources"""
        logger.info("Cleaning up resources...")
        
        try:
            # Clear conversation history
            llm_handler.clear_history()
            
            # Close any open files or connections
            # (Add specific cleanup code here if needed)
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Voice AI System for PRIME CARGO LOGISTICS INC.")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    
    args = parser.parse_args()
    
    # Set debug mode if requested
    if args.debug:
        Config.WEBHOOK["debug"] = True
        Config.LOGGING["level"] = "DEBUG"
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Debug mode enabled")
    
    # Create and start system
    system = VoiceAISystem()
    
    try:
        system.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"System error: {e}")
        sys.exit(1)
    finally:
        system.stop()

if __name__ == "__main__":
    main()
