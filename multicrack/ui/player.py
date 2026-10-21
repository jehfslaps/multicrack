"""Audio preview (sounddevice). Tracks the play position so a playhead can be drawn,
and can loop seamlessly. Fails quietly if no audio device is available."""
import time

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - library or device missing
    sd = None


class Player:
    def __init__(self):
        self.error = None if sd else "Audio playback isn't available on this computer."
        self.playing_id = None
        self._t0 = 0.0
        self._n = 0
        self._sr = 44100
        self._loop = False

    def play(self, audio: np.ndarray, sr: int, ident=None, loop=False) -> bool:
        if sd is None:
            return False
        try:
            sd.stop()
            data = np.ascontiguousarray(audio, dtype=np.float32)
            sd.play(data, sr, loop=bool(loop))
            self.playing_id = ident
            self._t0 = time.perf_counter()
            self._n = len(data)
            self._sr = sr
            self._loop = bool(loop)
            self.error = None
            return True
        except Exception as e:
            self.error = f"Couldn't play audio: {e}"
            self.playing_id = None
            return False

    def position(self):
        """Frames into the playing clip, or None when nothing is playing."""
        if self.playing_id is None or self._n == 0:
            return None
        pos = int((time.perf_counter() - self._t0) * self._sr)
        if self._loop:
            return pos % self._n
        if pos >= self._n:
            self.playing_id = None
            return None
        return pos

    @property
    def is_playing(self):
        return self.position() is not None

    def stop(self):
        self.playing_id = None
        if sd is not None:
            try:
                sd.stop()
            except Exception:
                pass
