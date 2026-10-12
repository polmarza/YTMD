"""Le dice a yt-dlp dónde están las cookies del navegador sin que tenga que buscarlas.

yt-dlp localiza la base de datos de cookies de Chrome recorriendo toda la carpeta del
perfil (cachés incluidas, varios GB). Si está en un disco externo puede tardar minutos, y se
repite en cada descarga. En macOS se copia el archivo de cookies (~1 MB) a una carpeta
temporal privada que solo lo contiene a él, y se le pasa esa carpeta a yt-dlp como perfil.
"""
from __future__ import annotations

import atexit
import glob
import os
import shutil
import sys
import tempfile

CHROMIUM = {"chrome", "chromium", "brave", "edge", "opera", "vivaldi", "whale"}
_tmpdir: str | None = None


def _private_dir() -> str:
    global _tmpdir
    if _tmpdir is None:
        _tmpdir = tempfile.mkdtemp(prefix="ytmd-cookies-")     # permisos 700: solo tu usuario
        atexit.register(shutil.rmtree, _tmpdir, True)
    return _tmpdir


def cookie_source(browser: str) -> tuple:
    """Valor para la opción `cookiesfrombrowser` de yt-dlp: (navegador,) o (navegador, perfil)."""
    # En Windows/Linux yt-dlp necesita además otros archivos del navegador: mejor no tocar.
    if sys.platform != "darwin" or browser not in CHROMIUM:
        return (browser,)
    try:
        from yt_dlp.cookies import _get_chromium_based_browser_settings
        base = _get_chromium_based_browser_settings(browser)["browser_dir"]
    except Exception:
        return (browser,)
    found = glob.glob(os.path.join(base, "*", "Network", "Cookies")) + \
        glob.glob(os.path.join(base, "*", "Cookies"))
    if not found:
        return (browser,)
    newest = max(found, key=os.path.getmtime)       # el perfil que estás usando
    folder = _private_dir()
    # copia nueva en cada uso (así nunca se queda vieja) y sin dejarla a medias
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".copy-")
    os.close(fd)
    shutil.copy2(newest, tmp)
    os.replace(tmp, os.path.join(folder, "Cookies"))
    return (browser, folder)
