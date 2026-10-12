"""Aviso de versión nueva (GitHub Releases) y actualización de la app y de yt-dlp."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from importlib import metadata

from PySide6.QtCore import QObject, Signal, Slot

from i18n import tr


def _nums(version: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version.split("-")[0]))


def is_newer(candidate: str, current: str) -> bool:
    """¿`candidate` ("v1.2.0") es posterior a `current` ("1.1.0")?"""
    return _nums(candidate) > _nums(current)


@dataclass
class Release:
    tag: str
    url: str
    notes: str


def latest_release(repo: str, timeout: float = 8) -> Release | None:
    """Última Release publicada del repo, o None si no hay ninguna."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "yt-music-downloader"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:       # el repo aún no tiene ninguna Release
            return None
        raise
    return Release(tag=data["tag_name"], url=data["html_url"], notes=data.get("body") or "")


def ytdlp_version() -> str:
    try:
        return metadata.version("yt-dlp")
    except metadata.PackageNotFoundError:
        return "?"


def _pip_install(args: list[str], dry_run: bool = False):
    """pip install en el entorno de la app; si no hay pip (entornos de uv), usa `uv pip`."""
    cmds = [[sys.executable, "-m", "pip", "install"]]
    if shutil.which("uv"):
        cmds.append(["uv", "pip", "install", "--python", sys.executable])
    errors = []
    for base in cmds:
        cmd = base + (["--dry-run"] if dry_run else []) + args
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if p.returncode == 0:
            return
        errors.append(p.stderr.strip().splitlines()[-1] if p.stderr.strip()
                      else tr("exit code {code}", code=p.returncode))
    raise RuntimeError(errors[-1])


def update_ytdlp(dry_run: bool = False) -> tuple[str, str]:
    """Actualiza yt-dlp en el entorno de la app. Devuelve (versión anterior, versión nueva).
    Hay que reiniciar la app para que use la nueva."""
    before = ytdlp_version()
    _pip_install(["-U", "yt-dlp[default]"], dry_run)
    # el módulo ya cargado no cambia: se pregunta a un Python nuevo
    q = subprocess.run([sys.executable, "-c", "import importlib.metadata as m; print(m.version('yt-dlp'))"],
                       capture_output=True, text=True)
    return before, q.stdout.strip() or before


ROOT = os.path.dirname(os.path.abspath(__file__))


def is_git_checkout(root: str = ROOT) -> bool:
    return os.path.isdir(os.path.join(root, ".git")) and shutil.which("git") is not None


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=120)


def update_app(root: str = ROOT, dry_run: bool = False) -> tuple[str, str]:
    """Actualiza la app con `git pull` (solo avance limpio: no pisa cambios tuyos) y reinstala las
    dependencias si hay cambios. Devuelve (commit anterior, commit nuevo); reinicia para aplicarlo."""
    if not is_git_checkout(root):
        raise RuntimeError(tr("This copy wasn't installed with git, so it can't update itself."))
    old = _git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    p = _git(root, "pull", "--ff-only")
    if p.returncode != 0:
        lines = (p.stderr or p.stdout).strip().splitlines()
        raise RuntimeError(lines[-1] if lines else tr("git pull failed"))
    new = _git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    if new != old and os.path.isfile(os.path.join(root, "requirements.txt")):
        _pip_install(["-r", os.path.join(root, "requirements.txt")], dry_run)
    return old, new


class Task(QObject):
    """Ejecuta una función en un hilo y avisa con (resultado, error)."""

    done = Signal(object, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    @Slot()
    def run(self):
        try:
            self.done.emit(self.fn(), "")
        except Exception as e:  # noqa: BLE001 - se muestra en la interfaz
            self.done.emit(None, str(e) or type(e).__name__)
