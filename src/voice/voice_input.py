# voice_input_nemo.py
import subprocess
import tempfile
import os
import wave
import math
import numpy as np
import torch
import nemo.collections.asr as nemo_asr
import re


class OrionVoiceInput:
    """
    ORION Voice Input – NeMo STT
    ---------------------------
    - Energy gate
    - Single-shot transcription
    - GPU accelerated
    """

    def __init__(
        self,
        rate: int = 16000,
        listen_seconds: int = 4,
        device: str | None = None,
    ):
        self.rate = rate
        self.listen_seconds = listen_seconds
        self.device = device or (
            "cuda" if torch.cuda.is_available() else "cpu")

        print("🎤 Loading NeMo STT (Parakeet)...")

        self.asr = nemo_asr.models.ASRModel.from_pretrained(
            model_name="nvidia/parakeet-ctc-1.1b"
        ).to(self.device)

        self.asr.eval()
        self.asr.freeze()

        print("✅ NeMo STT ready on", self.device)

    # --------------------------------------------------
    def _is_orion(self, word):
        # Phonetic & Typto Robustness
        triggers = {
            "orion", "orian", "orien", "orient", "aurion",
            "ryan", "arion", "hail", "hey", "onion", "Obrien"
        }
        # Check strict list or regex
        clean = re.sub(r"[^a-z]", "", word.lower())
        return clean in triggers or bool(re.fullmatch(r"ori[a-z]{0,4}", clean))

    def _extract_intent(self, text):
        words = text.split()
        if not words:
            return None, None

    # --------------------------------------------------
    def _record_audio(self, wav_path: str):
        subprocess.run(
            [
                "arecord",
                "-D", "pulse",
                "-f", "S16_LE",
                "-r", str(self.rate),
                "-c", "1",
                "-d", str(self.listen_seconds),
                "--quiet",
                wav_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # --------------------------------------------------
    def _rms_energy(self, wav_path: str) -> float:
        try:
            with wave.open(wav_path, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                if not frames:
                    return 0.0
                samples = np.frombuffer(frames, dtype=np.int16)
                return math.sqrt(np.mean(samples.astype(np.float32) ** 2))
        except Exception:
            return 0.0

    # --------------------------------------------------
    def listen_for_command(self) -> str | None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name

        self._record_audio(wav_path)

        energy = self._rms_energy(wav_path)
        print(f"🔈 RMS ENERGY: {energy:.1f}")

        if energy < 300:
            os.remove(wav_path)
            return None

        try:
            hypothesis = self.asr.transcribe([wav_path])[0]
        except Exception as e:
            print("❌ NeMo STT error:", e)
            os.remove(wav_path)
            return None

        os.remove(wav_path)

        text = (hypothesis.text or "").strip()
        if not text:
            return None

        print("📝 STT:", text)

        # Optional: Check for wake word if this was a wake-up listen
        # For now, we return raw text and let the caller handle logic

        return text

    # --------------------------------------------------
    def is_wake_word(self, text):
        """
        Robust check for 'Orion' including common mishearings.
        """
        triggers = {
            "orion", "orian", "orien", "orient", "aurion",
            "ryan", "arion", "hail", "hey", "onion", "Obrien"
        }
        words = re.sub(r"[^a-z\s]", "", text.lower()).split()
        for word in words:
            if word in triggers or re.fullmatch(r"ori[a-z]{0,4}", word):
                return True
        return False
