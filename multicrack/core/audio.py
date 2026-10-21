"""Reading stems, joining split L/R files, rendering chops and writing clean WAVs."""
from __future__ import annotations

import os
import struct
import sys

import numpy as np
import soundfile as sf

from .model import Chop, Stem
from .naming import channel_side, clean_stem_name

AUDIO_EXTS = {".wav", ".wave", ".aif", ".aiff", ".aifc", ".flac", ".mp3", ".ogg", ".oga",
              ".opus", ".caf", ".w64", ".rf64", ".au", ".snd"}

PEAK_DB = -0.1


def is_audio(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in AUDIO_EXTS


def expand_paths(paths) -> list[str]:
    """Files and folders (recursively) -> sorted list of audio files."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in files:
                    if is_audio(f) and not f.startswith("._"):
                        out.append(os.path.join(root, f))
        elif os.path.isfile(p) and is_audio(p):
            out.append(p)
    seen, uniq = set(), []
    for p in sorted(out, key=lambda s: os.path.basename(s).lower()):
        k = os.path.normcase(os.path.abspath(p))
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


def read_audio(path: str):
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    if data.shape[1] > 2:          # keep the front pair of multichannel files
        data = data[:, :2]
    data = np.nan_to_num(data, copy=False)
    return np.ascontiguousarray(data), int(sr)


def load_stems(paths, progress=None) -> list[Stem]:
    """Load files; split-mono L/R pairs with equal length and rate become one stereo stem."""
    files = expand_paths(paths)
    sides = {}
    for p in files:
        cs = channel_side(p)
        if cs:
            sides.setdefault((os.path.dirname(p).lower(), cs[0]), {})[cs[1]] = p
    pairs = {}
    for key, d in sides.items():
        if "L" in d and "R" in d:
            pairs[d["L"]] = d["R"]
    skip = set(pairs.values())

    stems = []
    for i, p in enumerate(files):
        if p in skip:
            continue
        if progress:
            progress(f"Loading {os.path.basename(p)}", i, len(files))
        try:
            audio, sr = read_audio(p)
        except Exception as e:  # unreadable file
            stems.append(_error_stem(p, str(e)))
            continue
        sources = [p]
        name = os.path.basename(p)
        if p in pairs:
            try:
                r_audio, r_sr = read_audio(pairs[p])
                if (r_sr == sr and r_audio.shape[0] == audio.shape[0]
                        and audio.shape[1] == 1 and r_audio.shape[1] == 1):
                    audio = np.ascontiguousarray(np.hstack([audio, r_audio]))
                    sources.append(pairs[p])
                    name = f"{name} + {os.path.basename(pairs[p])}"
                else:
                    pairs.pop(p)
            except Exception:
                pairs.pop(p)
        stems.append(Stem(path=p, name=name, clean_name=clean_stem_name(p), audio=audio,
                          sr=sr, sources=sources))
    # a lone half of a pair that failed to join is loaded on its own
    loaded = {s for st in stems for s in st.sources}
    for p in files:
        if p not in loaded and p in skip:
            try:
                audio, sr = read_audio(p)
                stems.append(Stem(path=p, name=os.path.basename(p), clean_name=clean_stem_name(p),
                                  audio=audio, sr=sr, sources=[p]))
            except Exception as e:
                stems.append(_error_stem(p, str(e)))
    return stems


def _error_stem(path, msg):
    s = Stem(path=path, name=os.path.basename(path), clean_name=clean_stem_name(path),
             audio=np.zeros((1, 1), np.float32), sr=44100, sources=[path])
    s.status = "Can't read this file"
    s.mode = "skip"
    s.analysis["error"] = msg
    return s


# ------------------------------------------------------------------ rendering
def _fade(n, length):
    length = max(1, min(length, n))
    return (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, length))).astype(np.float32)


def default_fades_ms(chop: Chop, sr: int = 44100):
    """Automatic de-click fade lengths in milliseconds for a chop."""
    if chop.kind == "loop":
        return (0.0, 0.0) if chop.seam else (0.4, 2.0)
    if chop.kind in ("hit", "roll"):
        return 0.6, (3.0 if chop.cut_at_next else 8.0)
    return 2.0, 12.0


def seam_length(chop: Chop, sr: int) -> int:
    return int(min(0.012 * sr, max(0, chop.end - chop.start) // 8))


def render_chop(stem: Stem, chop: Chop) -> np.ndarray:
    """Slice, (reverse), de-click / fade, smooth loop seams, peak-normalize and apply gain.
    Returns float32 (frames, channels). Preview and export use exactly this."""
    s = max(0, int(chop.start))
    e = min(stem.frames, int(chop.end))
    x = stem.audio[s:e].astype(np.float32, copy=True)
    n = x.shape[0]
    if n == 0:
        return x
    sr = stem.sr
    # loop seam: blend the end into the audio just before the loop start, so the wrap-around
    # from the last sample back to the first is continuous (length stays exactly on the bars)
    if chop.kind == "loop" and chop.seam and not chop.reverse:
        k = seam_length(chop, sr)
        if k > 8 and s - k >= 0:
            pre = stem.audio[s - k:s].astype(np.float32)
            ramp = np.linspace(0, np.pi / 2, k, dtype=np.float32)
            x[-k:] = x[-k:] * np.cos(ramp)[:, None] + pre * np.sin(ramp)[:, None]
    if chop.reverse:
        x = np.ascontiguousarray(x[::-1])
    din, dout = default_fades_ms(chop, sr)
    fin_ms = din if chop.fade_in_ms is None else float(chop.fade_in_ms)
    fout_ms = dout if chop.fade_out_ms is None else float(chop.fade_out_ms)
    fin = int(fin_ms / 1000.0 * sr)
    fout = int(fout_ms / 1000.0 * sr)
    if chop.fade_in_ms is None:
        fin = min(fin, n // 4)
    if chop.fade_out_ms is None:
        fout = min(fout, n // 3)
    fin, fout = min(fin, n), min(fout, n)
    if fin > 1:
        x[:fin] *= _fade(n, fin)[:, None]
    if fout > 1:
        x[-fout:] *= _fade(n, fout)[::-1][:, None]
    peak = float(np.max(np.abs(x)))
    if peak > 1e-9:
        gain = min(0.0, float(chop.gain_db or 0.0))
        x *= (10 ** ((PEAK_DB + gain) / 20.0)) / peak
    return x


def write_wav24(path: str, x: np.ndarray, sr: int) -> None:
    """Plain 24-bit PCM WAV: only the 'fmt ' and 'data' chunks, no tempo or other tags."""
    if x.ndim == 1:
        x = x[:, None]
    ch = x.shape[1]
    q = np.clip(np.round(x.astype(np.float64) * 8388607.0), -8388608, 8388607).astype("<i4")
    raw = q.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    block = 3 * ch
    fmt = struct.pack("<HHIIHH", 1, ch, sr, sr * block, block, 24)
    pad = b"\x00" if len(raw) % 2 else b""
    riff_size = 4 + (8 + len(fmt)) + (8 + len(raw) + len(pad))
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", riff_size) + b"WAVE")
        f.write(b"fmt " + struct.pack("<I", len(fmt)) + fmt)
        f.write(b"data" + struct.pack("<I", len(raw)) + raw + pad)


def desktop_dir() -> str:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            # FOLDERID_Desktop {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}
            fid = GUID(0xB4BFCC3A, 0xDB2C, 0x424C,
                       (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41))
            p = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None,
                                                         ctypes.byref(p)) == 0:
                path = p.value
                ctypes.windll.ole32.CoTaskMemFree(p)
                if path and os.path.isdir(path):
                    return path
        except Exception:
            pass
    d = os.path.join(os.path.expanduser("~"), "Desktop")
    return d if os.path.isdir(d) else os.path.expanduser("~")
