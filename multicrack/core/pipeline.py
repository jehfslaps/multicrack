"""High-level steps: detect stem types, lock the song tempo, chop, export."""
from __future__ import annotations

import os

import numpy as np

from . import ai, classify, engines, tempo
from .audio import render_chop, write_wav24
from .dsp import pitch_strength
from .model import STEM_KINDS, Chop, Stem
from .naming import assign_names

DRUM_KINDS = {"Kick", "Snare", "Clap", "Hats", "Cymbals", "Toms", "Full drums", "Drum loops",
              "Perc / loops", "Fills", "Mixed hits"}


def detect_kind(stem: Stem) -> str:
    """Work out what a stem is: file name first, then the sound itself."""
    an = engines.get_analysis(stem)
    centroid = classify.summarize_spectrum(an)
    stem.analysis["centroid"] = centroid
    hints = classify.kinds_from_name(stem.name)
    stem.analysis["ai_used"] = False
    if len(hints) == 1:
        hinted = hints[0]
    else:
        # no clue in the name, or it points two ways ("Vox_Fx"): let the trained model listen
        hinted = ai.best_kind(stem, an, hints or None)
        stem.analysis["ai_used"] = hinted is not None
        if hinted is None and hints:
            hinted = hints[0]
    if hinted == "Synth" and centroid and centroid < 300:
        hinted = "Bass"
    if hinted:
        return hinted
    onsets = engines.get_onsets(stem, an)
    sample = onsets[:: max(1, len(onsets) // 150)]
    counts: dict = {}
    for i, s in enumerate(sample):
        e = min(an.n, int(s) + int(0.3 * an.sr))
        lab = classify.drum_label(an.features(int(s), e), "drums")
        counts[lab] = counts.get(lab, 0) + 1
    mask, _ = an.active_mask(1024)
    active = float(mask.mean()) if len(mask) else 0.0
    loud = np.argsort(-an.env[::64])[:8] * 64 * an.HOP_ENV
    pitch = float(np.median([pitch_strength(an.m[int(p):int(p) + int(0.2 * an.sr)], an.sr)
                             for p in loud])) if len(loud) else 0.0
    est = tempo.estimate(an) if len(onsets) > 16 else None
    conf = est["confidence"] if est else 0.0
    return classify.kind_from_audio(an, onsets, counts, conf, active, pitch, centroid)


def lock_tempo(stems: list[Stem]) -> dict | None:
    """One tempo for the whole song, from the clearest drum stem."""
    best = None
    for st in stems:
        if st.mode != "auto" or st.kind not in DRUM_KINDS or st.seconds < 6:
            continue
        an = engines.get_analysis(st)
        est = st.analysis.get("tempo_est") or tempo.estimate(an)
        st.analysis["tempo_est"] = est
        if est and (best is None or est["confidence"] > best[1]["confidence"]):
            best = (st, est)
    if best is None:
        return None
    ref, est = best
    song = dict(bpm=est["bpm"], downbeat=est["downbeat"], ref=ref.id, frames=ref.frames,
                sr=ref.sr)
    return song


def apply_grid(stem: Stem, song: dict | None) -> None:
    stem.analysis.pop("tempo_warning", None)
    if song is None:
        stem.analysis.pop("grid", None)
        return
    same_timeline = (stem.sr == song["sr"] and abs(stem.frames - song["frames"]) < stem.sr)
    if same_timeline:
        stem.analysis["grid"] = dict(bpm=song["bpm"], downbeat=song["downbeat"])
    else:
        an = engines.get_analysis(stem)
        est = stem.analysis.get("tempo_est") or tempo.estimate(an)
        stem.analysis["tempo_est"] = est
        if est is None:
            stem.analysis["grid"] = dict(bpm=song["bpm"], downbeat=0)
        else:
            stem.analysis["grid"] = dict(bpm=song["bpm"] if tempo.fits(est["bpm"], song["bpm"])
                                         else est["bpm"], downbeat=est["downbeat"])
    if stem.engine == "groove":
        est = stem.analysis.get("tempo_est")
        if est is None and stem.kind in DRUM_KINDS:
            est = tempo.estimate(engines.get_analysis(stem))
            stem.analysis["tempo_est"] = est
        if est and est["confidence"] > 2.0 and not tempo.fits(est["bpm"], song["bpm"]):
            stem.analysis["tempo_warning"] = (
                f"Rhythm doesn't fit the song tempo ({song['bpm']:g} BPM). Check its loops.")


def chop_stem(stem: Stem, song: dict | None) -> list[Chop]:
    if stem.mode != "auto":
        return []
    if stem.kind not in STEM_KINDS:
        stem.kind = "Melodic (other)"
    apply_grid(stem, song)
    eng = stem.engine
    if eng == "oneshot":
        chops = engines.oneshot_engine(stem)
    elif eng == "groove":
        chops = engines.groove_engine(stem)
    else:
        chops = engines.events_engine(stem, bpm=song["bpm"] if song else None)
    warn = stem.analysis.get("tempo_warning")
    if warn:
        for c in chops:
            if c.kind == "loop":
                c.flag = (c.flag + " " + warn).strip()
    return chops


def process(stems: list[Stem], progress=None) -> tuple[list[Chop], dict | None]:
    work = [s for s in stems if s.mode == "auto"]
    if progress:
        progress("Finding the song tempo", 0, max(1, len(work)) + 1)
    song = lock_tempo(stems)
    out = []
    for i, st in enumerate(work):
        if progress:
            progress(f"Chopping {st.name}", i + 1, len(work) + 1)
        try:
            chops = chop_stem(st, song)
            st.status = f"{len(chops)} chops" if chops else "Nothing found"
        except Exception as e:  # keep going with the other files
            chops = []
            st.status = "Couldn't chop this file"
            st.analysis["error"] = repr(e)
        out.extend(chops)
    return out, song


def export(stems_by_id: dict, chops: list[Chop], folder: str, prefix: str,
           progress=None) -> list[str]:
    os.makedirs(folder, exist_ok=True)
    names = assign_names(chops, prefix, folder)
    written = []
    for i, c in enumerate(chops):
        st = stems_by_id[c.stem_id]
        if progress:
            progress(f"Writing {names[c.id]}", i, len(chops))
        path = os.path.join(folder, names[c.id])
        write_wav24(path, render_chop(st, c), st.sr)
        written.append(path)
    return written
