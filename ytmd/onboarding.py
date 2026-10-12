"""Primer arranque: canción de ejemplo y comprobación de lo que la app necesita del sistema."""
from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

from ytmd.i18n import tr

# Canción de ejemplo con licencia libre: «Carefree», de Kevin MacLeod, publicada por el propio autor
# en YouTube con licencia Creative Commons Attribution (CC BY 4.0): se puede descargar y compartir
# citando al autor.
SAMPLE_URL = "https://music.youtube.com/watch?v=sMcWOaJFuw0"
SAMPLE_CREDIT = "“Carefree” by Kevin MacLeod (incompetech.com) · CC BY 4.0"


@dataclass
class MissingTool:
    name: str
    why: str
    command: str        # cómo instalarlo en este sistema


def _install(mac: str, win: str, linux: str) -> str:
    return {"darwin": mac, "win32": win}.get(sys.platform, linux)


def missing_tools() -> list[MissingTool]:
    """Programas externos que faltan: sin ellos las descargas fallan."""
    out = []
    if not shutil.which("ffmpeg"):
        out.append(MissingTool("ffmpeg", tr("needed to convert the audio and add cover art"),
                               _install("brew install ffmpeg", "winget install Gyan.FFmpeg",
                                        "sudo apt install ffmpeg")))
    if not (shutil.which("node") or shutil.which("deno")):
        out.append(MissingTool("Node.js", tr("needed by yt-dlp to read YouTube"),
                               _install("brew install node", "winget install OpenJS.NodeJS",
                                        "sudo apt install nodejs")))
    return out
