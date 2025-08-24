#!/usr/bin/env python3
"""
Voice Quality Test Script
Тестирует разные TTS модели для выбора лучшего голоса
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from TTS.api import TTS

def test_tts_model(model_name, speaker=None, test_text="Hello, this is a test of the voice quality for Prime Cargo Logistics."):
    """Test a TTS model and save audio file"""
    try:
        print(f"\n🔊 Testing model: {model_name}")
        
        # Initialize TTS model
        tts = TTS(model_name=model_name, progress_bar=False)
        
        # Get available speakers if model supports multiple speakers
        if hasattr(tts, 'speakers') and tts.speakers:
            print(f"Available speakers: {tts.speakers[:5]}...")  # Show first 5
            if speaker and speaker in tts.speakers:
                test_speaker = speaker
            else:
                test_speaker = tts.speakers[0]
        else:
            test_speaker = None
        
        # Create output filename
        model_short = model_name.split('/')[-1]
        output_file = f"test_voice_{model_short}.wav"
        
        # Generate speech
        if test_speaker:
            print(f"Using speaker: {test_speaker}")
            tts.tts_to_file(
                text=test_text,
                file_path=output_file,
                speaker=test_speaker,
                speed=0.9
            )
        else:
            tts.tts_to_file(
                text=test_text,
                file_path=output_file,
                speed=0.9
            )
        
        print(f"✅ Audio saved: {output_file}")
        
        # Try to play the audio (if possible)
        try:
            if sys.platform.startswith('linux'):
                subprocess.run(['aplay', output_file], check=False)
            elif sys.platform == 'darwin':
                subprocess.run(['afplay', output_file], check=False)
            elif sys.platform == 'win32':
                subprocess.run(['start', output_file], shell=True, check=False)
        except:
            print("Could not play audio automatically. Please play the file manually.")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Error with model {model_name}: {e}")
        return None

def main():
    """Main function to test all TTS models"""
    print("🎤 Voice Quality Test for Prime Cargo Logistics")
    print("=" * 50)
    
    # Test text for logistics
    test_text = """
    Welcome to Prime Cargo Logistics. I'm your AI assistant. 
    How can I help you with your delivery today? 
    I can provide information about routes, order status, and delivery addresses.
    """
    
    # Test different models
    models_to_test = [
        "tts_models/en/vctk/vits",
        "tts_models/en/ljspeech/fast_pitch", 
        "tts_models/en/ljspeech/glow-tts",
        "tts_models/en/ljspeech/tacotron2-DDC"
    ]
    
    results = []
    
    for model in models_to_test:
        result = test_tts_model(model, test_text=test_text)
        if result:
            results.append((model, result))
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print("=" * 50)
    
    for i, (model, file) in enumerate(results, 1):
        print(f"{i}. {model}")
        print(f"   File: {file}")
        print()
    
    print("🎯 Recommendations:")
    print("- VCTK/VITS: Best overall quality, multiple voices")
    print("- FastPitch: Good balance of speed and quality")
    print("- Glow-TTS: Natural sounding, good for long texts")
    print("- Tacotron2: Classic model, reliable but slower")
    
    print(f"\n📁 All test files saved in: {os.getcwd()}")
    print("Listen to each file and choose the best voice for your system!")

if __name__ == "__main__":
    main()
