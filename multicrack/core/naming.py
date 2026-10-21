"""File, folder and stem naming."""
from __future__ import annotations

import os
import re

from .model import LOOPED_LABELS

_INVALID = r'[<>:"/\\|?*\x00-\x1f]'

TOKEN_OVERRIDES = {
    "Vocal Shout": "VoxShout", "Vocal Chop": "VoxChop", "Vocal FX": "VoxFX",
    "Vocal Phrase": "VoxPhrase", "Guitar Chord": "GtrChord", "Guitar Lead": "GtrLead",
    "Guitar Stab": "GtrStab",
}


def _clean_words(text: str) -> list[str]:
    return [w for w in re.split(r"[^0-9A-Za-z]+", text or "") if w]


def make_prefix(artist: str, song: str) -> str:
    """'Taylor Swift', 'Style' -> 'TS_Style_'."""
    initials = "".join(w[0].upper() for w in _clean_words(artist))
    words = _clean_words(song)
    song_part = "".join(w[:1].upper() + w[1:] for w in words)[:28]
    parts = [p for p in (initials, song_part) if p]
    return ("_".join(parts) + "_") if parts else ""


def folder_name(artist: str, song: str) -> str:
    artist = re.sub(_INVALID, "", (artist or "").strip())
    song = re.sub(_INVALID, "", (song or "").strip())
    base = " - ".join(p for p in (artist, song) if p) or "Untitled"
    return f"{base} (Chopped)".rstrip(". ")


def label_token(label: str) -> str:
    if label in TOKEN_OVERRIDES:
        return TOKEN_OVERRIDES[label]
    return "".join(w[:1].upper() + w[1:] for w in _clean_words(label)) or "Sample"


def chop_key(label: str, bars, reverse: bool = False) -> str:
    tok = label_token(label)
    if reverse:
        tok += "Rev"
    if label in LOOPED_LABELS and bars:
        tok += f"_{int(bars)}bar"
    return tok


def existing_counts(folder: str, prefix: str) -> dict:
    """Highest number already used per key in the output folder."""
    counts: dict = {}
    if not folder or not os.path.isdir(folder):
        return counts
    pat = re.compile(re.escape(prefix) + r"(.+)_(\d+)\.wav$", re.IGNORECASE)
    for f in os.listdir(folder):
        m = pat.match(f)
        if m:
            k = m.group(1)
            counts[k] = max(counts.get(k, 0), int(m.group(2)))
    return counts


def assign_names(chops, prefix: str, folder: str = "") -> dict:
    """Return {chop.id: filename}; numbering continues after files already in the folder."""
    counts = existing_counts(folder, prefix)
    names = {}
    for c in chops:
        k = chop_key(c.label, c.bars, getattr(c, "reverse", False))
        counts[k] = counts.get(k, 0) + 1
        names[c.id] = f"{prefix}{k}_{counts[k]:02d}.wav"
    return names


# ------------------------------------------------------------- stem file names
_KEY_RE = re.compile(r"^[A-Ga-g](#|b|s)?(m|min|maj|minor|major|M)?$")
_CH_RE = re.compile(r"^(l|r|left|right|lt|rt)$", re.IGNORECASE)
_NOISE = {"stem", "stems", "st", "bounce", "export", "print", "final", "mix", "wav"}


def split_tokens(name: str) -> list[str]:
    base = os.path.splitext(os.path.basename(name))[0]
    raw = re.split(r"[^0-9A-Za-z#]+", base)
    out = []
    for r in raw:
        if not r:
            continue
        # split camelCase and letter/digit boundaries
        out.extend(t for t in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z#]+|\d+", r) if t)
    return out


def clean_stem_name(name: str) -> str:
    """'_042_Juno_1_Cm_R.wav' -> 'Juno 1'."""
    base = os.path.splitext(os.path.basename(name))[0]
    parts = [p for p in re.split(r"[\s_\-.]+", base) if p]
    while parts and parts[0].isdigit():
        parts.pop(0)
    while parts and (_CH_RE.match(parts[-1]) or _KEY_RE.match(parts[-1])
                     or parts[-1].lower() in _NOISE):
        parts.pop()
    parts = [p for p in parts if p.lower() not in _NOISE]
    return " ".join(parts) or base


def channel_side(name: str):
    """Return ('base', 'L'|'R') for split-mono files, else None."""
    base = os.path.splitext(os.path.basename(name))[0]
    m = re.match(r"^(.*?)[\s_\-.]+(L|R|Left|Right|Lt|Rt)$", base, re.IGNORECASE)
    if not m:
        return None
    side = m.group(2)[0].upper()
    return m.group(1).lower(), side
