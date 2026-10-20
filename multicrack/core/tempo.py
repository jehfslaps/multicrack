"""Tempo and bar-grid detection."""
from __future__ import annotations

import numpy as np

from .dsp import Analysis, EPS


def _autocorr(x):
    x = x - x.mean()
    n = len(x)
    f = np.fft.rfft(x, 2 * n)
    ac = np.fft.irfft(np.abs(f) ** 2)[:n]
    return ac / (ac[0] + EPS)


def _fold_sharpness(pos, w, period, bins=96):
    ph = np.mod(pos, period) / period
    h = np.bincount((ph * bins).astype(int) % bins, weights=w, minlength=bins)
    h = (h + np.roll(h, 1) + np.roll(h, -1)) / 3.0
    return float(h.max() / (h.mean() + EPS)), h


def estimate(an: Analysis):
    """Return dict(bpm, confidence, downbeat) or None when there is no steady pulse."""
    o = an.flux + an.flux_low
    fps = an.fps
    if len(o) < fps * 4 or o.max() <= 0:
        return None
    ac = _autocorr(o)
    bpms = np.arange(60.0, 200.0, 0.25)

    def score(b):
        lag = 60.0 * fps / b
        s = 0.0
        for mult, wt in ((1, 1.0), (2, 0.5), (4, 0.25)):
            L = lag * mult
            i = int(L)
            if i + 1 >= len(ac):
                continue
            fr = L - i
            s += wt * (ac[i] * (1 - fr) + ac[i + 1] * fr)
        return s

    sc = np.array([score(b) for b in bpms])
    prior = np.exp(-0.5 * (np.log2(bpms / 120.0) / 0.7) ** 2)
    best = float(bpms[int(np.argmax(sc * prior))])
    s_best = score(best)
    if best < 88 and score(best * 2) > 0.55 * s_best:
        best *= 2
    elif best > 170 and score(best / 2) > 0.55 * s_best:
        best /= 2

    # fine search by folding onset strength over the whole file
    pos = np.arange(len(o)) * float(an.HOP_ONSET)
    w = o.astype(np.float64)
    keep = w > np.percentile(w, 80)
    pos, w = pos[keep], w[keep]
    cands = np.arange(best - 1.5, best + 1.5, 0.01)
    sharp = np.array([_fold_sharpness(pos, w, 60.0 * an.sr / b)[0] for b in cands])
    bpm = float(cands[int(np.argmax(sharp))])
    top = sharp.max()
    r = round(bpm)
    if abs(bpm - r) < 0.08 and _fold_sharpness(pos, w, 60.0 * an.sr / r)[0] >= 0.95 * top:
        bpm = float(r)
    period = 60.0 * an.sr / bpm
    conf, hist = _fold_sharpness(pos, w, period)
    beat_phase = (np.argmax(hist) + 0.5) / len(hist) * period

    downbeat = _downbeat(an, bpm, beat_phase)
    return dict(bpm=round(bpm, 2), confidence=conf, downbeat=int(downbeat))


def _downbeat(an: Analysis, bpm: float, beat_phase: float) -> float:
    period = 60.0 * an.sr / bpm
    H = an.HOP_ONSET
    low, full = an.flux_low, an.flux
    mid = np.maximum(full - low, 0)
    nb = int((an.n - beat_phase) // period)
    if nb < 8:
        return beat_phase
    beats = beat_phase + np.arange(nb) * period
    idx = np.clip((beats / H).round().astype(int), 0, len(low) - 1)

    def around(arr):
        out = np.zeros(len(idx))
        for d in (-1, 0, 1):
            out = np.maximum(out, arr[np.clip(idx + d, 0, len(arr) - 1)])
        return out

    lb, mb = around(low), around(mid)
    lb = lb / (lb.mean() + EPS)
    mb = mb / (mb.mean() + EPS)
    scores = []
    first_on = None
    strong = np.where(full > np.percentile(full, 97))[0]
    if len(strong):
        first_on = strong[0] * H
    for b in range(4):
        sel = np.arange(b, nb, 4)
        back = np.arange((b + 1) % 4, nb, 4)
        back2 = np.arange((b + 3) % 4, nb, 4)
        s = lb[sel].mean() + 0.5 * (mb[back].mean() + mb[back2].mean()) / 2 - 0.25 * mb[sel].mean()
        if first_on is not None:
            d0 = beat_phase + b * period
            dist = (first_on - d0) % (4 * period)
            dist = min(dist, 4 * period - dist)
            if dist < 0.06 * an.sr:
                s += 0.35
        scores.append(s)
    b = int(np.argmax(scores))
    d = beat_phase + b * period
    bar = 4 * period
    d = d % bar
    return d


def fits(bpm_a: float, bpm_b: float) -> bool:
    """True when two tempo readings agree (allowing half / double / 3:2 readings)."""
    if not bpm_a or not bpm_b:
        return True
    for ratio in (1.0, 2.0, 0.5, 1.5, 2 / 3.0):
        if abs(bpm_a * ratio - bpm_b) / bpm_b < 0.035:
            return True
    return False
