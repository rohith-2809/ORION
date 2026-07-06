import os
import json
import threading
import time
from voice.tts import OrionTTS

VOSK_AVAILABLE = False
try:
    import vosk
    if os.environ.get("ORION_TEST_MODE") != "1":
        VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False


class OrionVoiceSystem:
    """
    Unified Voice Manager for ORION
    -------------------------------
    HYBRID ARCHITECTURE
    1. Wake Word: Vosk (CPU, Efficient)
    2. STT: NeMo Parakeet (1.1B) (GPU, High Accuracy)
    3. TTS: NeMo FastPitch (GPU/CPU)
    """

    def __init__(self, wake_word="orion", socketio=None):
        print(
            "[ORION VOICE] Initializing Hybrid Voice System (Vosk + NeMo)..."
        )

        self.socketio = socketio  # [NEW] Real-time events
        self.wake_word = wake_word.lower()
        self.rate = 16000
        self.torch = None
        self.nemo_asr = None
        self.audio_mutex = threading.Lock()

        # 0. Wake Word (Vosk)
        self.vosk_model = None
        if VOSK_AVAILABLE:
            model_path = "models/vosk-model-small-en-us-0.15"
            if os.path.exists(model_path):
                try:
                    self.vosk_model = vosk.Model(model_path)
                    print("✅ Vosk Wake Word Model Loaded")
                except Exception as e:
                    print(f"⚠️ Vosk Error: {e}")
            else:
                print(f"⚠️ Vosk model missing at {model_path}")

        # 1. STT (NeMo) - Lazy Load
        self.stt_ok = False
        self.asr = None

        if os.environ.get("ORION_TEST_MODE") == "1":
            print("🚀 ORION_TEST_MODE Active - Skipping NeMo ASR/TTS to save memory for integration tests.")
            self.tts_ok = False
            return

        try:
            print("⏳ Lazy Loading NeMo ASR (This may take a moment)...")
            import torch
            import nemo.collections.asr as nemo_asr
            self.torch = torch
            self.nemo_asr = nemo_asr

            # Force CPU usage with memory optimization (as requested)
            self.device = "cpu"
            # Limit threads for CPU inference to reduce memory and CPU overhead
            os.environ["OMP_NUM_THREADS"] = "4"
            torch.set_num_threads(4)

            # Check if we are online or have cached models
            print(
                f"[ORION VOICE] Loading NeMo Parakeet 1.1B on "
                f"{self.device} (FP16)..."
            )
            self.asr = nemo_asr.models.ASRModel.from_pretrained(
                model_name="nvidia/parakeet-ctc-1.1b",
                map_location=self.device
            ).to(self.device)

            # 🧠 VRAM SAVER: Convert to FP16 if on CUDA
            if self.device == "cuda":
                self.asr = self.asr.half()

            # FIX: Overwrite greedy strategy to 'greedy_batch' to disable
            # repetitive warning output and boost decode speed
            try:
                from nemo.collections.asr.parts.submodules.ctc_decoding import CTCDecodingConfig
                self.asr.change_decoding_strategy(
                    CTCDecodingConfig(strategy="greedy_batch")
                )
            except Exception:
                # Ignore the warning if NeMo version doesn't support easy
                # dynamic swapping
                pass
            self.asr.eval()
            self.asr.freeze()
            if self.device == "cuda":
                torch.cuda.empty_cache()

            self.stt_ok = True
        except Exception as e:
            print(f"⚠️ NeMo STT Failed to Load (Offline?): {e}")
            self.asr = None
            self.stt_ok = False

        # 2. TTS (NeMo)
        try:
            self.tts = OrionTTS(socketio=self.socketio)
            if self.tts.ok:
                self.tts_ok = True
            else:
                self.tts_ok = False
        except Exception as e:
            print(f"⚠️ NeMo TTS Failed: {e}")
            self.tts_ok = False

    def listen_for_wake_word(self, is_active_cb=None):
        """
        Continuous listening loop using 'arecord' piped to Vosk.
        Blocks until wake word is detected, but checks is_active_cb if
        provided.
        """
        if not self.vosk_model:
            print("❌ Vosk Model missing. Cannot listen for wake word.")
            return False

        rec = vosk.KaldiRecognizer(
            self.vosk_model,
            self.rate,
            '["orion", "[unk]"]')

        print(f"🟢 [LISTENING] Vosk Active. Say '{self.wake_word}'...")
        # self._emit_status('user', 'idle') # Listening
        # # Use robust native Python sounddevice to prevent libvosk segment
        # faults
        import sounddevice as sd
        import queue

        # Increase queue size and drop old frames if NeMo blocks the thread too
        # long
        q = queue.Queue(maxsize=100)

        def callback(indata, frames, time, status):
            if status:
                print(status, flush=True)
            try:
                q.put_nowait(bytes(indata))
            except queue.Full:
                pass  # Drop frame gracefully rather than locking ALSA

        stream = None
        while stream is None:
            try:
                self.audio_mutex.acquire()
                stream = sd.RawInputStream(
                    samplerate=self.rate,
                    blocksize=2048,
                    device=None,
                    dtype='int16',
                    channels=1,
                    callback=callback)
            except Exception as e:
                self.audio_mutex.release()
                print(f"⚠️ Audio device contention: {e}. Retrying in 0.5s...")
                time.sleep(0.5)

        try:
            # Drop blocksize to decrease latency buffer lock
            with stream:
                while True:
                    # [BUG FIX] Check if we should still be listening
                    if is_active_cb and not is_active_cb():
                        return False

                    try:
                        # Use timeout so we can periodically check is_active_cb
                        data = q.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    # Yield slightly so we don't monopolize the GIL
                    time.sleep(0.005)

                    if rec.AcceptWaveform(data):
                        res = json.loads(rec.Result())
                        text = res.get("text", "")
                        if self.wake_word in text.lower():
                            print(f"⚡ WAKE DETECTED: '{text}'")
                            self._emit_status('user', 'speaking')
                            return True
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"Error in listen loop: {e}")
        finally:
            if self.audio_mutex.locked():
                self.audio_mutex.release()

    def _emit_status(self, source, state):
        if self.socketio:
            self.socketio.emit(
                'voice_status', {
                    'source': source, 'state': state})

    def listen_for_command(self, is_active_cb=None):
        """
        Listens for wake word, then records a command, then transcribes it.
        Returns the transcribed text.
        """
        if self.listen_for_wake_word(is_active_cb):
            audio = self.record_command()
            text = self.transcribe(audio)
            return text
        return ""

    def record_command(
            self,
            max_seconds=10,
            silence_threshold=0.015,
            silent_chunks=10):
        """Records command natively until silence is detected or max_seconds
        is reached"""
        print("🔴 [RECORDING COMMAND]...")
        self._emit_status('user', 'speaking')

        import sounddevice as sd
        import numpy as np
        import queue

        q = queue.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                print(status, flush=True)
            q.put(indata.copy())

        recording = []
        silence_count = 0
        chunk_size = 1600  # 0.1 seconds at 16000Hz

        time.sleep(0.1)  # Allow system audio lock to release before recording
        with self.audio_mutex:
            try:
                stream = sd.InputStream(
                    samplerate=self.rate,
                    channels=1,
                    dtype='float32',
                    blocksize=chunk_size,
                    callback=callback)
                with stream:
                    for _ in range(
                            int((max_seconds * self.rate) / chunk_size)):
                        try:
                            chunk = q.get(timeout=2.0)
                        except queue.Empty:
                            break

                        recording.append(chunk)

                        rms = np.sqrt(np.mean(chunk**2))
                        if rms < silence_threshold:
                            silence_count += 1
                        else:
                            silence_count = 0

                        if silence_count > silent_chunks:  # ~1 second of silence
                            break
            except Exception as e:
                print(f"⚠️ Recording Error: {e}")

        time.sleep(0.1)  # Gap after recording before TTS logs

        print("⏹️ [RECORDING COMPLETE]")
        self._emit_status('user', 'idle')

        if not recording:
            return np.zeros((1, 1), dtype='float32').flatten()
        return np.concatenate(recording).flatten()

    def transcribe(self, audio_signal):
        """Transcribes float32 audio signal"""
        if not self.stt_ok or not self.asr:
            print(
                "⚠️ NeMo STT not available. "
                "Falling back to empty transcription."
            )
            return ""

        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        sf.write(temp_path, audio_signal, self.rate)

        try:
            # 🧠 VRAM SAVER: Inference mode prevents gradient history allocation
            with self.torch.inference_mode():
                # Some NeMo versions use autocast automatically, but we can
                # enforce it
                with self.torch.amp.autocast(
                        'cuda', enabled=(self.device == "cuda")):
                    transcriptions = self.asr.transcribe([temp_path])

            # [VRAM CLEANUP]
            if self.torch and self.device == "cuda":
                self.torch.cuda.empty_cache()

            if transcriptions:
                result = transcriptions[0]
                # If NeMo returns a Hypothesis object, extract text attribute
                if hasattr(result, 'text'):
                    return result.text
                return str(result)
            return ""
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def speak(self, text):
        if self.tts_ok:
            self.tts.speak(text)
        else:
            print(f"[SILENT TTS]: {text}")
