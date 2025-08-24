"""
Webhook Server for RingCentral Integration
Handles incoming calls and webhook events from RingCentral
"""

import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import threading
import time

from voice_ai_engine import voice_ai_engine
from config import Config

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

# Create Flask app
app = Flask(__name__)
CORS(app)

# Global variables
active_calls = {}
call_lock = threading.Lock()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        health_data = voice_ai_engine.health_check()
        return jsonify(health_data), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Get system metrics"""
    try:
        metrics = voice_ai_engine.get_metrics()
        return jsonify(metrics), 200
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/calls', methods=['GET'])
def get_active_calls():
    """Get list of active calls"""
    try:
        calls = voice_ai_engine.get_active_calls()
        return jsonify(calls), 200
    except Exception as e:
        logger.error(f"Failed to get active calls: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def ringcentral_webhook():
    """
    Main webhook endpoint for RingCentral events
    
    Handles:
    - Incoming call notifications
    - Call status updates
    - Audio data
    """
    try:
        # Verify webhook signature (if configured)
        if not _verify_webhook_signature(request):
            logger.warning("Invalid webhook signature")
            return jsonify({"error": "Invalid signature"}), 401
        
        # Parse webhook data
        webhook_data = request.get_json()
        if not webhook_data:
            logger.error("No JSON data in webhook request")
            return jsonify({"error": "No data received"}), 400
        
        logger.info(f"Received webhook: {webhook_data.get('eventType', 'unknown')}")
        
        # Handle different event types
        event_type = webhook_data.get('eventType', '')
        
        if event_type == 'IncomingCall':
            return _handle_incoming_call(webhook_data)
        elif event_type == 'CallStatus':
            return _handle_call_status(webhook_data)
        elif event_type == 'AudioData':
            return _handle_audio_data(webhook_data)
        elif event_type == 'CallEnded':
            return _handle_call_ended(webhook_data)
        else:
            logger.info(f"Unhandled event type: {event_type}")
            return jsonify({"status": "received"}), 200
            
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return jsonify({"error": str(e)}), 500

def _verify_webhook_signature(request) -> bool:
    """Verify webhook signature from RingCentral"""
    # In production, implement proper signature verification
    # For now, return True to allow all requests
    return True

def _handle_incoming_call(webhook_data: Dict[str, Any]) -> Response:
    """Handle incoming call notification"""
    try:
        call_data = {
            "callId": webhook_data.get("callId"),
            "from": webhook_data.get("from", {}),
            "to": webhook_data.get("to", {}),
            "direction": webhook_data.get("direction", "inbound"),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Handling incoming call: {call_data['callId']}")
        
        # Process call asynchronously
        def process_call():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(
                    voice_ai_engine.handle_incoming_call(call_data)
                )
                logger.info(f"Call {call_data['callId']} processed: {response.get('action')}")
            except Exception as e:
                logger.error(f"Failed to process call {call_data['callId']}: {e}")
            finally:
                loop.close()
        
        # Start processing in background thread
        thread = threading.Thread(target=process_call)
        thread.daemon = True
        thread.start()
        
        # Return immediate response to RingCentral
        return jsonify({
            "status": "accepted",
            "callId": call_data["callId"],
            "message": "Call processing started"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to handle incoming call: {e}")
        return jsonify({"error": str(e)}), 500

def _handle_call_status(webhook_data: Dict[str, Any]) -> Response:
    """Handle call status updates"""
    try:
        call_id = webhook_data.get("callId")
        status = webhook_data.get("status")
        
        logger.info(f"Call {call_id} status: {status}")
        
        # Update call status in our tracking
        with call_lock:
            if call_id in active_calls:
                active_calls[call_id]["status"] = status
                active_calls[call_id]["last_update"] = datetime.now().isoformat()
        
        return jsonify({"status": "updated"}), 200
        
    except Exception as e:
        logger.error(f"Failed to handle call status: {e}")
        return jsonify({"error": str(e)}), 500

def _handle_audio_data(webhook_data: Dict[str, Any]) -> Response:
    """Handle incoming audio data from call"""
    try:
        call_id = webhook_data.get("callId")
        audio_data = webhook_data.get("audioData")
        
        if not audio_data:
            return jsonify({"error": "No audio data"}), 400
        
        logger.info(f"Received audio data for call {call_id}")
        
        # Store audio data for processing
        with call_lock:
            if call_id in active_calls:
                active_calls[call_id]["audio_buffer"] = audio_data
                active_calls[call_id]["last_audio"] = datetime.now().isoformat()
        
        return jsonify({"status": "received"}), 200
        
    except Exception as e:
        logger.error(f"Failed to handle audio data: {e}")
        return jsonify({"error": str(e)}), 500

def _handle_call_ended(webhook_data: Dict[str, Any]) -> Response:
    """Handle call ended notification"""
    try:
        call_id = webhook_data.get("callId")
        reason = webhook_data.get("reason", "unknown")
        
        logger.info(f"Call {call_id} ended: {reason}")
        
        # Clean up call data
        with call_lock:
            if call_id in active_calls:
                del active_calls[call_id]
        
        return jsonify({"status": "ended"}), 200
        
    except Exception as e:
        logger.error(f"Failed to handle call ended: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/test', methods=['POST'])
def test_call():
    """Test endpoint for simulating calls"""
    try:
        test_data = {
            "callId": f"test_{int(time.time())}",
            "from": {"phoneNumber": "+1234567890"},
            "to": {"phoneNumber": Config.RINGCENTRAL["main_number"]},
            "direction": "inbound"
        }
        
        # Process test call
        def process_test_call():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(
                    voice_ai_engine.handle_incoming_call(test_data)
                )
                logger.info(f"Test call processed: {response}")
            except Exception as e:
                logger.error(f"Test call failed: {e}")
            finally:
                loop.close()
        
        thread = threading.Thread(target=process_test_call)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "test_call_started",
            "callId": test_data["callId"]
        }), 200
        
    except Exception as e:
        logger.error(f"Test call failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration (without sensitive data)"""
    try:
        safe_config = {
            "webhook": {
                "host": Config.WEBHOOK["host"],
                "port": Config.WEBHOOK["port"],
                "debug": Config.WEBHOOK["debug"]
            },
            "performance": Config.PERFORMANCE,
            "speech": {
                "whisper_model": Config.SPEECH["whisper_model"],
                "language": Config.SPEECH["language"]
            },
            "llm": {
                "model": Config.LLM["model"],
                "temperature": Config.LLM["temperature"]
            }
        }
        return jsonify(safe_config), 200
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

def start_server():
    """Start the webhook server"""
    try:
        logger.info(f"Starting webhook server on {Config.WEBHOOK['host']}:{Config.WEBHOOK['port']}")
        
        # Initialize Voice AI engine
        logger.info("Initializing Voice AI engine...")
        
        # Start server
        app.run(
            host=Config.WEBHOOK["host"],
            port=Config.WEBHOOK["port"],
            debug=Config.WEBHOOK["debug"],
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"Failed to start webhook server: {e}")
        raise

if __name__ == '__main__':
    start_server()
