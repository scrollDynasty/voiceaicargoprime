"""
LLM Handler Module
Handles interactions with Llama 3.1 70B through Ollama API
"""

import logging
import requests
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime
import time

from config import Config

logger = logging.getLogger(__name__)

class LLMHandler:
    """Handles LLM interactions through Ollama API"""
    
    def __init__(self):
        """Initialize LLM handler"""
        self.ollama_url = Config.LLM["ollama_url"]
        self.model = Config.LLM["model"]
        self.system_prompt = Config.LLM["system_prompt"]
        self.temperature = Config.LLM["temperature"]
        self.max_tokens = Config.LLM["max_tokens"]
        self.top_p = Config.LLM["top_p"]
        
        # Conversation history for context
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 10  # Keep last 10 exchanges
        
        # Performance metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.average_response_time = 0.0
        
    async def generate_response(self, user_input: str, context: str = "") -> str:
        """
        Generate response using Llama 3.1 70B
        
        Args:
            user_input: User's input text
            context: Additional context (optional)
            
        Returns:
            Generated response
        """
        start_time = time.time()
        
        try:
            # Build conversation context
            messages = self._build_messages(user_input, context)
            
            # Prepare request payload
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "num_predict": self.max_tokens
                }
            }
            
            # Make request to Ollama
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        generated_text = result.get("message", {}).get("content", "")
                        
                        # Update conversation history
                        self._update_history(user_input, generated_text)
                        
                        # Update metrics
                        self._update_metrics(time.time() - start_time, True)
                        
                        logger.info(f"LLM Response: {generated_text[:100]}...")
                        return generated_text.strip()
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama API error: {response.status} - {error_text}")
                        self._update_metrics(time.time() - start_time, False)
                        return self._get_fallback_response()
                        
        except asyncio.TimeoutError:
            logger.error("LLM request timed out")
            self._update_metrics(time.time() - start_time, False)
            return self._get_fallback_response()
            
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            self._update_metrics(time.time() - start_time, False)
            return self._get_fallback_response()
    
    def _build_messages(self, user_input: str, context: str = "") -> List[Dict[str, str]]:
        """
        Build messages array for Ollama API
        
        Args:
            user_input: Current user input
            context: Additional context
            
        Returns:
            List of message dictionaries
        """
        messages = []
        
        # Add system prompt
        messages.append({
            "role": "system",
            "content": self.system_prompt
        })
        
        # Add context if provided
        if context:
            messages.append({
                "role": "system",
                "content": f"Additional context: {context}"
            })
        
        # Add conversation history
        for exchange in self.conversation_history[-self.max_history:]:
            messages.append({
                "role": "user",
                "content": exchange["user"]
            })
            messages.append({
                "role": "assistant",
                "content": exchange["assistant"]
            })
        
        # Add current user input
        messages.append({
            "role": "user",
            "content": user_input
        })
        
        return messages
    
    def _update_history(self, user_input: str, assistant_response: str):
        """Update conversation history"""
        self.conversation_history.append({
            "user": user_input,
            "assistant": assistant_response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only recent history
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
    
    def _update_metrics(self, response_time: float, success: bool):
        """Update performance metrics"""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        
        # Update average response time
        if self.total_requests == 1:
            self.average_response_time = response_time
        else:
            self.average_response_time = (
                (self.average_response_time * (self.total_requests - 1) + response_time) 
                / self.total_requests
            )
    
    def _get_fallback_response(self) -> str:
        """Get fallback response when LLM fails"""
        fallback_responses = [
            "I apologize, but I'm having trouble processing your request right now. Please call our main dispatch line for immediate assistance.",
            "I'm experiencing technical difficulties. Please contact our dispatch team directly for help with your delivery.",
            "I'm unable to assist at the moment. Please call our main office for support with your logistics needs.",
            "I'm sorry, but I need to transfer you to a human dispatcher. Please call our main line for assistance."
        ]
        
        import random
        return random.choice(fallback_responses)
    
    def get_logistics_response(self, query: str, order_info: Dict[str, Any] = None) -> str:
        """
        Generate logistics-specific response
        
        Args:
            query: User query
            order_info: Order information dictionary
            
        Returns:
            Logistics-specific response
        """
        # Add logistics context
        context = ""
        if order_info:
            context = f"Order #{order_info.get('order_id', 'N/A')} - "
            context += f"Status: {order_info.get('status', 'Unknown')} - "
            context += f"Destination: {order_info.get('destination', 'Unknown')}"
        
        # Use async method
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new task
            task = asyncio.create_task(self.generate_response(query, context))
            return task.result()
        else:
            # Run in new event loop
            return asyncio.run(self.generate_response(query, context))
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info("Conversation history cleared")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "success_rate": self.successful_requests / max(self.total_requests, 1),
            "average_response_time": self.average_response_time,
            "conversation_history_length": len(self.conversation_history)
        }
    
    def health_check(self) -> bool:
        """
        Check if Ollama service is healthy
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

# Global LLM handler instance
llm_handler = LLMHandler()

# Convenience functions
async def generate_ai_response(user_input: str, context: str = "") -> str:
    """Async wrapper for generating AI response"""
    return await llm_handler.generate_response(user_input, context)

def get_logistics_help(query: str, order_info: Dict[str, Any] = None) -> str:
    """Get logistics-specific help"""
    return llm_handler.get_logistics_response(query, order_info)
