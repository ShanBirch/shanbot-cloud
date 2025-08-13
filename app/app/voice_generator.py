import os
import torch
from tortoise.api import TextToSpeech
from tortoise.utils.audio import load_audio, load_voice, load_voices
import torchaudio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_generator")

class VoiceGenerator:
    def __init__(self):
        """Initialize the voice generator with Tortoise TTS."""
        self.tts = TextToSpeech()
        self.voice_samples = {}
        self.current_preset = 'standard'
        
        # Quality preset settings
        self.presets = {
            'ultra_fast': {
                'num_autoregressive_samples': 1,
                'diffusion_iterations': 30,
                'temperature': 0.8,
            },
            'fast': {
                'num_autoregressive_samples': 2,
                'diffusion_iterations': 50,
                'temperature': 0.8,
            },
            'standard': {
                'num_autoregressive_samples': 4,
                'diffusion_iterations': 100,
                'temperature': 0.8,
            }
        }

    def add_voice_sample(self, voice_name: str, sample_path: str) -> bool:
        """
        Add a voice sample for cloning.
        
        Args:
            voice_name: Name to identify this voice
            sample_path: Path to the WAV file containing the voice sample
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not os.path.exists(sample_path):
                print(f"Sample file not found: {sample_path}")
                return False
                
            # Load and process the voice sample
            audio = load_audio(sample_path, 22050)
            self.voice_samples[voice_name] = audio
            return True
            
        except Exception as e:
            print(f"Error adding voice sample: {e}")
            return False

    def set_preset(self, preset_name: str):
        """Set the quality preset for voice generation."""
        if preset_name in self.presets:
            self.current_preset = preset_name
        else:
            print(f"Invalid preset '{preset_name}'. Using 'standard' instead.")
            self.current_preset = 'standard'

    def generate_speech(self, text: str, voice_name: str, output_file: str) -> str:
        """
        Generate speech using the cloned voice.
        
        Args:
            text: Text to convert to speech
            voice_name: Name of the voice to use
            output_file: Path to save the generated audio
            
        Returns:
            str: Path to the generated audio file
        """
        if voice_name not in self.voice_samples:
            raise ValueError(f"Voice '{voice_name}' not found. Add it first with add_voice_sample()")
            
        preset = self.presets[self.current_preset]
        
        # Generate speech with Tortoise
        gen_audio = self.tts.tts_with_preset(
            text,
            voice_samples=self.voice_samples[voice_name],
            preset=preset
        )
        
        # Save the generated audio
        output_path = os.path.abspath(output_file)
        torchaudio.save(output_path, gen_audio.squeeze(0).unsqueeze(0), 24000)
        
        return output_path

    def list_available_voices(self) -> list:
        """List all available voice samples."""
        try:
            voices = list(self.voice_samples.keys())
            return voices
        except Exception as e:
            logger.error(f"Error listing voices: {e}")
            return []

    def set_preset(self, preset: str) -> bool:
        """
        Set the generation preset.
        
        Args:
            preset: One of 'ultra_fast', 'fast', 'standard', 'high_quality'
        """
        valid_presets = ['ultra_fast', 'fast', 'standard', 'high_quality']
        if preset not in valid_presets:
            logger.error(f"Invalid preset. Must be one of {valid_presets}")
            return False
            
        self.current_preset = preset
        logger.info(f"Preset set to: {preset}")
        return True 