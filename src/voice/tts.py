# tts.py
import os
# import soundfile as sf
# import torch
# from nemo.collections.tts.models import FastPitchModel, HifiGanModel


class OrionTTS:
    """
    NeMo-based TTS (FastPitch + HifiGan).
    """

    def __init__(self, socketio=None):
        os.environ["NEMO_LOG_LEVEL"] = "ERROR"
        self.ok = False
        self.socketio = socketio  # [NEW] Real-time events

        print("🔊 Loading NeMo TTS Modules (Lazy Load)...")

        try:
            import torch
            import soundfile as sf
            from nemo.collections.tts.models import FastPitchModel, HifiGanModel

            # Force CPU for TTS to save VRAM for Parakeet ASR (1.1B)
            self.device = "cpu"
            print(f"   → Device: {self.device} (Forced to save VRAM)")
            torch.set_num_threads(4)  # Optimize for CPU execution

            print("   → Loading FastPitch...")
            self.fastpitch = FastPitchModel.from_pretrained(
                "nvidia/tts_en_fastpitch"
            ).to(self.device)

            print("   → Loading HifiGan...")
            self.hifigan = HifiGanModel.from_pretrained(
                "nvidia/tts_hifigan"
            ).to(self.device)

            self.fastpitch.eval()
            self.hifigan.eval()

            self.fastpitch.freeze()
            self.hifigan.freeze()

            self.ok = True
            print("✅ NeMo TTS ready")

            self.torch = torch  # Store reference
            self.sf = sf

            self.torch.set_grad_enabled(False)
            # warmup (only if ok)
            self._warmup()

        except Exception as e:
            print(f"⚠️ NeMo TTS Failed to Load: {e}")
            self.ok = False

    def _warmup(self):
        print("   → Warming up TTS models to reduce first-time latency...")
        try:
            with self.torch.inference_mode():
                # Run a dummy forward pass to initialize PyTorch JIT and memory
                # caches
                tokens = self.fastpitch.parse("System online.")
                spec = self.fastpitch.generate_spectrogram(tokens=tokens)
                _ = self.hifigan.convert_spectrogram_to_audio(spec=spec)
        except Exception as e:
            print(f"⚠️ Warmup failed: {e}")

    # --------------------------------------------------
    def speak(self, text: str, lock_mic=None, unlock_mic=None):
        if not self.ok or not text.strip():
            return

        if lock_mic:
            lock_mic()

        try:
            with self.torch.inference_mode():
                tokens = self.fastpitch.parse(text)
                spec = self.fastpitch.generate_spectrogram(tokens=tokens)
                audio = self.hifigan.convert_spectrogram_to_audio(spec=spec)

            audio_np = audio.squeeze().cpu().numpy()

            # Refine voice to maximum (normalize amplitude)
            import numpy as np
            import sounddevice as sd

            max_amp = np.max(np.abs(audio_np))
            if max_amp > 0:
                audio_np = audio_np / max_amp

            if self.socketio:
                self.socketio.emit(
                    'voice_status', {
                        'source': 'orion', 'state': 'speaking'})

            # PLAY DIRECTLY FROM MEMORY (Zero Disk I/O Latency)
            sd.play(audio_np, samplerate=22050)
            sd.wait()

            if self.socketio:
                self.socketio.emit(
                    'voice_status', {
                        'source': 'orion', 'state': 'idle'})

        finally:
            if unlock_mic:
                unlock_mic()
