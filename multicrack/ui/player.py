"""Audio preview (sounddevice, fails quietly if no audio device is available)."""
import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - library or device missing
    sd = None


class Player:
    def __init__(self):
        self.error = None if sd else "Audio playback isn't available on this computer."
        self.playing_id = None

    def play(self, audio: np.ndarray, sr: int, ident=None) -> bool:
        if sd is None:
            return False
        try:
            sd.stop()
            sd.play(np.ascontiguousarray(audio, dtype=np.float32), sr)
            self.playing_id = ident
            self.error = None
            return True
        except Exception as e:
            self.error = f"Couldn't play audio: {e}"
            return False

    def stop(self):
        self.playing_id = None
        if sd is not None:
            try:
                sd.stop()
            except Exception:
                pass
