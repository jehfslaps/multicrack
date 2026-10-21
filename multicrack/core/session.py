"""Saving and reopening a Xenakis session (song info, stems, every chop and its edits)."""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, fields

from .audio import load_stems
from .model import Chop

EXT = ".xenakis"
OPEN_EXTS = (EXT, ".multicrack")  # sessions saved before the rename still open
APPS = ("Xenakis", "MultiCrack")
CHOP_FIELDS = [f.name for f in fields(Chop) if f.name not in ("id", "stem_id")]


def to_dict(meta: dict, stems, chops, queue=None, finished=False) -> dict:
    index = {s.id: i for i, s in enumerate(stems)}
    return {
        "app": "Xenakis", "version": 1, "saved": time.time(), "finished": bool(finished),
        "meta": meta,
        "stems": [{"sources": list(s.sources or [s.path]), "kind": s.kind, "mode": s.mode,
                   "options": s.options, "status": s.status} for s in stems],
        "chops": [dict({k: v for k, v in asdict(c).items() if k in CHOP_FIELDS},
                       stem=index[c.stem_id]) for c in chops if c.stem_id in index],
        "queue": queue or [],
    }


def save(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, default=_jsonable)
    os.replace(tmp, path)


def _jsonable(o):
    try:
        import numpy as np
        if isinstance(o, np.generic):
            return o.item()
    except Exception:
        pass
    return str(o)


def read(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("app") not in APPS:
        raise ValueError("This isn't a Xenakis session file.")
    return data


def restore(data: dict, progress=None):
    """Reload the audio and rebuild stems and chops. Returns (stems, chops, missing_files)."""
    stems, missing, by_index = [], [], {}
    specs = data.get("stems", [])
    for i, spec in enumerate(specs):
        srcs = [p for p in spec.get("sources", []) if os.path.isfile(p)]
        if progress:
            progress(f"Reloading {os.path.basename(spec['sources'][0]) if spec.get('sources') else ''}",
                     i, len(specs))
        if len(srcs) != len(spec.get("sources", [])) or not srcs:
            missing.extend(p for p in spec.get("sources", []) if not os.path.isfile(p))
            continue
        loaded = load_stems(srcs)
        if not loaded:
            missing.extend(srcs)
            continue
        st = loaded[0]
        st.kind = spec.get("kind", st.kind)
        st.mode = spec.get("mode", "auto")
        st.options = spec.get("options") or {}
        st.status = spec.get("status", "Ready")
        stems.append(st)
        by_index[i] = st
    chops = []
    for cd in data.get("chops", []):
        st = by_index.get(cd.get("stem"))
        if st is None:
            continue
        kw = {k: cd[k] for k in CHOP_FIELDS if k in cd}
        chops.append(Chop(stem_id=st.id, **kw))
    return stems, chops, missing


def describe(data: dict) -> str:
    m = data.get("meta", {})
    name = " - ".join(p for p in (m.get("artist", ""), m.get("song", "")) if p) or "Untitled"
    n = len(data.get("chops", []))
    a = sum(1 for c in data.get("chops", []) if c.get("approved"))
    when = time.strftime("%b %d, %I:%M %p", time.localtime(data.get("saved", time.time())))
    return f"{name}: {a} of {n} chops approved (saved {when})"
