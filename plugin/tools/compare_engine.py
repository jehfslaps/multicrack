"""Print what the Python engine finds, in the same format as xk_engine_cli.

    python plugin/tools/compare_engine.py <folder> [--ai]

Without --ai the trained model is switched off, which is how the plug-in's first stage works,
so the two outputs can be compared line by line.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from multicrack.core import ai, audio, pipeline  # noqa: E402

if "--ai" not in sys.argv:
    ai._get = lambda: None
    ai.available = lambda: False
    ai.best_kind = lambda *a, **k: None
    ai.tags = lambda *a, **k: []
    ai.fx_label = lambda tg: None
    ai.hit_label = lambda tg: None
    ai.vocal_label = lambda tg, label: label

paths = [a for a in sys.argv[1:] if not a.startswith("--")]
t0 = time.time()
stems = audio.load_stems(paths)
for st in stems:
    if st.mode != "skip":
        st.kind = pipeline.detect_kind(st)
        st.status = "Ready"
chops, song = pipeline.process(stems)
t1 = time.time()
print(f"SONG bpm={song['bpm'] if song else 0:.2f} downbeat={song['downbeat'] if song else 0}")
for st in stems:
    print(f"STEM {st.name} | kind={st.kind} | sr={st.sr} ch={st.audio.shape[1]} frames={st.frames} | {st.status}")
    for c in chops:
        if c.stem_id == st.id:
            print(f"  {c.kind:<6} {c.label:<12} {c.start:9d} {c.end:9d} bars={c.bars or 0} {c.flag}")
print(f"TOTAL {len(chops)} chops in {t1 - t0:.1f} s")
