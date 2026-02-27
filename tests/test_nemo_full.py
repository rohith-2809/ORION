import sys
import os

# Append src/ to the path dynamically
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

os.environ['ORION_TEST_MODE'] = '0'
try:
    from core.orchestrator import OrionOrchestrator
    print("Initializing Orion...")
    orion = OrionOrchestrator()
    print('Orion initialized. TTS OK:', getattr(orion.voice_system, 'tts_ok', False))
    print('ASR OK:', getattr(orion.voice_system, 'stt_ok', False))
except Exception as e:
    import traceback
    traceback.print_exc()
