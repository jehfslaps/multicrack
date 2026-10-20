"""Developer check: run a folder of stems through the engine and print what it finds.
Usage: python tools/run_stems.py <folder-or-files...> [--export OUTDIR]"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multicrack.core import audio, pipeline  # noqa: E402
from multicrack.core.naming import assign_names, make_prefix  # noqa: E402


def main():
    args = sys.argv[1:]
    out = None
    if "--export" in args:
        i = args.index("--export")
        out = args[i + 1]
        args = args[:i] + args[i + 2:]
    t = time.time()
    stems = audio.load_stems(args)
    print(f"loaded {len(stems)} stems in {time.time() - t:.1f}s")
    for st in stems:
        t = time.time()
        st.kind = pipeline.detect_kind(st)
        print(f"  {st.name:40s} -> {st.kind:14s} ({st.clean_name}) {time.time() - t:.1f}s")
    t = time.time()
    chops, song = pipeline.process(stems)
    print(f"song: {song and {k: song[k] for k in ('bpm', 'downbeat')}}  chopped in {time.time() - t:.1f}s")
    by = {s.id: s for s in stems}
    names = assign_names(chops, make_prefix("Test Artist", "Demo"))
    for st in stems:
        sec = st.analysis.get("sections")
        print(f"\n== {st.name} [{st.kind}] {st.status}")
        if sec:
            print(f"   bpm {sec['bpm']}  grooves: " + "; ".join(
                f"{g['name']} {g['where']} -> {g['bars']}bar {g['label']} ({g['hits']} hits)"
                for g in sec["grooves"]) + f" | rolls {sec.get('rolls')} kept {sec.get('rolls_kept')} | single hits {sec['hits']}")
        for c in chops:
            if c.stem_id == st.id:
                print(f"   {names[c.id]:34s} {c.start / st.sr:7.2f}s  {c.length / st.sr:6.3f}s  {c.flag}")
    if out:
        written = pipeline.export(by, chops, out, make_prefix("Test Artist", "Demo"))
        print(f"\nwrote {len(written)} files to {out}")


if __name__ == "__main__":
    main()
