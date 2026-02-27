import os
import sys
import subprocess
import json
import numpy as np

try:
    from vosk import Model, KaldiRecognizer
except ImportError:
    print("❌ Vosk not installed. Run: pip install vosk")
    sys.exit(1)


def verify_wake_word():
    print("--- ORION WAKE WORD CHECK (Vosk) ---")
    model_path = "models/vosk-model-small-en-us-0.15"

    if not os.path.exists(model_path):
        print(f"❌ Model not found at {model_path}")
        print("   Please check 'models/' directory.")
        return

    print(f"📦 Loading Vosk Model from {model_path}...")
    try:
        model = Model(model_path)
        # Constrain grammar to just the wake word for higher accuracy
        rec = KaldiRecognizer(model, 16000, '["orion", "[unk]"]')
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return

    print("✅ Model Loaded.")
    print("🟢 [LISTENING] Say 'Orion' to verify detection...")
    print("   (Press Ctrl+C to exit)\n")

    # Start arecord process
    cmd = [
        "arecord",
        "-D", "pulse",
        "-f", "S16_LE",
        "-r", "16000",
        "-c", "1",
        "-t", "raw",
        "--quiet"
    ]

    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=4096)

        while True:
            data = process.stdout.read(4096)
            if not data:
                break

            # Calculate RMS amplitude for visual feedback
            audio_chunk = np.frombuffer(
                data, dtype=np.int16).astype(
                np.float32)
            rms = np.sqrt(np.mean(audio_chunk**2))

            # Simple bar graph: 500 is roughly noise floor, 2000+ is speech
            if np.isnan(rms):
                rms = 0
            bars = "I" * int(rms / 300)
            if len(bars) > 0:
                print(f"[Audio Level]: {bars}", end="\r")

            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                text = res.get("text", "")
                if text:
                    print(f"\n🗣️  Recognized: '{text}'")
                    if "orion" in text.lower():
                        print(f"⚡ WAKE DETECTED: '{text}'")
            else:
                partial = json.loads(rec.PartialResult())
                part_text = partial.get("partial", "")
                if part_text:
                    print(f"   (Partial: {part_text})", end="\r")

    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    except FileNotFoundError:
        print("❌ 'arecord' not found.")
    finally:
        if process:
            process.terminate()


if __name__ == "__main__":
    verify_wake_word()
