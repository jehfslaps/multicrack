"""Working out when a drop contains several songs (for the song queue)."""
from __future__ import annotations

import os
import re

from .audio import is_audio

_JUNK = re.compile(r"[\[(][^\])]*[\])]|\b(stems?|multi ?tracks?|multitrack|tracks|bounces?|"
                   r"exports?|session|wavs?|files)\b", re.IGNORECASE)


def _has_audio_directly(folder: str) -> bool:
    try:
        return any(is_audio(f) for f in os.listdir(folder)
                   if os.path.isfile(os.path.join(folder, f)))
    except OSError:
        return False


def _has_audio(folder: str) -> bool:
    for _root, _dirs, files in os.walk(folder):
        if any(is_audio(f) for f in files):
            return True
    return False


def split_songs(paths) -> list[str]:
    """Return a list of song folders when the drop holds more than one song, else []."""
    folders = [p for p in paths if os.path.isdir(p)]
    loose = [p for p in paths if os.path.isfile(p)]
    if loose:
        return []
    if len(folders) >= 2 and all(_has_audio(f) for f in folders):
        return sorted(folders, key=str.lower)
    if len(folders) == 1 and not _has_audio_directly(folders[0]):
        subs = sorted((os.path.join(folders[0], d) for d in os.listdir(folders[0])
                       if os.path.isdir(os.path.join(folders[0], d))), key=str.lower)
        songs = [s for s in subs if _has_audio(s)]
        if len(songs) >= 2:
            return songs
    return []


def guess_names(folder: str) -> tuple[str, str]:
    """'Taylor Swift - Style (Stems)' -> ('Taylor Swift', 'Style')."""
    name = os.path.basename(os.path.normpath(folder))
    name = _JUNK.sub(" ", name.replace("_", " "))
    name = re.sub(r"\s+", " ", name).strip(" -–—.")
    for sep in (" - ", " – ", " — ", " -", "- "):
        if sep in name:
            a, b = name.split(sep, 1)
            return a.strip(" -–—"), b.strip(" -–—")
    return "", name
