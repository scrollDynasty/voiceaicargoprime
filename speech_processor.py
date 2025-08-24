"""
Speech Processing Module
Handles Speech-to-Text (Whisper) and Text-to-Speech (Coqui TTS)
"""

import os
import tempfile
import logging
import numpy as np
import torch
import whisper
from TTS.api import TTS
from pydub import AudioSegment
import soundfile as sf
import librosa
from typing import Optional, Tuple
import asyncio
import threading
from queue import Queue

from config import Config

logger = logging.getLogger(__name__)

class SpeechProcessor:
    """Handles speech recognition and synthesis"""
    
    def __init__(self):
        """Initialize speech processor with Whisper and TTS models"""
        self.whisper_model = None
        self.tts_model = None
        self.initialized = False
        self._init_lock = threading.Lock()
        
    def initialize(self):
        """Initialize speech models"""
        if self.initialized:
            return
            
        with self._init_lock:
            if self.initialized:
                return
                
            try:
                logger.info("Initializing Whisper model...")
                self.whisper_model = whisper.load_model(
                    Config.SPEECH["whisper_model"],
                    device=Config.SPEECH["whisper_device"]
                )
                
                logger.info("Initializing TTS model...")
                self.tts_model = TTS(
                    model_name=Config.TTS["model_name"],
                    progress_bar=False
                )
                
                self.initialized = True
                logger.info("Speech processor initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize speech processor: {e}")
                raise
    
    def transcribe_audio(self, audio_data: bytes, language: str = "en") -> str:
        """
        Transcribe audio to text using Whisper
        
        Args:
            audio_data: Raw audio bytes
            language: Language code (default: "en")
            
        Returns:
            Transcribed text
        """
        if not self.initialized:
            self.initialize()
            
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            # Transcribe with Whisper
            result = self.whisper_model.transcribe(
                temp_file_path,
                language=language,
                task="transcribe"
            )
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            transcribed_text = result["text"].strip()
            logger.info(f"Transcribed: {transcribed_text}")
            
            return transcribed_text
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""
    
    def synthesize_speech(self, text: str, output_path: str = None) -> bytes:
        """
        Convert text to speech using Coqui TTS
        
        Args:
            text: Text to synthesize
            output_path: Optional path to save audio file
            
        Returns:
            Audio data as bytes
        """
        if not self.initialized:
            self.initialize()
            
        try:
            # Generate temporary output path if not provided
            if not output_path:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    output_path = temp_file.name
            
            # Synthesize speech with improved settings
            self.tts_model.tts_to_file(
                text=text,
                file_path=output_path,
                speaker=Config.TTS["speaker"],
                speed=Config.TTS["speed"],
                sample_rate=Config.TTS["sample_rate"]
            )
            
            # Read audio data
            with open(output_path, "rb") as f:
                audio_data = f.read()
            
            # Clean up temporary file if we created it
            if not output_path or "tmp" in output_path:
                os.unlink(output_path)
            
            logger.info(f"Synthesized speech for: {text[:50]}...")
            return audio_data
            
        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            return b""
    
    def process_audio_chunk(self, audio_chunk: bytes) -> str:
        """
        Process a single audio chunk for real-time transcription
        
        Args:
            audio_chunk: Audio chunk bytes
            
        Returns:
            Transcribed text
        """
        try:
            # Convert audio chunk to proper format
            audio_array, sample_rate = sf.read(io.BytesIO(audio_chunk))
            
            # Resample if necessary
            if sample_rate != Config.SPEECH["sample_rate"]:
                audio_array = librosa.resample(
                    audio_array, 
                    orig_sr=sample_rate, 
                    target_sr=Config.SPEECH["sample_rate"]
                )
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                sf.write(temp_file.name, audio_array, Config.SPEECH["sample_rate"])
                temp_file_path = temp_file.name
            
            # Transcribe
            result = self.whisper_model.transcribe(
                temp_file_path,
                language=Config.SPEECH["language"],
                task="transcribe"
            )
            
            # Clean up
            os.unlink(temp_file_path)
            
            return result["text"].strip()
            
        except Exception as e:
            logger.error(f"Chunk processing failed: {e}")
            return ""
    
    def detect_speech_activity(self, audio_data: bytes) -> bool:
        """
        Detect if audio contains speech activity
        
        Args:
            audio_data: Audio data bytes
            
        Returns:
            True if speech detected, False otherwise
        """
        try:
            # Convert to numpy array
            audio_array, sample_rate = sf.read(io.BytesIO(audio_data))
            
            # Calculate RMS energy
            rms = np.sqrt(np.mean(audio_array**2))
            
            # Simple threshold-based detection
            threshold = Config.SPEECH["vad_threshold"]
            return rms > threshold
            
        except Exception as e:
            logger.error(f"Speech activity detection failed: {e}")
            return False
    
    def get_audio_duration(self, audio_data: bytes) -> float:
        """
        Get duration of audio in seconds
        
        Args:
            audio_data: Audio data bytes
            
        Returns:
            Duration in seconds
        """
        try:
            audio_array, sample_rate = sf.read(io.BytesIO(audio_data))
            return len(audio_array) / sample_rate
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 0.0
    
    def convert_audio_format(self, audio_data: bytes, target_format: str = "wav") -> bytes:
        """
        Convert audio to different format
        
        Args:
            audio_data: Source audio data
            target_format: Target format (wav, mp3, etc.)
            
        Returns:
            Converted audio data
        """
        try:
            # Load audio with pydub
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Export to target format
            output = io.BytesIO()
            audio.export(output, format=target_format)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Audio format conversion failed: {e}")
            return audio_data

# Global speech processor instance
speech_processor = SpeechProcessor()

# Async wrapper functions for non-blocking operations
async def async_transcribe(audio_data: bytes, language: str = "en") -> str:
    """Async wrapper for transcription"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        speech_processor.transcribe_audio, 
        audio_data, 
        language
    )

async def async_synthesize(text: str, output_path: str = None) -> bytes:
    """Async wrapper for speech synthesis"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        speech_processor.synthesize_speech,
        text,
        output_path
    )
