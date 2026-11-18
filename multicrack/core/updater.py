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
ASSET = "Xenakis.exe"                 # the app on its own (portable copies swap themselves)
INSTALLER_ASSET = "Install-Xenakis.exe"   # installed copies update by running the new installer
LEGACY_ASSETS = ("MultiCrack.exe",)
UNINSTALLER = "Uninstall Xenakis.exe"


def current_version() -> str:
    try:
        from .. import _build  # written by the build workflow
        return _build.BUILD
    except Exception:
        return __version__


def display_version() -> str:
    """The public version ("1.0"). Build numbers stay internal (they only order updates)."""
    try:
        from .. import _build
        return _build.DISPLAY
    except Exception:
        pass
    try:
        here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(here, "VERSION"), encoding="utf-8") as f:
            return f.read().strip() or "1.0"
    except OSError:
        return "1.0"


def is_installed() -> bool:
    """Installed by Install Xenakis.exe (Program Files), rather than a loose .exe."""
    return is_frozen() and os.path.exists(os.path.join(os.path.dirname(sys.executable), UNINSTALLER))


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
    order = (INSTALLER_ASSET, ASSET, *LEGACY_ASSETS) if is_installed() else (ASSET, *LEGACY_ASSETS)
    name = next((n for n in order if assets.get(n)), None)
    if not name:
        return None
    if _tuple(tag) > _tuple(current_version()):
        return {"version": tag.lstrip("v"), "url": assets[name], "notes": data.get("body", ""),
                "installer": name == INSTALLER_ASSET}
    return None


def download(url, progress=None, installer=False) -> str:
    dest_dir = os.path.join(tempfile.gettempdir(), "Xenakis", "update")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, INSTALLER_ASSET if installer else ASSET)
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


def run_installer(path: str) -> None:
    """Start the new installer (Windows asks for permission); the app then quits so its files
    can be replaced. The installer offers to open Xenakis again when it's done."""
    os.startfile(path)  # type: ignore[attr-defined]   (Windows only)


def cleanup_old() -> None:
    if is_frozen():
        old = sys.executable + ".old"
        try:
            if os.path.exists(old):
                os.remove(old)
        except OSError:
            pass
