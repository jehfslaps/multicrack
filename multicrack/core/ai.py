"""Trained sound-recognition model (CED-mini audio tagger, AudioSet classes).

Used alongside the rule-based detection: it decides what a stem is when the file name is unclear
or conflicting, labels FX and vocal events, and confirms a few drum-hit types (clap, tambourine,
shaker, rimshot). If the model can't load, everything falls back to the rules."""
from __future__ import annotations

import os
import sys
import threading

import numpy as np

MODEL_SR = 16000
_lock = threading.Lock()
_tagger = None
_failed = False


def _model_dir() -> str:
    roots = []
    if getattr(sys, "_MEIPASS", None):
        roots.append(sys._MEIPASS)
    here = os.path.dirname(os.path.abspath(__file__))
    roots.append(os.path.normpath(os.path.join(here, "..", "..")))
    for r in roots:
        d = os.path.join(r, "assets", "models", "ced-mini")
        if os.path.isfile(os.path.join(d, "model.int8.onnx")):
            return d
    return ""


def _get():
    global _tagger, _failed
    if _tagger is not None or _failed:
        return _tagger
    with _lock:
        if _tagger is not None or _failed:
            return _tagger
        try:
            import sherpa_onnx
            d = _model_dir()
            if not d:
                raise FileNotFoundError("model files not found")
            cfg = sherpa_onnx.AudioTaggingConfig(
                model=sherpa_onnx.AudioTaggingModelConfig(
                    ced=os.path.join(d, "model.int8.onnx"), num_threads=2, provider="cpu"),
                labels=os.path.join(d, "class_labels_indices.csv"), top_k=15)
            _tagger = sherpa_onnx.AudioTagging(cfg)
        except Exception:
            _failed = True
            _tagger = None
    return _tagger


def available() -> bool:
    return _get() is not None


def resample(x: np.ndarray, sr: int, target: int = MODEL_SR) -> np.ndarray:
    """Band-limited resampling via FFT (fine for short analysis clips)."""
    if sr == target or len(x) == 0:
        return x.astype(np.float32)
    n_out = max(1, int(round(len(x) * target / sr)))
    X = np.fft.rfft(x.astype(np.float64))
    keep = n_out // 2 + 1
    Y = np.zeros(keep, np.complex128)
    m = min(keep, len(X))
    Y[:m] = X[:m]
    y = np.fft.irfft(Y, n_out) * (n_out / len(x))
    return y.astype(np.float32)


def tags(x: np.ndarray, sr: int) -> dict:
    """{AudioSet label: probability} for a mono clip (padded to at least 1 s)."""
    t = _get()
    if t is None or len(x) == 0:
        return {}
    y = resample(x, sr)
    y = y[: MODEL_SR * 10]
    if len(y) < MODEL_SR:
        y = np.concatenate([y, np.zeros(MODEL_SR - len(y), np.float32)])
    pk = float(np.max(np.abs(y)))
    if pk > 1e-6:
        y = y * (0.9 / pk)
    try:
        with _lock:
            s = t.create_stream()
            s.accept_waveform(MODEL_SR, y)
            res = t.compute(s)
        return {e.name: float(e.prob) for e in res}
    except Exception:
        return {}


# ------------------------------------------------------------------ mappings
KIND_TAGS = {
    "Vocals": {"Speech": 1, "Male speech, man speaking": 1, "Female speech, woman speaking": 1,
               "Shout": 1.2, "Yell": 1.2, "Singing": 1.2, "Male singing": 1.2,
               "Female singing": 1.2, "Rapping": 1.2, "Choir": 1, "Vocal music": 1,
               "Humming": 1, "Whispering": 1, "Speech synthesizer": 0.6, "A capella": 1.2,
               "Children shouting": 1, "Battle cry": 1, "Chant": 1, "Synthetic singing": 1},
    "Kick": {"Bass drum": 1.5},
    "Snare": {"Snare drum": 1.5, "Rimshot": 1},
    "Clap": {"Clapping": 1.5, "Hands": 0.6},
    "Hats": {"Hi-hat": 1.5},
    "Cymbals": {"Cymbal": 1.3},
    "Perc / loops": {"Tambourine": 1.2, "Maraca": 1.2, "Cowbell": 1.2, "Wood block": 1.2,
                     "Percussion": 0.8, "Tabla": 1, "Rattle (instrument)": 1, "Gong": 0.8,
                     "Mallet percussion": 0.8, "Shaker": 1},
    "Full drums": {"Drum kit": 1.2, "Drum machine": 1, "Drum": 0.8, "Drum roll": 0.8,
                   "Drum and bass": 0.6, "Drum beat": 1},
    "Guitar": {"Guitar": 1.3, "Electric guitar": 1.3, "Acoustic guitar": 1.3,
               "Plucked string instrument": 0.8, "Steel guitar, slide guitar": 1.2,
               "Distortion": 0.4, "Tapping (guitar technique)": 1},
    "Bass": {"Bass guitar": 1.5, "Double bass": 1.2},
    "Keys": {"Piano": 1.3, "Electric piano": 1.3, "Organ": 1.2, "Electronic organ": 1.2,
             "Hammond organ": 1.2, "Keyboard (musical)": 1, "Harpsichord": 1},
    "Synth": {"Synthesizer": 1.2, "Sampler": 0.8},
    "Strings": {"Bowed string instrument": 1.2, "String section": 1.3,
                "Violin, fiddle": 1.2, "Cello": 1.2, "Orchestra": 0.6},
    "Brass": {"Brass instrument": 1.3, "Trumpet": 1.3, "Trombone": 1.3, "French horn": 1.2,
              "Saxophone": 1.2},
    "FX": {"Whoosh, swoosh, swish": 1.3, "Explosion": 1.2, "Boom": 1.2, "Zing": 1.2,
           "Beep, bleep": 1, "Siren": 1.2, "Civil defense siren": 1.2,
           "Air horn, truck horn": 1.3, "Vehicle horn, car horn, honking": 1.1,
           "Sound effect": 0.9, "Noise": 0.6, "White noise": 0.8, "Pink noise": 0.8,
           "Chirp tone": 0.8, "Thunder": 1, "Bang": 1, "Laser": 1.3, "Sine wave": 0.3},
}

FX_MAP = [  # (AudioSet tags, Xenakis label)
    ({"Air horn, truck horn", "Vehicle horn, car horn, honking", "Foghorn", "Toot"}, "Air Horn"),
    ({"Siren", "Civil defense siren", "Police car (siren)", "Ambulance (siren)",
      "Fire engine, fire truck (siren)", "Fire alarm", "Alarm"}, "Siren"),
    ({"Whoosh, swoosh, swish"}, "Whoosh"),
    ({"Explosion", "Boom", "Bang", "Thunder", "Gunshot, gunfire", "Slam"}, "Impact"),
    ({"Zing", "Beep, bleep", "Chirp tone", "Laser"}, "Laser"),
    ({"White noise", "Pink noise", "Noise", "Static"}, "Noise"),
]
VOICE = {"Speech", "Male speech, man speaking", "Female speech, woman speaking", "Shout", "Yell",
         "Singing", "Male singing", "Female singing", "Rapping", "Choir", "Vocal music",
         "Humming", "Children shouting", "Battle cry", "Chant", "A capella", "Synthetic singing"}


def kind_scores(stem, an) -> dict:
    """Score each stem kind from up to 6 loud 4-second excerpts."""
    if not available():
        return {}
    sr = an.sr
    seg = int(4 * sr)
    H = an.HOP_ENV
    env = an.env
    if len(env) == 0:
        return {}
    # loudest, well-separated excerpt centres
    order = np.argsort(-env[::64])[:200] * 64
    picks = []
    for i in order:
        c = int(i) * H
        if all(abs(c - p) > seg for p in picks):
            picks.append(c)
        if len(picks) >= 6:
            break
    total: dict = {}
    for c in picks:
        a = max(0, c - seg // 4)
        tg = tags(an.m[a:a + seg], sr)
        for k, v in tg.items():
            total[k] = total.get(k, 0.0) + v / len(picks)
    scores = {}
    for kind, weights in KIND_TAGS.items():
        scores[kind] = sum(total.get(t, 0.0) * w for t, w in weights.items())
    return scores


def best_kind(stem, an, candidates=None):
    sc = kind_scores(stem, an)
    if not sc:
        return None
    pool = {k: v for k, v in sc.items() if (not candidates or k in candidates)}
    if not pool:
        return None
    k, v = max(pool.items(), key=lambda kv: kv[1])
    if candidates:
        # the file name lists candidates in priority order; keep the first one unless the model
        # clearly hears something else (at least twice as strong)
        first = candidates[0]
        if pool.get(first, 0) * 2 >= v:
            return first
        return k
    return k if v >= 0.12 else None


def _top(tg: dict, names: set) -> float:
    return max((tg.get(n, 0.0) for n in names), default=0.0)


def fx_label(tg: dict):
    best, bp = None, 0.14
    for names, lab in FX_MAP:
        p = _top(tg, names)
        if p > bp:
            best, bp = lab, p
    if _top(tg, VOICE) > max(bp, 0.25):
        return "Vocal Chop"
    return best


def vocal_label(tg: dict, heuristic: str) -> str:
    voice = _top(tg, VOICE)
    fx = fx_label({k: v for k, v in tg.items() if k not in VOICE})
    if fx and fx != "Vocal Chop" and _top(tg, {n for names, _l in FX_MAP for n in names}) > voice:
        return fx
    if _top(tg, {"Shout", "Yell", "Battle cry", "Children shouting"}) > 0.2:
        return "Vocal Shout"
    if voice < 0.08 and tg.get("Sound effect", 0) > 0.2:
        return "Vocal FX"
    return heuristic


HIT_MAP = [({"Clapping", "Hands"}, "Clap", 0.3), ({"Tambourine"}, "Tambourine", 0.25),
           ({"Maraca", "Shaker", "Rattle (instrument)"}, "Shaker", 0.25),
           ({"Rimshot"}, "Rim", 0.3), ({"Cowbell"}, "Perc", 0.3)]


def hit_label(tg: dict):
    for names, lab, thr in HIT_MAP:
        if _top(tg, names) >= thr:
            return lab
    return None
