"""Auto-update from the project's GitHub Releases (public project required)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from .. import __version__

REPO = "jehfslaps/multicrack"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSET = "Xenakis.exe"
LEGACY_ASSETS = ("MultiCrack.exe",)


def current_version() -> str:
    try:
        from .. import _build  # written by the build workflow
        return _build.BUILD
    except Exception:
        return __version__


def _tuple(v: str):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def check(timeout=8):
    """Return {'version', 'url', 'notes'} when a newer release exists, else None.
    Raises on network / access problems."""
    req = urllib.request.Request(API, headers={"User-Agent": "Xenakis-updater",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    tag = data.get("tag_name", "")
    assets = {a.get("name"): a.get("browser_download_url") for a in data.get("assets", [])}
    url = next((assets[n] for n in (ASSET, *LEGACY_ASSETS) if assets.get(n)), None)
    if not url:
        return None
    if _tuple(tag) > _tuple(current_version()):
        return {"version": tag.lstrip("v"), "url": url, "notes": data.get("body", "")}
    return None


def download(url, progress=None) -> str:
    dest_dir = os.path.join(tempfile.gettempdir(), "Xenakis", "update")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, ASSET)
    req = urllib.request.Request(url, headers={"User-Agent": "Xenakis-updater"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest + ".part", "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if progress:
                progress("Downloading update", got, max(total, got))
    if os.path.getsize(dest + ".part") < 1_000_000:
        raise IOError("The download looks incomplete.")
    os.replace(dest + ".part", dest)
    return dest


def install_and_restart(new_exe: str) -> None:
    """Swap the running .exe for the new one and start it. Windows lets a running program be
    renamed (not deleted), so the old one is moved aside and cleaned up on the next start."""
    exe = sys.executable
    old = exe + ".old"
    if os.path.exists(old):
        os.remove(old)
    os.replace(exe, old)
    try:
        os.replace(new_exe, exe)
    except Exception:
        os.replace(old, exe)   # put things back
        raise
    subprocess.Popen([exe], close_fds=True)


def cleanup_old() -> None:
    if is_frozen():
        old = sys.executable + ".old"
        try:
            if os.path.exists(old):
                os.remove(old)
        except OSError:
            pass
