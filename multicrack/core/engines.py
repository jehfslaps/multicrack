"""The three chopping engines: one-shots, grooves (loops + hits + rolls) and events."""
from __future__ import annotations

import numpy as np

from . import ai, classify
from .dsp import Analysis, farthest_pick, group_items
from .model import DRUM_LABELS, Chop, Stem
from .naming import split_tokens

MAX_HIT_LEN = {"kick": 1.5, "snare": 2.0, "clap": 1.5, "hats": 1.6, "cymbals": 6.0,
               "toms": 2.5, "mixed": 3.0, "drums": 2.0, "perc": 1.5, "fills": 2.5}
VARIATIONS = 3
VARIATIONS_PERC = 6
MIN_DIFF_HIT = 0.05      # hits closer than this count as copies of each other
MIN_DIFF_EVENT = 0.06


def get_analysis(stem: Stem) -> Analysis:
    an = stem.analysis.get("an")
    if an is None:
        an = Analysis(stem.mono(), stem.sr)
        stem.analysis["an"] = an
    return an


def get_onsets(stem: Stem, an: Analysis) -> np.ndarray:
    """Onsets with false hits removed (spots where the sound doesn't actually get louder and
    the attack is weak). Those used to end chops early."""
    if "onsets" not in stem.analysis:
        raw = an.onsets()
        if len(raw) > 2:
            ra = np.array([_reattack_db(an, int(o)) for o in raw])
            fl = np.array([an.flux[max(0, int(o) // an.HOP_ONSET - 1):int(o) // an.HOP_ONSET + 4].max()
                           for o in raw])
            rel = fl / (np.median(fl) + 1e-12)
            raw = raw[~((ra < 2.0) & (rel < 0.5))]
        stem.analysis["onsets"] = raw
    return stem.analysis["onsets"]


# ------------------------------------------------------------------- hits
def _make_hits(an: Analysis, onsets: np.ndarray, context: str, region_end=None,
               within=None) -> list[dict]:
    """Measure every hit; `within` = (start, end) keeps only onsets inside a window and
    stops tails at the window end."""
    sr = an.sr
    max_len = MAX_HIT_LEN.get(context, 2.0)
    hits = []
    for i, s in enumerate(onsets):
        s = int(s)
        if within and not (within[0] <= s < within[1] - int(0.01 * sr)):
            continue
        nxt = int(onsets[i + 1]) if i + 1 < len(onsets) else an.n
        limit = nxt - int(0.003 * sr)
        if within:
            limit = min(limit, within[1])
        if region_end is not None:
            limit = min(limit, region_end)
        end, cut = an.tail_end(s, limit, rel_db=-50.0, max_len=max_len)
        if end - s < int(0.012 * sr):
            continue
        f = an.features(s, end)
        if f["attack"] > max(0.03, 0.3 * (end - s) / sr):
            continue        # the loud part comes late: the onset landed on something else
        pre_a = max(0, (s - int(0.006 * sr)) // an.HOP_ENV)
        pre = float(an.env[pre_a:max(pre_a + 1, s // an.HOP_ENV)].max()) / (f["level"] + 1e-9)
        gap = (nxt - s) / sr
        hits.append(dict(start=s, end=int(end), cut=bool(cut), f=f, gap=gap, pre=pre,
                         label=classify.drum_label(f, context)))
    if hits:
        loud = max(h["f"]["level"] for h in hits) + 1e-9
        for h in hits:
            rel = h["f"]["level"] / loud
            h["score"] = ((0.0 if h["cut"] else 1.0) + min(h["gap"], 1.2) * 0.5
                          - min(h["pre"], 1.0) * 1.5 + rel * 0.8)
            h["rel"] = rel
    return hits


def _pick_hits(stem: Stem, hits: list[dict], context: str) -> list[Chop]:
    by_label: dict = {}
    for h in hits:
        if h["rel"] < 0.12:          # ignore faint ghost notes and bleed
            continue
        by_label.setdefault(h["label"], []).append(h)
    chops = []
    for label in sorted(by_label, key=lambda l: DRUM_LABELS.index(l) if l in DRUM_LABELS else 99):
        group = sorted(by_label[label], key=lambda h: -h["score"])
        if context in ("drums", "perc", "fills", "mixed") and len(group) < 2 and len(hits) > 12:
            # a lone stray hit of a different type is usually a misread; keep only if clean
            if group[0]["cut"] or group[0]["pre"] > 0.3:
                continue
        top = group[:max(8, min(120, len(group) // 2))]
        vecs = np.stack([h["f"]["vec"] for h in top])
        k = VARIATIONS_PERC if label == "Perc" else VARIATIONS
        picked = farthest_pick(vecs, list(range(len(top))), k, MIN_DIFF_HIT)
        for i in sorted(picked, key=lambda i: top[i]["start"]):
            h = top[i]
            lab = label
            if context in ("drums", "perc", "fills", "mixed") and ai.available():
                lab = ai.hit_label(ai.tags(stem.mono()[h["start"]:h["end"]], stem.sr)) or label
            chops.append(Chop(stem_id=stem.id, start=h["start"], end=h["end"], label=lab,
                              kind="hit", cut_at_next=h["cut"],
                              flag="Tail cut at the next hit." if h["cut"] else ""))
    return chops


def oneshot_engine(stem: Stem) -> list[Chop]:
    an = get_analysis(stem)
    onsets = get_onsets(stem, an)
    hits = _make_hits(an, onsets, stem.context)
    chops = _pick_hits(stem, hits, stem.context)
    stem.analysis["sections"] = None
    return chops


# ----------------------------------------------------------------- grooves
def _bar_grid(stem: Stem, an: Analysis):
    grid = stem.analysis.get("grid")
    opt_bpm = stem.options.get("bpm")
    if grid is None:
        from . import tempo
        est = tempo.estimate(an)
        grid = dict(bpm=est["bpm"], downbeat=est["downbeat"]) if est else None
        stem.analysis["grid"] = grid
    if grid is None:
        return None
    bpm = float(opt_bpm or grid["bpm"])
    bar = 240.0 * an.sr / bpm
    d0 = float(grid["downbeat"]) % bar
    return bpm, bar, d0


def groove_engine(stem: Stem) -> list[Chop]:
    an = get_analysis(stem)
    sr = an.sr
    onsets = get_onsets(stem, an)
    ctx = stem.context
    opts = stem.options
    want_bars = int(opts.get("bars", 4))
    roll_mode = opts.get("roll_mode", "One-shot")
    include_hits = opts.get("include_hits", True)
    gopts = opts.setdefault("grooves", {})

    g = _bar_grid(stem, an)
    if g is None:
        stem.analysis["sections"] = dict(bpm=None, grooves=[], rolls=0, hits=0)
        return oneshot_engine_like(stem, an, onsets, ctx)
    bpm, bar, d0 = g
    nb = int((an.n - d0) // bar)
    H = an.HOP_ONSET
    flux, low, high = an.flux, an.flux_low, an.flux_high
    act_mask, _ = an.active_mask(512, rel_db=-42.0)

    descs, active = [], []
    for b in range(nb):
        s = d0 + b * bar
        steps = []
        for j in range(16):
            a = int((s + j * bar / 16) / H)
            e = max(a + 1, int((s + (j + 1) * bar / 16) / H))
            steps.append(float(flux[a:e].max()) if a < len(flux) else 0.0)
        p = np.array(steps)
        a0, a1 = int(s / H), int((s + bar) / H)
        prof = np.array([low[a0:a1].mean(), (flux[a0:a1] - low[a0:a1] - high[a0:a1]).clip(0).mean(),
                         high[a0:a1].mean()]) if a1 > a0 else np.zeros(3)
        pn = p / (np.linalg.norm(p) + 1e-9)
        prn = prof / (np.linalg.norm(prof) + 1e-9)
        descs.append(np.concatenate([pn, prn * 0.6]))
        m0, m1 = int(s / 512), int((s + bar) / 512)
        frac = float(act_mask[m0:m1].mean()) if m1 > m0 else 0.0
        active.append(frac > 0.55 and p.max() > 0)
    descs = np.array(descs) if descs else np.zeros((0, 19))

    def sim(i, j):
        return float(np.dot(descs[i], descs[j]) / (np.linalg.norm(descs[i]) * np.linalg.norm(descs[j]) + 1e-9))

    repeating = []
    for i in range(nb):
        ok = False
        if active[i]:
            for d in (-2, -1, 1, 2):
                j = i + d
                if 0 <= j < nb and active[j] and sim(i, j) > 0.86:
                    ok = True
                    break
        repeating.append(ok)
    segs = []
    i = 0
    while i < nb:
        if repeating[i]:
            j = i
            while j + 1 < nb and repeating[j + 1]:
                j += 1
            if j - i + 1 >= 2:
                segs.append((i, j + 1))
            i = j + 1
        else:
            i += 1

    # group sections that play the same groove
    clusters = []    # dict(center, segs)
    for sg in sorted(segs, key=lambda x: -(x[1] - x[0])):
        v = descs[sg[0]:sg[1]].mean(axis=0)
        v = v / (np.linalg.norm(v) + 1e-9)
        best, bs = None, 0.0
        for c in clusters:
            s_ = float(np.dot(v, c["center"]))
            if s_ > bs:
                best, bs = c, s_
        if best is not None and bs > 0.93:
            best["segs"].append(sg)
        else:
            clusters.append(dict(center=v, segs=[sg]))
    clusters.sort(key=lambda c: -sum(b - a for a, b in c["segs"]))
    clusters = clusters[:4]
    clusters.sort(key=lambda c: min(a for a, _ in c["segs"]))

    chops: list[Chop] = []
    pool: list[dict] = []
    sections = []
    in_groove = np.zeros(nb, bool)
    for a, b in segs:
        in_groove[a:b] = True

    def snap(x):
        if len(onsets) == 0:
            return int(round(x))
        k = int(np.argmin(np.abs(onsets - x)))
        return int(onsets[k]) if abs(onsets[k] - x) < 0.025 * sr else int(round(x))

    for ci, c in enumerate(clusters):
        name = f"Groove {chr(65 + ci)}"
        go = gopts.setdefault(name, {"loop": True, "chop": True})
        a, b = max(c["segs"], key=lambda x: x[1] - x[0])
        seg_len = b - a
        n_use = max(n for n in (16, 8, 4, 2, 1) if n <= max(1, min(want_bars, seg_len)))
        start_bar = a
        ls = snap(d0 + start_bar * bar)
        le = min(an.n, ls + int(round(n_use * bar)))
        hits = _make_hits(an, onsets, ctx, within=(ls, le))
        label = classify.loop_label([h["label"] for h in hits if h["rel"] > 0.3], ctx,
                                    float(np.mean([h["f"]["centroid"] for h in hits])) if hits else 0)
        where = ", ".join(f"bars {x + 1}–{y}" for x, y in sorted(c["segs"])[:3])
        sections.append(dict(name=name, where=where, bars=n_use, label=label,
                             short=n_use < want_bars, hits=len(hits),
                             start=ls, end=le, loop=go["loop"], chop=go["chop"]))
        if go["loop"]:
            chops.append(Chop(stem_id=stem.id, start=ls, end=le, label=label, kind="loop",
                              bars=n_use, flag=(f"This section only fits {n_use} bars."
                                                if n_use < want_bars else "")))
        if go["chop"]:
            pool.extend(hits)

    # outside the grooves: rolls and single hits
    def bar_of(x):
        return int((x - d0) // bar)

    outside = [int(o) for o in onsets if not (0 <= bar_of(o) < nb and in_groove[bar_of(o)])]
    rolls, singles = [], []
    i = 0
    while i < len(outside):
        j = i
        while (j + 1 < len(outside) and outside[j + 1] - outside[j] < 0.17 * sr
               and outside[j + 1] - outside[i] < 2.2 * bar):
            j += 1
        group = outside[i:j + 1]
        if len(group) >= 4 and group[-1] - group[0] > 0.25 * sr:
            rolls.append(group)
        else:
            singles.extend(group)
        i = j + 1

    roll_items = []
    for grp in rolls:
        nxt = [o for o in onsets if o > grp[-1]]
        limit = int(nxt[0]) - int(0.0015 * sr) if nxt else an.n
        end, cut = an.tail_end(grp[-1], limit, rel_db=-50.0, max_len=2.5)
        roll_items.append(dict(start=grp[0], end=int(end), cut=cut,
                               f=an.event_features(grp[0], int(end))))
    kept_rolls = []
    if roll_items and roll_mode != "Skip":
        vecs = np.stack([r["f"]["vec"] for r in roll_items])
        order = sorted(range(len(roll_items)), key=lambda k: -roll_items[k]["f"]["level"])
        for grp in group_items(vecs, order, 0.32):
            for k in farthest_pick(vecs, grp, 2, MIN_DIFF_EVENT):
                kept_rolls.append(roll_items[k])
        kept_rolls = sorted(kept_rolls, key=lambda r: -r["f"]["level"])[:6]
        for r in sorted(kept_rolls, key=lambda r: r["start"]):
            if roll_mode == "Loop":
                bstart = d0 + bar_of(r["start"]) * bar
                nbars = max(1, int(np.ceil((r["end"] - bstart) / bar - 0.15)))
                s_ = snap(bstart)
                chops.append(Chop(stem_id=stem.id, start=s_, end=min(an.n, s_ + int(round(nbars * bar))),
                                  label="Fill", kind="loop", bars=nbars))
            else:
                chops.append(Chop(stem_id=stem.id, start=r["start"], end=r["end"], label="Roll",
                                  kind="roll", cut_at_next=r["cut"],
                                  flag="Ends where the next sound starts." if r["cut"] else ""))

    if include_hits and singles:
        sset = set(singles)
        pool.extend(h for h in _make_hits(an, onsets, ctx) if h["start"] in sset)
    if pool:
        loud = max(h["f"]["level"] for h in pool) + 1e-9
        for h in pool:
            h["rel"] = h["f"]["level"] / loud
        chops.extend(_pick_hits(stem, pool, ctx))

    stem.analysis["sections"] = dict(bpm=bpm, grooves=sections, rolls=len(roll_items),
                                      rolls_kept=len(kept_rolls), hits=len(singles))
    return chops


def oneshot_engine_like(stem, an, onsets, ctx):
    hits = _make_hits(an, onsets, ctx)
    return _pick_hits(stem, hits, ctx)


# ------------------------------------------------------------------ events
EVENT_PARAMS = {
    "fx": dict(gap=0.25, min_len=0.08, max_len=14.0, cap=20, group=0.30),
    "vocal": dict(gap=0.14, min_len=0.12, max_len=6.0, cap=16, group=0.28),
    "melodic": dict(gap=0.15, min_len=0.12, max_len=4.0, cap=12, group=0.14),
}


def _regions(an: Analysis, gap: float, min_len: float):
    hop = 256
    mask, _env = an.active_mask(hop, rel_db=-45.0)
    sr = an.sr
    idx = np.where(mask)[0]
    if not len(idx):
        return []
    regs = []
    start = prev = idx[0]
    gap_f = int(gap * sr / hop)
    for i in idx[1:]:
        if i - prev > gap_f:
            regs.append((start, prev + 1))
            start = i
        prev = i
    regs.append((start, prev + 1))
    out = []
    for a, b in regs:
        s, e = a * hop, min(an.n, b * hop)
        if (e - s) / sr >= min_len:
            out.append((s, e))
    return out


def _split_long(an: Analysis, s: int, e: int, max_len: float, min_piece: float):
    sr = an.sr
    if (e - s) / sr <= max_len:
        return [(s, e)]
    env = an.env[s // an.HOP_ENV:e // an.HOP_ENV]
    k = max(1, int(0.03 * sr / an.HOP_ENV))
    sm = np.convolve(env, np.ones(k) / k, mode="same")
    lo = int(min_piece * sr / an.HOP_ENV)
    if len(sm) <= 2 * lo:
        return [(s, s + int(max_len * sr))]
    cut = lo + int(np.argmin(sm[lo:len(sm) - lo]))
    c = s + cut * an.HOP_ENV
    return _split_long(an, s, c, max_len, min_piece) + _split_long(an, c, e, max_len, min_piece)


def events_engine(stem: Stem, bpm=None) -> list[Chop]:
    an = get_analysis(stem)
    sr = an.sr
    ctx = stem.context
    family = "fx" if ctx == "fx" else "vocal" if ctx == "vocal" else "melodic"
    P = dict(EVENT_PARAMS[family])
    if family == "melodic" and bpm:
        P["max_len"] = min(8.0, 2 * 240.0 / bpm)
    fx_hint = "fx" in [t.lower() for t in split_tokens(stem.name)]
    segs = []
    for s, e in _regions(an, P["gap"], P["min_len"]):
        s = an.refine_start(s) if family != "melodic" else s
        if family == "melodic":
            segs.extend(_melodic_units(stem, an, s, e, bpm))
        else:
            for a, b in _split_long(an, s, e, P["max_len"], 0.8 if family == "vocal" else 1.5):
                nxt = b + int(0.25 * sr)
                end, _cut = an.tail_end(max(a, b - int(0.03 * sr)), min(an.n, nxt), rel_db=-55.0)
                segs.append((a, max(b, end), False))
    if not segs:
        return []
    items = []
    for s, e, trimmed in segs:
        f = an.event_features(s, e)
        if family == "fx":
            label = classify.fx_label(f)
            tg = ai.tags(an.m[s:e], sr)
            label = ai.fx_label(tg) or label
        elif family == "vocal":
            label = classify.vocal_label(f, fx_hint)
            label = ai.vocal_label(ai.tags(an.m[s:e], sr), label) if ai.available() else label
        else:
            label = classify.melodic_label(f, ctx)
        items.append(dict(start=s, end=e, f=f, label=label, trimmed=trimmed))
    loud = max(it["f"]["level"] for it in items) + 1e-9
    items = [it for it in items if it["f"]["level"] / loud > 0.08]
    vecs = np.stack([it["f"]["vec"] for it in items])
    order = sorted(range(len(items)), key=lambda k: -items[k]["f"]["level"])
    groups = group_items(vecs, order, P["group"])
    groups.sort(key=lambda g: -(len(g) ** 0.5 * items[g[0]]["f"]["level"]))
    per_group = [farthest_pick(vecs, g, VARIATIONS, MIN_DIFF_EVENT) for g in groups]
    picked = []
    for rnd in range(VARIATIONS):          # one of each sound first, then the variations
        for pg in per_group:
            if rnd < len(pg) and len(picked) < P["cap"]:
                picked.append(pg[rnd])
    if family == "melodic":
        picked = picked[:6]
        phrase_chops = _phrases(stem, an, ctx, bars=1, cap=3) + _phrases(stem, an, ctx, bars=2, cap=3)
    else:
        phrase_chops = []
    chops = []
    for k in sorted(picked, key=lambda k: items[k]["start"]):
        it = items[k]
        origin = "ai" if family == "melodic" else "auto"
        flag = "AI suggestion: check the label." if family == "melodic" else ""
        if it["trimmed"]:
            flag = (flag + " Long part trimmed.").strip()
        chops.append(Chop(stem_id=stem.id, start=it["start"], end=it["end"], label=it["label"],
                          kind="event", origin=origin, flag=flag))
    chops.extend(phrase_chops)
    chops.sort(key=lambda c: c.start)
    stem.analysis["sections"] = None
    return chops


def _melodic_units(stem: Stem, an: Analysis, s: int, e: int, bpm) -> list:
    """Split a melodic passage into musical units: each starts on a clear new attack, lasts at
    least one beat, and runs until the next clear attack (at most one bar)."""
    sr = an.sr
    beat = (60.0 / bpm) if bpm else 0.48
    min_unit = int(beat * sr * 0.95)
    max_unit = int(4 * beat * sr)
    strong = [int(o) for o in get_onsets(stem, an)
              if s + int(0.05 * sr) <= o < e - int(0.05 * sr) and _reattack_db(an, int(o)) >= 6.0]
    starts = [an.refine_start(s)] + strong
    out = []
    i = 0
    while i < len(starts):
        st = starts[i]
        j = i + 1
        while j < len(starts) and starts[j] - st < min_unit:
            j += 1
        if j < len(starts):
            natural = starts[j] - int(0.003 * sr)
        else:   # end of the passage: keep the full release
            natural, _cut = an.tail_end(max(st, e - int(0.03 * sr)), min(an.n, e + int(2.0 * sr)),
                                        rel_db=-55.0)
            natural = max(natural, e)
        end = min(natural, st + max_unit)
        if end - st >= int(0.12 * sr):
            out.append((st, end, end < natural))
        i = j
    return out


def _reattack_db(an: Analysis, o: int) -> float:
    """How much louder the sound gets right after an onset (dB)."""
    sr, H = an.sr, an.HOP_ENV
    before = an.env[max(0, (o - int(0.03 * sr)) // H):max(1, o // H)]
    after = an.env[o // H:max(o // H + 1, (o + int(0.035 * sr)) // H)]
    if not len(before) or not len(after):
        return 99.0
    return float(20 * np.log10((after.max() + 1e-9) / (before.min() + 1e-9)))


def _phrases(stem: Stem, an: Analysis, ctx: str, bars: int = 2, cap: int = 3) -> list[Chop]:
    """Bar-aligned phrase suggestions (riffs, chord progressions)."""
    grid = stem.analysis.get("grid")
    if not grid:
        return []
    sr = an.sr
    bar = 240.0 * sr / float(grid["bpm"])
    d0 = float(grid["downbeat"]) % bar
    mask, _ = an.active_mask(512, rel_db=-40.0)
    cands = []
    b = 0
    while d0 + (b + bars) * bar <= an.n:
        s, e = int(round(d0 + b * bar)), int(round(d0 + (b + bars) * bar))
        frac = float(mask[s // 512:e // 512].mean()) if e // 512 > s // 512 else 0.0
        if frac > 0.8:
            cands.append((s, e))
        b += bars
    if not cands:
        return []
    feats = [an.event_features(s, e) for s, e in cands]
    vecs = np.stack([f["vec"] for f in feats])
    order = sorted(range(len(cands)), key=lambda k: -feats[k]["level"])
    groups = group_items(vecs, order, 0.12)
    groups.sort(key=lambda g: -len(g))
    label = {"guitar": "Guitar Lead", "keys": "Keys", "strings": "Strings",
             "brass": "Brass", "bass": "Bass"}.get(ctx, "Synth Lead")
    out = []
    for g in groups[:cap]:
        s, e = cands[g[0]]
        out.append(Chop(stem_id=stem.id, start=s, end=e, label=label, kind="event", origin="ai",
                        flag=f"AI suggestion: {bars}-bar phrase."))
    return out
