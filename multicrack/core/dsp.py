"""Signal analysis: envelopes, onsets, tails and per-sound features (numpy only)."""
from __future__ import annotations

import numpy as np

EPS = 1e-12


def db(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), EPS))


def frame_rms(m: np.ndarray, hop: int, win: int) -> np.ndarray:
    """RMS of windows centred on k*hop."""
    sq = np.square(m, dtype=np.float64)
    c = np.concatenate(([0.0], np.cumsum(sq)))
    n = len(m)
    centers = np.arange(0, n, hop)
    a = np.clip(centers - win // 2, 0, n)
    b = np.clip(centers + win // 2, 0, n)
    return np.sqrt(np.maximum(c[b] - c[a], 0) / np.maximum(b - a, 1)).astype(np.float32)


def moving_mean(x: np.ndarray, w: int) -> np.ndarray:
    w = max(1, int(w))
    c = np.concatenate(([0.0], np.cumsum(x, dtype=np.float64)))
    n = len(x)
    i = np.arange(n)
    a = np.clip(i - w // 2, 0, n)
    b = np.clip(i + w // 2 + 1, 0, n)
    return ((c[b] - c[a]) / np.maximum(b - a, 1)).astype(np.float32)


def stft_mag_chunks(m: np.ndarray, n_fft: int, hop: int, chunk: int = 2048):
    """Yield (first_frame, |STFT| chunk). Frame k is centred on sample k*hop."""
    win = np.hanning(n_fft).astype(np.float32)
    pad = np.concatenate([np.zeros(n_fft // 2, np.float32), m.astype(np.float32),
                          np.zeros(n_fft, np.float32)])
    n_frames = 1 + len(m) // hop
    view = np.lib.stride_tricks.sliding_window_view(pad, n_fft)[::hop][:n_frames]
    for s in range(0, n_frames, chunk):
        fr = view[s:s + chunk] * win
        yield s, np.abs(np.fft.rfft(fr, axis=1)).astype(np.float32)


def band_edges(sr: int, n_fft: int, n_bands: int = 24, lo: float = 30.0, hi: float = 16000.0):
    hi = min(hi, sr / 2 * 0.98)
    edges_hz = np.geomspace(lo, hi, n_bands + 1)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    return np.searchsorted(freqs, edges_hz), freqs


class Analysis:
    """Per-stem analysis shared by the engines (computed once, cached on the stem)."""

    HOP_ENV = 64          # fine amplitude envelope
    HOP_ONSET = 256       # onset-strength frames

    def __init__(self, m: np.ndarray, sr: int):
        self.m = m
        self.sr = sr
        self.n = len(m)
        self.env = frame_rms(m, self.HOP_ENV, self.HOP_ENV * 4)            # ~1.5 ms frames
        self.peak = float(np.max(np.abs(m))) if self.n else 0.0
        # noise floor: quietest non-silent level, never higher than -60 dB below the peak
        # (stems with long digital silence would otherwise report a floor inside the music)
        nz = self.env[self.env > 1e-7]
        floor = float(np.percentile(nz, 2)) if len(nz) else 1e-7
        floor = min(floor, self.peak * 10 ** (-60 / 20))
        self.floor = max(floor, self.peak * 10 ** (-90 / 20), 1e-8)
        self._onset_strength()

    # ------------------------------------------------------------- onsets
    def _onset_strength(self):
        n_fft, hop = 1024, self.HOP_ONSET
        freqs = np.fft.rfftfreq(n_fft, 1.0 / self.sr)
        low = freqs < 160
        high = freqs > 5000
        ref = max(self.peak, 1e-6)
        full, lowe, highe, prev = [], [], [], None
        for _s, mag in stft_mag_chunks(self.m, n_fft, hop):
            lm = np.log1p(mag * (100.0 / ref))
            first = lm[:1] if prev is None else prev
            d = np.diff(np.vstack([first, lm]), axis=0)
            prev = lm[-1:]
            np.maximum(d, 0, out=d)
            full.append(d.mean(axis=1))
            lowe.append(d[:, low].mean(axis=1))
            highe.append(d[:, high].mean(axis=1) if high.any() else d.mean(axis=1) * 0)
        self.flux = np.concatenate(full).astype(np.float32)
        self.flux_low = np.concatenate(lowe).astype(np.float32)
        self.flux_high = np.concatenate(highe).astype(np.float32)
        self.fps = self.sr / hop

    def onsets(self, sensitivity: float = 1.0, min_gap: float = 0.035):
        """Detect onsets; returns int array of attack-start sample positions."""
        f = self.flux
        if len(f) < 5:
            return np.zeros(0, int)
        fps = self.fps
        base = moving_mean(f, int(0.3 * fps))
        p99 = float(np.percentile(f, 99.5)) if len(f) else 0.0
        delta = 0.06 * p99 / max(sensitivity, 0.1)
        thr = base * 1.4 + delta
        # level gate: frame must be well above the noise floor
        env_at = self.env[np.clip((np.arange(len(f)) * self.HOP_ONSET) // self.HOP_ENV, 0,
                                  len(self.env) - 1)]
        gate = max(self.floor * 4, self.peak * 10 ** (-48 / 20))
        cand = np.where((f > thr) & (f >= np.roll(f, 1)) & (f >= np.roll(f, -1)))[0]
        out = []
        last = -10 ** 9
        min_frames = max(1, int(min_gap * fps))
        for i in cand:
            lo, hi = max(0, i - 2), min(len(f), i + 3)
            if f[i] < f[lo:hi].max():
                continue
            # level after the onset must clear the gate
            look = env_at[i:min(len(env_at), i + int(0.03 * fps) + 1)]
            if look.size == 0 or look.max() < gate:
                continue
            if i - last < min_frames:
                if out and f[i] > f[out[-1]]:
                    out[-1] = i
                    last = i
                continue
            out.append(i)
            last = i
        starts = [self.refine_start(int(i * self.HOP_ONSET)) for i in out]
        starts = np.array(sorted(set(starts)), dtype=int)
        if len(starts) > 1:   # merge duplicates that refined to (almost) the same place
            keep = np.concatenate(([True], np.diff(starts) > int(0.02 * self.sr)))
            starts = starts[keep]
        return starts

    def refine_start(self, approx: int) -> int:
        """Move an approximate onset to just before the attack begins."""
        sr = self.sr
        a = max(0, approx - int(0.025 * sr))
        b = min(self.n, approx + int(0.03 * sr))
        if b - a < 8:
            return max(0, approx)
        seg = np.abs(self.m[a:b])
        k = max(1, int(0.0005 * sr))
        sm = np.convolve(seg, np.ones(k) / k, mode="same")
        p = int(np.argmax(sm))
        pk = sm[p]
        if pk <= 0:
            return max(0, approx)
        before = sm[:p + 1]
        below = np.where(before < 0.05 * pk)[0]
        st = below[-1] if len(below) else 0
        st = a + st - int(0.0008 * sr)
        return int(max(0, st))

    # --------------------------------------------------------------- tails
    def peak_index(self, start: int, end: int) -> int:
        a = start // self.HOP_ENV
        b = max(a + 1, min(len(self.env), end // self.HOP_ENV))
        return a + int(np.argmax(self.env[a:b]))

    def tail_end(self, start: int, limit: int, rel_db: float = -50.0, hold: float = 0.025,
                 max_len: float = None):
        """End of a sound's tail. Returns (end_sample, cut_at_limit)."""
        sr, H = self.sr, self.HOP_ENV
        if max_len:
            limit = min(limit, start + int(max_len * sr))
        limit = min(limit, self.n)
        if limit - start < int(0.004 * sr):
            return limit, True
        pk = self.peak_index(start, min(limit, start + int(0.08 * sr)))
        thr = max(self.env[pk] * 10 ** (rel_db / 20.0), self.floor * 1.6)
        seg = self.env[pk:max(pk + 1, limit // H)]
        below = (seg < thr).astype(np.int32)
        hf = max(1, int(hold * sr / H))
        if len(below) >= hf:
            c = np.concatenate(([0], np.cumsum(below)))
            run = c[hf:] - c[:-hf]
            idx = np.where(run == hf)[0]
            if len(idx):
                end = (pk + int(idx[0])) * H + int(0.004 * sr)
                if end < limit:
                    return int(end), False
        return int(limit), True

    def active_mask(self, hop: int, rel_db: float = -45.0):
        """Boolean activity per `hop` samples."""
        env = frame_rms(self.m, hop, hop * 2)
        thr = max(self.peak * 10 ** (rel_db / 20.0), self.floor * 4)
        return env > thr, env

    # ------------------------------------------------------------ features
    def features(self, start: int, end: int) -> dict:
        """Spectral / envelope features of a short sound."""
        sr = self.sr
        n_fft = 2048
        seg = self.m[start:min(end, start + int(0.4 * sr))]
        if len(seg) < n_fft:
            seg = np.concatenate([seg, np.zeros(n_fft - len(seg), np.float32)])
        win = np.hanning(n_fft).astype(np.float32)
        hops = [0, n_fft // 4, n_fft // 2]
        spec = np.zeros(n_fft // 2 + 1, np.float64)
        for h in hops:
            fr = seg[h:h + n_fft]
            if len(fr) < n_fft:
                fr = np.concatenate([fr, np.zeros(n_fft - len(fr), np.float32)])
            spec += np.abs(np.fft.rfft(fr * win)) ** 2
        spec /= len(hops)
        edges, freqs = band_edges(sr, n_fft)
        bands = np.array([spec[edges[i]:max(edges[i] + 1, edges[i + 1])].sum()
                          for i in range(len(edges) - 1)])
        total = spec[(freqs > 20)].sum() + EPS
        cent = float((freqs * spec).sum() / (spec.sum() + EPS))
        lo = float(spec[(freqs > 20) & (freqs < 150)].sum() / total)
        hi = float(spec[freqs > 6000].sum() / total)
        mid = float(spec[(freqs >= 150) & (freqs <= 6000)].sum() / total)
        band = spec[(freqs > 100) & (freqs < min(16000, sr / 2))] + EPS
        flat = float(np.exp(np.mean(np.log(band))) / np.mean(band))
        # envelope: decay from peak to -20 dB / -40 dB
        H = self.HOP_ENV
        a = start // H
        b = max(a + 2, min(len(self.env), end // H))
        e = self.env[a:b]
        p = int(np.argmax(e))
        pk = e[p] + EPS
        after = e[p:]
        d20 = np.where(after < pk * 0.1)[0]
        decay = (d20[0] if len(d20) else len(after)) * H / sr
        attack = p * H / sr
        # clap check: several bursts in the first 40 ms
        fine = np.abs(self.m[start:start + int(0.045 * sr)])
        bursts = 0
        if len(fine) > 20:
            k = max(1, int(0.001 * sr))
            sm = np.convolve(fine, np.ones(k) / k, mode="same")
            mx = sm.max() + EPS
            pk_idx = np.where((sm[1:-1] > sm[:-2]) & (sm[1:-1] >= sm[2:]) & (sm[1:-1] > 0.45 * mx))[0]
            if len(pk_idx):
                sep = int(0.004 * sr)
                last = -sep
                for q in pk_idx:
                    if q - last >= sep:
                        bursts += 1
                        last = q
        logb = np.log10(bands + EPS)
        shape = logb - logb.mean()
        nrm = np.linalg.norm(shape) + EPS
        env_pts = np.interp(np.linspace(0, len(e) - 1, 12), np.arange(len(e)), db(e / pk) / 60.0)
        vec = np.concatenate([shape / nrm * 3.0, env_pts * 1.2, [np.log10(decay + 0.01)]])
        return dict(centroid=cent, low=lo, high=hi, mid=mid, flat=flat, decay=decay,
                    attack=attack, bursts=bursts, level=float(pk), vec=vec.astype(np.float32))

    def event_features(self, start: int, end: int) -> dict:
        """Features for longer sounds (FX, vocals, melodic)."""
        sr = self.sr
        seg = self.m[start:end]
        n_fft, hop = 2048, 1024
        if len(seg) < n_fft:
            seg = np.concatenate([seg, np.zeros(n_fft - len(seg), np.float32)])
        mags = np.vstack([m_ for _s, m_ in stft_mag_chunks(seg, n_fft, hop)])
        pw = mags ** 2
        edges, freqs = band_edges(sr, n_fft)
        bands = np.stack([pw[:, edges[i]:max(edges[i] + 1, edges[i + 1])].sum(axis=1)
                          for i in range(len(edges) - 1)], axis=1)
        lb = np.log10(bands + 1e-10)
        mean_shape = lb.mean(axis=0)
        mean_shape = mean_shape - mean_shape.mean()
        sd = lb.std(axis=0)
        tot = pw.sum(axis=1) + EPS
        cent_t = (pw * freqs).sum(axis=1) / tot
        energy = np.sqrt(tot)
        e_db = db(energy / (energy.max() + EPS))
        env_pts = np.interp(np.linspace(0, len(e_db) - 1, 16), np.arange(len(e_db)), e_db) / 60.0
        spec = pw.mean(axis=0)
        band = spec[(freqs > 100) & (freqs < min(12000, sr / 2))] + EPS
        flat = float(np.exp(np.mean(np.log(band))) / np.mean(band))
        weight = energy / (energy.sum() + EPS)
        cent = float((cent_t * weight).sum())
        thirds = np.array_split(np.arange(len(cent_t)), 3)
        cent_parts = [float((cent_t[t] * weight[t]).sum() / (weight[t].sum() + EPS)) for t in thirds]
        dur = (end - start) / sr
        peak_pos = float(np.argmax(energy) / max(1, len(energy) - 1))
        # attack sharpness (time to peak of the fine envelope)
        H = self.HOP_ENV
        e = self.env[start // H:max(start // H + 2, end // H)]
        attack = float(np.argmax(e) * H / sr)
        pitch = pitch_strength(self.m[start:end], sr)
        # polyphony estimate: prominent spectral peaks between 80 Hz and 2 kHz
        sel = (freqs > 80) & (freqs < 2000)
        s = spec[sel]
        peaks = 0
        if len(s) > 5:
            sdb = 10 * np.log10(s + EPS)
            mx = sdb.max()
            loc = np.where((sdb[1:-1] > sdb[:-2]) & (sdb[1:-1] > sdb[2:]) & (sdb[1:-1] > mx - 24))[0]
            peaks = len(loc)
        vec = np.concatenate([mean_shape / (np.linalg.norm(mean_shape) + EPS) * 3.0, sd * 0.6,
                              env_pts, [np.log2(dur + 0.05) * 0.8]])
        return dict(centroid=cent, cent_parts=cent_parts, flat=flat, dur=dur, peak_pos=peak_pos,
                    attack=attack, pitch=pitch, peaks=peaks,
                    level=float(np.max(np.abs(self.m[start:end])) if end > start else 0.0),
                    vec=vec.astype(np.float32))


def pitch_strength(x: np.ndarray, sr: int) -> float:
    """0..1: how strongly periodic (voiced / tonal) a sound is, between 70 and 900 Hz."""
    if len(x) < int(0.05 * sr):
        return 0.0
    n = int(0.04 * sr)
    starts = np.linspace(0, len(x) - n, num=min(8, max(1, len(x) // n)), dtype=int)
    lo, hi = int(sr / 900), int(sr / 70)
    vals = []
    for s in starts:
        fr = x[s:s + n].astype(np.float64)
        fr = fr - fr.mean()
        e = np.dot(fr, fr)
        if e < 1e-9:
            continue
        spec = np.fft.rfft(fr, 2 * n)
        ac = np.fft.irfft(np.abs(spec) ** 2)[:n]
        ac /= ac[0] + EPS
        if hi >= len(ac):
            hi = len(ac) - 1
        vals.append(float(np.max(ac[lo:hi])) if hi > lo else 0.0)
    return float(np.median(vals)) if vals else 0.0


def farthest_pick(vecs: np.ndarray, order: list[int], k: int, min_dist: float) -> list[int]:
    """Pick up to k items: first the most typical, then the most different ones.
    `order` lists candidate indices (cleanest first)."""
    if not order:
        return []
    cand = order
    V = vecs[cand]
    if len(cand) == 1:
        return [cand[0]]
    # most typical = smallest mean distance to the cleanest candidates
    D = np.sqrt(((V[:, None, :] - V[None, :, :]) ** 2).mean(axis=2))
    rank_bonus = np.linspace(0, 0.15, len(cand)) * (D.mean() + EPS)
    first = int(np.argmin(D.mean(axis=1) + rank_bonus))
    chosen = [first]
    while len(chosen) < k:
        md = D[:, chosen].min(axis=1)
        md[chosen] = -1
        j = int(np.argmax(md))
        if md[j] < min_dist:
            break
        chosen.append(j)
    return [cand[i] for i in chosen]


def group_items(vecs: np.ndarray, order: list[int], threshold: float) -> list[list[int]]:
    """Greedy grouping of similar sounds (order = importance)."""
    groups: list[list[int]] = []
    centers: list[np.ndarray] = []
    for i in order:
        v = vecs[i]
        best, bd = -1, 1e9
        for gi, c in enumerate(centers):
            d = float(np.sqrt(((v - c) ** 2).mean()))
            if d < bd:
                best, bd = gi, d
        if best >= 0 and bd < threshold:
            groups[best].append(i)
        else:
            groups.append([i])
            centers.append(v.copy())
    return groups
