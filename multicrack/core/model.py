"""Data model shared by the engine and the interface."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# ---------------------------------------------------------------- sample types

DRUM_LABELS = ["Kick", "Snare", "Clap", "Rim", "Closed Hat", "Open Hat", "Ride",
               "Crash", "Tom", "Shaker", "Tambourine", "Perc"]
LOOP_LABELS = ["Drum Loop", "Perc Loop", "Top Loop", "Fill", "Roll"]
FX_LABELS = ["Whoosh", "Riser", "Downlifter", "Impact", "Laser", "Noise", "FX"]
MELODIC_LABELS = ["Guitar Chord", "Guitar Lead", "Guitar Stab", "Synth Lead", "Synth Stab",
                  "Pad", "Keys", "Bass", "Strings", "Brass"]
VOCAL_LABELS = ["Vocal Shout", "Vocal Chop", "Vocal FX", "Adlib", "Vocal Phrase"]

LABEL_GROUPS = [("Drums", DRUM_LABELS), ("Loops", LOOP_LABELS), ("FX", FX_LABELS),
                ("Melodic", MELODIC_LABELS), ("Vocals", VOCAL_LABELS)]
ALL_LABELS = [l for _, g in LABEL_GROUPS for l in g]
LOOPED_LABELS = {"Drum Loop", "Perc Loop", "Top Loop"}

# ------------------------------------------------------------------ stem kinds
# kind name shown in the "AI detected" dropdown -> (engine, context)
STEM_KINDS = {
    "Kick": ("oneshot", "kick"),
    "Snare": ("oneshot", "snare"),
    "Clap": ("oneshot", "clap"),
    "Hats": ("oneshot", "hats"),
    "Cymbals": ("oneshot", "cymbals"),
    "Toms": ("oneshot", "toms"),
    "Mixed hits": ("oneshot", "mixed"),
    "Full drums": ("groove", "drums"),
    "Drum loops": ("groove", "drums"),
    "Perc / loops": ("groove", "perc"),
    "Fills": ("groove", "fills"),
    "FX": ("events", "fx"),
    "Vocals": ("events", "vocal"),
    "Guitar": ("events", "guitar"),
    "Synth": ("events", "synth"),
    "Bass": ("events", "bass"),
    "Keys": ("events", "keys"),
    "Strings": ("events", "strings"),
    "Brass": ("events", "brass"),
    "Melodic (other)": ("events", "melodic"),
}
KIND_NAMES = list(STEM_KINDS.keys())

_ids = itertools.count(1)


@dataclass
class Chop:
    stem_id: int
    start: int                  # sample index in the stem (inclusive)
    end: int                    # sample index in the stem (exclusive)
    label: str
    kind: str = "hit"           # hit | loop | roll | event | region
    bars: Optional[int] = None  # loop length in bars, for loop chops
    origin: str = "auto"        # auto | ai | manual
    flag: str = ""              # note shown on the review list
    cut_at_next: bool = False   # the tail was cut where the next sound starts
    approved: bool = False
    id: int = field(default_factory=lambda: next(_ids))

    @property
    def length(self) -> int:
        return max(0, self.end - self.start)


@dataclass
class Stem:
    path: str
    name: str                    # file name shown in the interface
    clean_name: str              # name with track numbers, key and L/R removed
    audio: np.ndarray            # float32, shape (frames, channels)
    sr: int
    kind: str = "Melodic (other)"
    mode: str = "auto"           # auto | manual
    status: str = "Ready"
    sources: list = field(default_factory=list)   # original file paths (2 for joined L/R)
    options: dict = field(default_factory=dict)   # per-stem engine options (loop dialog)
    analysis: dict = field(default_factory=dict)  # cached analysis (tempo, sections ...)
    id: int = field(default_factory=lambda: next(_ids))

    @property
    def frames(self) -> int:
        return int(self.audio.shape[0])

    @property
    def seconds(self) -> float:
        return self.frames / float(self.sr)

    @property
    def engine(self) -> str:
        return STEM_KINDS.get(self.kind, ("events", "melodic"))[0]

    @property
    def context(self) -> str:
        return STEM_KINDS.get(self.kind, ("events", "melodic"))[1]

    def mono(self) -> np.ndarray:
        if "mono" not in self.analysis:
            a = self.audio
            self.analysis["mono"] = (a.mean(axis=1) if a.ndim == 2 else a).astype(np.float32)
        return self.analysis["mono"]
