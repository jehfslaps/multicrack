"""Working out what a stem is and what each sound in it is."""
from __future__ import annotations

import numpy as np

from .naming import split_tokens

# filename tokens -> stem kind (checked in this order)
HINTS = [
    ("Vocals", {"vox", "vocal", "vocals", "voc", "vo", "adlib", "adlibs", "shout", "shouts",
                "chant", "chants", "bgv", "bv", "bvs", "harmony", "harmonies", "acapella", "acap"}),
    ("Kick", {"kick", "kicks", "kik", "kck", "bd", "bassdrum"}),
    ("Snare", {"snare", "snares", "snr", "sd", "rim", "rimshot"}),
    ("Clap", {"clap", "claps", "clp"}),
    ("Hats", {"hat", "hats", "hh", "hihat", "hihats", "hhat"}),
    ("Cymbals", {"crash", "ride", "cym", "cymbal", "cymbals", "splash", "china", "oh", "overhead",
                 "overheads"}),
    ("Toms", {"tom", "toms", "floortom"}),
    ("Fills", {"fill", "fills", "roll", "rolls"}),
    ("Perc / loops", {"perc", "percs", "percussion", "conga", "congas", "bongo", "bongos", "shaker",
                      "shakers", "tamb", "tambo", "tambourine", "cowbell", "timbale", "timbales",
                      "clave", "claves", "guiro", "triangle", "block", "cabasa"}),
    ("Drum loops", {"loop", "loops", "groove", "grooves", "break", "breaks", "beat", "beats",
                    "breakbeat"}),
    ("Full drums", {"drum", "drums", "kit", "drm", "drms", "room", "rooms", "dr"}),
    ("FX", {"fx", "sfx", "efx", "riser", "risers", "rise", "sweep", "sweeps", "whoosh", "swoosh",
            "impact", "impacts", "noise", "uplifter", "downlifter", "downer", "laser", "lasers",
            "zap", "transition", "transitions", "reverse", "atmos", "atmosphere", "foley"}),
    ("Guitar", {"gtr", "gtrs", "guitar", "guitars", "gt", "acgtr", "elecgtr"}),
    ("Bass", {"bass", "sub", "subs", "808", "bs", "subbass"}),
    ("Keys", {"keys", "piano", "pno", "rhodes", "wurli", "wurlitzer", "epiano", "ep", "organ",
              "clav", "clavinet"}),
    ("Strings", {"strings", "string", "str", "violin", "violins", "viola", "cello", "cellos",
                 "orch", "orchestra"}),
    ("Brass", {"brass", "horn", "horns", "trumpet", "trumpets", "sax", "trombone", "tpt"}),
    ("Synth", {"synth", "synths", "syn", "juno", "moog", "prophet", "jupiter", "ob", "lead",
               "leads", "arp", "arps", "pluck", "plucks", "pad", "pads", "saw", "poly", "chord",
               "chords", "stab", "stabs", "serum", "massive", "sylenth", "nexus"}),
]


def kind_from_name(name: str):
    toks = [t.lower() for t in split_tokens(name)]
    joined = "".join(toks)
    for kind, words in HINTS:
        if any(t in words for t in toks):
            return kind
    # compound words such as "hihat", "kickdrum", "percloop"
    for kind, words in HINTS:
        for w in words:
            if len(w) >= 4 and w in joined:
                return kind
    return None


def kind_from_audio(an, onsets, label_counts: dict, tempo_conf: float, active_frac: float,
                    pitch: float, centroid: float) -> str:
    """Guess a stem kind from the sound itself (used when the file name gives no clue)."""
    n_hits = sum(label_counts.values())
    dur = an.n / an.sr
    rate = len(onsets) / max(dur * max(active_frac, 0.05), 1e-3)
    percussive = n_hits > 0 and rate > 0.8 and pitch < 0.55
    if percussive:
        top_label, top = max(label_counts.items(), key=lambda kv: kv[1])
        share = top / max(n_hits, 1)
        distinct = sum(1 for v in label_counts.values() if v >= 0.08 * n_hits)
        if share > 0.8:
            return {"Kick": "Kick", "Snare": "Snare", "Clap": "Clap", "Closed Hat": "Hats",
                    "Open Hat": "Hats", "Crash": "Cymbals", "Ride": "Cymbals", "Tom": "Toms",
                    "Shaker": "Perc / loops"}.get(top_label, "Perc / loops")
        if tempo_conf > 2.2 and active_frac > 0.3 and distinct >= 2:
            return "Full drums" if label_counts.get("Kick", 0) > 0.1 * n_hits else "Perc / loops"
        return "Mixed hits"
    if pitch > 0.45:
        return "Bass" if centroid < 300 else "Synth"
    return "FX"


# ------------------------------------------------------------- hit labeling
def drum_label(f: dict, context: str) -> str:
    c, lo, hi, flat, dec = f["centroid"], f["low"], f["high"], f["flat"], f["decay"]
    if context == "kick":
        return "Kick"
    if context == "snare":
        return "Clap" if f["bursts"] >= 3 and dec < 0.25 else "Snare"
    if context == "clap":
        return "Clap"
    if context == "toms":
        return "Tom"
    if context in ("hats", "cymbals"):
        if dec > 0.9:
            return "Crash" if flat > 0.2 or context == "cymbals" else "Ride"
        if context == "cymbals":
            return "Ride" if dec < 0.5 else "Crash"
        return "Open Hat" if dec > 0.16 else "Closed Hat"

    # generic drum rules
    if lo > 0.42 and c < 1500:
        label = "Kick"
    elif hi > 0.42 or c > 6500:
        if dec > 0.9:
            label = "Crash"
        elif dec > 0.16:
            label = "Open Hat"
        else:
            label = "Closed Hat"
    elif c > 1200 and flat > 0.08:
        label = "Clap" if f["bursts"] >= 3 and dec < 0.25 else "Snare"
    elif c < 1200 and lo + f["mid"] > 0.7 and flat < 0.12 and dec > 0.1:
        label = "Tom"
    else:
        label = "Perc"

    if context == "perc":
        return {"Closed Hat": "Shaker", "Open Hat": "Shaker", "Kick": "Perc", "Snare": "Perc",
                "Clap": "Clap", "Tom": "Perc", "Crash": "Perc"}.get(label, label)
    return label


def roll_label(context: str) -> str:
    return "Roll"


def loop_label(hit_labels: list[str], context: str, centroid: float) -> str:
    if context == "perc":
        return "Perc Loop"
    if any(l == "Kick" for l in hit_labels):
        return "Drum Loop"
    if centroid > 3000:
        return "Top Loop"
    return "Perc Loop" if context in ("perc", "fills") else "Drum Loop"


# ----------------------------------------------------------- event labeling
def fx_label(f: dict) -> str:
    dur, pp, flat, pitch, att = f["dur"], f["peak_pos"], f["flat"], f["pitch"], f["attack"]
    c0, c1, c2 = f["cent_parts"]
    if pp > 0.62 and dur > 0.8:
        return "Riser"
    if att < 0.03 and dur > 0.35 and f["centroid"] < 1800 and pp < 0.2:
        return "Impact"
    if pitch > 0.5 and dur < 1.6 and (max(c0, c2) > 1.6 * min(c0, c2) + 1):
        return "Laser"
    if pp < 0.35 and dur > 0.9 and c0 > 1.4 * c2:
        return "Downlifter"
    if flat > 0.12 and 0.2 <= pp <= 0.8 and 0.25 < dur < 3.5:
        return "Whoosh"
    if flat > 0.2 and dur > 1.0:
        return "Noise"
    return "FX"


def vocal_label(f: dict, fx_hint: bool) -> str:
    dur, pitch, flat = f["dur"], f["pitch"], f["flat"]
    processed = pitch < 0.3 or flat > 0.25
    if fx_hint and processed:
        return "Vocal FX"
    if dur < 0.9:
        return "Vocal Shout" if f["attack"] < 0.08 else "Vocal Chop"
    if dur < 2.6:
        return "Adlib"
    return "Vocal Phrase"


def melodic_label(f: dict, context: str) -> str:
    dur, poly = f["dur"], f["peaks"] >= 7
    short = dur < 0.7 and f["attack"] < 0.06
    if context == "guitar":
        if short:
            return "Guitar Stab"
        return "Guitar Chord" if poly else "Guitar Lead"
    if context == "bass":
        return "Bass"
    if context == "keys":
        return "Keys"
    if context == "strings":
        return "Strings"
    if context == "brass":
        return "Brass"
    if f["centroid"] < 260 and not poly:
        return "Bass"
    if short:
        return "Synth Stab"
    if dur > 1.6 and (poly or f["attack"] > 0.12):
        return "Pad"
    return "Synth Lead"


def summarize_spectrum(an) -> float:
    """Median spectral centroid of the loud parts of a stem."""
    from .dsp import stft_mag_chunks
    n_fft, hop = 2048, 4096
    freqs = np.fft.rfftfreq(n_fft, 1.0 / an.sr)
    cents, levels = [], []
    for _s, mag in stft_mag_chunks(an.m, n_fft, hop):
        p = mag ** 2
        tot = p.sum(axis=1)
        cents.append((p * freqs).sum(axis=1) / (tot + 1e-12))
        levels.append(tot)
    c = np.concatenate(cents)
    lv = np.concatenate(levels)
    if not len(lv) or lv.max() <= 0:
        return 0.0
    loud = lv > lv.max() * 1e-3
    return float(np.median(c[loud])) if loud.any() else 0.0
