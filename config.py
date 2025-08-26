"""
Configuration file for Voice AI System
PRIME CARGO LOGISTICS INC.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Main configuration class"""
    
    # RingCentral API Configuration
    RINGCENTRAL = {
        "client_id": os.getenv("RINGCENTRAL_CLIENT_ID", "bXCZ510zNmybxAUXGIZruT"),
        "client_secret": os.getenv("RINGCENTRAL_CLIENT_SECRET", "10hW9ccNfhyc1y69bQzdgnVUnFyf76B6qcmwOtypEGo7"),
        "server": os.getenv("RINGCENTRAL_SERVER", "https://platform.ringcentral.com"),
        "main_number": os.getenv("RINGCENTRAL_MAIN_NUMBER", "+15139283626"),       
        "webhook_url": os.getenv("WEBHOOK_URL", "https://9632ab98a232.ngrok-free.app/webhook"), 
        "webhook_secret": os.getenv("WEBHOOK_SECRET", "1Z7ztKD0I1gBu1QscmOBkonCn1tXG7LN"),
        "jwt_token": os.getenv("RINGCENTRAL_JWT_TOKEN", "eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbS9yZXN0YXBpL29hdXRoL3Rva2VuIiwic3ViIjoiMjA2OTkwOTAxOSIsImlzcyI6Imh0dHBzOi8vcGxhdGZvcm0ucmluZ2NlbnRyYWwuY29tIiwiZXhwIjozOTAzNjUxMzQyLCJpYXQiOjE3NTYxNjc2OTUsImp0aSI6IlpTckJuOHlFVDJLeEFjOXhmTlZ6ZncifQ.fHF6mXLa9wHygLYiFVQzIo4bKT8niwnYKD7PT7gFGoayZpDOkHwamesmXunn_IIY3rRT9Z2hXHgaJpdpW5ZRimaYOydcjGpj1HgdOxmTRBcYj6B4HWXb9YXO95Q2sfFLPS-3DwvcxeqNW8yoX3Cx31VpCfsybrvwq1NtDO73KulJYPByTSjoLQMj5to5gxRtKlqbhabj1o4YaeKkKb70_Sr-T0lXQS_93fOaPi0xP_AYNhDmDEQBZc1tvwUF7-ETj2Bv-EnfH5OxWfbRS3bSnZdRs1P-0TJg6SfNgwlAGNnMqEdpVyBMXt-02aQA8xgo1O9RDI-nSUXd2iKaA5CTAg"),
        "auth_method": os.getenv("RINGCENTRAL_AUTH_METHOD", "jwt")
    }
    
    # Webhook Server Configuration
    WEBHOOK = {
        "host": os.getenv("WEBHOOK_HOST", "0.0.0.0"),
        "port": int(os.getenv("WEBHOOK_PORT", "5000")),
        "debug": os.getenv("WEBHOOK_DEBUG", "False").lower() == "true",
        "ssl_context": None  # Set to SSL context for HTTPS
    }
    
    # Speech Processing Configuration
    SPEECH = {
        "whisper_model": os.getenv("WHISPER_MODEL", "base"),  # tiny, base, small, medium, large
        "whisper_device": os.getenv("WHISPER_DEVICE", "cuda" if os.getenv("USE_GPU", "True").lower() == "true" else "cpu"),
        "sample_rate": 16000,
        "chunk_duration": 30,  # seconds
        "vad_threshold": 0.5,
        "language": "en"
    }
    
    # TTS Configuration
    TTS = {
        "model_name": os.getenv("TTS_MODEL", "tts_models/en/vctk/vits"),  # Более качественная модель
        "device": os.getenv("TTS_DEVICE", "cuda" if os.getenv("USE_GPU", "True").lower() == "true" else "cpu"),
        "speaker": "p227",  # Дружелюбная и теплая женская диспетчер
        "speed": 1.15,  # Быстро и энергично как в тесте
        "volume": 1.2,  # Громко и позитивно
        "sample_rate": 22050,  # Высокое качество
        "use_phonemes": True,  # Использовать фонемы для лучшего произношения
        # Альтернативные модели для лучшего качества:
        "alternative_models": [
            "tts_models/en/vctk/vits",  # VCTK - много голосов, хорошее качество
            "tts_models/en/ljspeech/fast_pitch",  # FastPitch - быстрая и качественная
            "tts_models/en/ljspeech/glow-tts",  # Glow-TTS - естественный голос
            "tts_models/en/ljspeech/tacotron2-DDC"  # Tacotron2 - классическая модель
        ]
    }
    
    # LLM Configuration
    LLM = {
        "model": os.getenv("LLM_MODEL", "llama3.1:8b-instruct-q4_0"),
        "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
        "temperature": 0.7,
        "max_tokens": 400,  # Reduced for 8GB GPU
        "top_p": 0.9,
        "system_prompt": """You are a professional logistics dispatcher for PRIME CARGO LOGISTICS INC. 
        You help drivers with delivery information, routes, order status, and logistics issues.
        
        Key responsibilities:
        - Provide delivery addresses and route information
        - Check order status and tracking
        - Share contact information for receivers
        - Help with documentation (BOL, POD)
        - Assist with delivery problems and delays
        - Escalate complex issues to human dispatchers
        
        Always be:
        - Professional and courteous
        - Brief but informative (max 50 words)
        - Helpful and solution-oriented
        - Clear and easy to understand
        
        If you cannot help with a request, politely ask the driver to call the main dispatch line.
        """
    }
    
    # Audio Configuration
    AUDIO = {
        "input_device": int(os.getenv("AUDIO_INPUT_DEVICE", "0")),
        "output_device": int(os.getenv("AUDIO_OUTPUT_DEVICE", "0")),
        "channels": 1,
        "format": "wav",
        "quality": "high"
    }
    
    # Logging Configuration
    LOGGING = {
        "level": os.getenv("LOG_LEVEL", "INFO"),
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": "logs/voice_ai.log",
        "max_size": 10 * 1024 * 1024,  # 10MB
        "backup_count": 5
    }
    
    # Storage Configuration
    STORAGE = {
        "recordings_dir": "recordings",
        "logs_dir": "logs",
        "temp_dir": "temp",
        "max_recording_age": 30,  # days
        "max_storage_gb": 10
    }
    
    # Performance Configuration
    PERFORMANCE = {
        "max_concurrent_calls": int(os.getenv("MAX_CONCURRENT_CALLS", "5")),  # Reduced for RTX 4060
        "response_timeout": 30,  # seconds
        "call_timeout": 300,  # seconds
        "use_gpu": os.getenv("USE_GPU", "True").lower() == "true",
        "gpu_memory_fraction": 0.7  # Reduced for RTX 4060 8GB to prevent OOM
    }
    
    # Security Configuration
    SECURITY = {
        "enable_ssl": os.getenv("ENABLE_SSL", "False").lower() == "true",
        "ssl_cert": os.getenv("SSL_CERT", ""),
        "ssl_key": os.getenv("SSL_KEY", ""),
        "allowed_ips": os.getenv("ALLOWED_IPS", "").split(",") if os.getenv("ALLOWED_IPS") else [],
        "rate_limit": int(os.getenv("RATE_LIMIT", "100"))  # requests per minute
    }
    
    # Monitoring Configuration
    MONITORING = {
        "enable_metrics": os.getenv("ENABLE_METRICS", "True").lower() == "true",
        "metrics_port": int(os.getenv("METRICS_PORT", "9090")),
        "health_check_interval": 30,  # seconds
        "alert_email": os.getenv("ALERT_EMAIL", "")
    }

# Create directories if they don't exist
def create_directories():
    """Create necessary directories"""
    dirs = [
        Config.STORAGE["recordings_dir"],
        Config.STORAGE["logs_dir"],
        Config.STORAGE["temp_dir"]
    ]
    
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)

# Initialize directories
create_directories()
