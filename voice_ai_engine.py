"""
Voice AI Engine
Main engine that coordinates all components of the Voice AI system
"""

import logging
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid
import threading
from dataclasses import dataclass
from enum import Enum

from speech_processor import speech_processor, async_transcribe, async_synthesize
from llm_handler import llm_handler, generate_ai_response
from config import Config

logger = logging.getLogger(__name__)

class CallState(Enum):
    """Call states"""
    RINGING = "ringing"
    ANSWERED = "answered"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ENDED = "ended"
    ERROR = "error"

@dataclass
class CallSession:
    """Call session data"""
    call_id: str
    phone_number: str
    start_time: datetime
    state: CallState
    conversation_history: List[Dict[str, str]]
    audio_buffer: bytes
    last_activity: datetime
    
    def __post_init__(self):
        self.conversation_history = []
        self.audio_buffer = b""
        self.last_activity = self.start_time

class VoiceAIEngine:
    """Main Voice AI engine"""
    
    def __init__(self):
        """Initialize Voice AI engine"""
        self.active_calls: Dict[str, CallSession] = {}
        self.call_lock = threading.Lock()
        
        # Performance metrics
        self.total_calls = 0
        self.successful_calls = 0
        self.average_call_duration = 0.0
        
        # Initialize components
        self._initialize_components()
        
    def _initialize_components(self):
        """Initialize all AI components"""
        try:
            logger.info("Initializing Voice AI components...")
            
            # Initialize speech processor
            speech_processor.initialize()
            
            # Check LLM health
            if not llm_handler.health_check():
                logger.warning("LLM service not available")
            
            logger.info("Voice AI components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    async def handle_incoming_call(self, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming call from RingCentral
        
        Args:
            call_data: Call data from RingCentral webhook
            
        Returns:
            Response data for RingCentral
        """
        call_id = call_data.get("callId", str(uuid.uuid4()))
        phone_number = call_data.get("from", {}).get("phoneNumber", "Unknown")
        
        logger.info(f"Handling incoming call {call_id} from {phone_number}")
        
        # Check if we can handle more calls
        if len(self.active_calls) >= Config.PERFORMANCE["max_concurrent_calls"]:
            logger.warning("Maximum concurrent calls reached")
            return self._create_reject_response(call_id, "System busy")
        
        # Create call session
        session = CallSession(
            call_id=call_id,
            phone_number=phone_number,
            start_time=datetime.now(),
            state=CallState.RINGING,
            conversation_history=[],
            audio_buffer=b"",
            last_activity=datetime.now()
        )
        
        with self.call_lock:
            self.active_calls[call_id] = session
        
        self.total_calls += 1
        
        try:
            # Answer the call
            response = await self._answer_call(call_id)
            
            # Start conversation loop
            asyncio.create_task(self._conversation_loop(call_id))
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to handle call {call_id}: {e}")
            await self._end_call(call_id, "Error occurred")
            return self._create_error_response(call_id, str(e))
    
    async def _answer_call(self, call_id: str) -> Dict[str, Any]:
        """Answer incoming call"""
        session = self.active_calls.get(call_id)
        if not session:
            raise ValueError(f"Call session {call_id} not found")
        
        session.state = CallState.ANSWERED
        session.last_activity = datetime.now()
        
        # Generate welcome message
        welcome_text = "Welcome to Prime Cargo Logistics. I'm your AI assistant. How can I help you with your delivery today?"
        
        # Synthesize welcome message
        welcome_audio = await async_synthesize(welcome_text)
        
        # Update session
        session.conversation_history.append({
            "role": "assistant",
            "content": welcome_text,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Answered call {call_id}")
        
        return {
            "callId": call_id,
            "action": "answer",
            "audio": welcome_audio,
            "text": welcome_text
        }
    
    async def _conversation_loop(self, call_id: str):
        """Main conversation loop for a call"""
        session = self.active_calls.get(call_id)
        if not session:
            return
        
        try:
            while session.state not in [CallState.ENDED, CallState.ERROR]:
                # Check for timeout
                if (datetime.now() - session.last_activity).seconds > Config.PERFORMANCE["call_timeout"]:
                    logger.info(f"Call {call_id} timed out")
                    break
                
                # Listen for user input
                session.state = CallState.LISTENING
                user_audio = await self._listen_for_input(call_id)
                
                if not user_audio:
                    # No input received, continue listening
                    continue
                
                # Process user input
                session.state = CallState.PROCESSING
                response = await self._process_user_input(call_id, user_audio)
                
                if response:
                    # Speak response
                    session.state = CallState.SPEAKING
                    await self._speak_response(call_id, response)
                
                session.last_activity = datetime.now()
                
        except Exception as e:
            logger.error(f"Conversation loop error for call {call_id}: {e}")
            session.state = CallState.ERROR
        
        finally:
            await self._end_call(call_id, "Conversation ended")
    
    async def _listen_for_input(self, call_id: str) -> Optional[bytes]:
        """
        Listen for user input (simulated - in real implementation this would
        receive audio from RingCentral)
        
        Args:
            call_id: Call identifier
            
        Returns:
            Audio data or None if no input
        """
        session = self.active_calls.get(call_id)
        if not session:
            return None
        
        # In real implementation, this would receive audio from RingCentral
        # For now, we'll simulate with a delay
        await asyncio.sleep(2)
        
        # Return simulated audio data (empty for now)
        return b""
    
    async def _process_user_input(self, call_id: str, audio_data: bytes) -> Optional[str]:
        """
        Process user audio input
        
        Args:
            call_id: Call identifier
            audio_data: Audio data from user
            
        Returns:
            Response text or None
        """
        session = self.active_calls.get(call_id)
        if not session:
            return None
        
        try:
            # Transcribe audio to text
            user_text = await async_transcribe(audio_data)
            
            if not user_text:
                return "I didn't catch that. Could you please repeat?"
            
            # Add to conversation history
            session.conversation_history.append({
                "role": "user",
                "content": user_text,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"User input for call {call_id}: {user_text}")
            
            # Generate AI response
            ai_response = await generate_ai_response(user_text)
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Failed to process user input for call {call_id}: {e}")
            return "I'm having trouble understanding. Please call our main dispatch line for assistance."
    
    async def _speak_response(self, call_id: str, response_text: str):
        """
        Synthesize and speak response
        
        Args:
            call_id: Call identifier
            response_text: Text to speak
        """
        session = self.active_calls.get(call_id)
        if not session:
            return
        
        try:
            # Synthesize speech
            audio_data = await async_synthesize(response_text)
            
            # Add to conversation history
            session.conversation_history.append({
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # In real implementation, send audio to RingCentral
            logger.info(f"Spoke response for call {call_id}: {response_text[:50]}...")
            
        except Exception as e:
            logger.error(f"Failed to speak response for call {call_id}: {e}")
    
    async def _end_call(self, call_id: str, reason: str):
        """End call session"""
        session = self.active_calls.get(call_id)
        if not session:
            return
        
        session.state = CallState.ENDED
        
        # Calculate call duration
        duration = (datetime.now() - session.start_time).total_seconds()
        
        # Update metrics
        if duration > 0:
            self.successful_calls += 1
            if self.successful_calls == 1:
                self.average_call_duration = duration
            else:
                self.average_call_duration = (
                    (self.average_call_duration * (self.successful_calls - 1) + duration) 
                    / self.successful_calls
                )
        
        # Save call recording and logs
        await self._save_call_data(call_id, session, reason)
        
        # Remove from active calls
        with self.call_lock:
            self.active_calls.pop(call_id, None)
        
        logger.info(f"Ended call {call_id} after {duration:.1f} seconds. Reason: {reason}")
    
    async def _save_call_data(self, call_id: str, session: CallSession, reason: str):
        """Save call data for analysis"""
        try:
            call_data = {
                "call_id": call_id,
                "phone_number": session.phone_number,
                "start_time": session.start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration": (datetime.now() - session.start_time).total_seconds(),
                "reason": reason,
                "conversation_history": session.conversation_history,
                "state": session.state.value
            }
            
            # Save to file
            filename = f"recordings/call_{call_id}_{session.start_time.strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(call_data, f, indent=2)
            
            logger.info(f"Saved call data to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save call data for {call_id}: {e}")
    
    def _create_reject_response(self, call_id: str, reason: str) -> Dict[str, Any]:
        """Create call rejection response"""
        return {
            "callId": call_id,
            "action": "reject",
            "reason": reason
        }
    
    def _create_error_response(self, call_id: str, error: str) -> Dict[str, Any]:
        """Create error response"""
        return {
            "callId": call_id,
            "action": "error",
            "error": error
        }
    
    def get_active_calls(self) -> List[Dict[str, Any]]:
        """Get list of active calls"""
        with self.call_lock:
            return [
                {
                    "call_id": session.call_id,
                    "phone_number": session.phone_number,
                    "state": session.state.value,
                    "duration": (datetime.now() - session.start_time).total_seconds(),
                    "last_activity": session.last_activity.isoformat()
                }
                for session in self.active_calls.values()
            ]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "success_rate": self.successful_calls / max(self.total_calls, 1),
            "average_call_duration": self.average_call_duration,
            "active_calls": len(self.active_calls),
            "max_concurrent_calls": Config.PERFORMANCE["max_concurrent_calls"],
            "llm_metrics": llm_handler.get_metrics()
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        return {
            "status": "healthy",
            "active_calls": len(self.active_calls),
            "llm_healthy": llm_handler.health_check(),
            "speech_processor_initialized": speech_processor.initialized,
            "timestamp": datetime.now().isoformat()
        }

# Global Voice AI engine instance
voice_ai_engine = VoiceAIEngine()
