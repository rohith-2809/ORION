# wake_listener.py

import json
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer


class OrionWakeListener:
    """
    Unified wake + command listener (single audio stream).
    """

    def __init__(
        self,
        model_path,
        wake_word="orion",
        rate=16000,
    ):
        self.model = Model(model_path)
        self.rate = rate
        self.wake_word = wake_word.lower()
        self.q = queue.Queue()
        self.recognizer = KaldiRecognizer(self.model, self.rate)

    def _callback(self, indata, frames, time, status):
        if status:
            print(status)
        self.q.put(bytes(indata))

    def listen(self) -> str:
        print("🟢 ORION listening (say 'orion' then command)")

        self.recognizer.Reset()

        with sd.RawInputStream(
            samplerate=self.rate,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=self._callback,
        ):
            awakened = False

            while True:
                data = self.q.get()
                if self.recognizer.AcceptWaveform(data):
                    text = json.loads(
                        self.recognizer.Result()).get(
                        "text", "").lower().strip()

                    if not text:
                        continue

                    print("📝 Heard:", text)

                    if not awakened:
                        if self.wake_word in text:
                            print("🔔 Wake word detected")
                            awakened = True
                            self.recognizer.Reset()
                    else:
                        # This is the actual command
                        return text
