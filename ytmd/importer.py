"""Lee tu biblioteca de YouTube Music (listas, "Música que me gusta" y álbumes guardados).

Usa la sesión del navegador elegido en «Cookies» (la misma que las descargas) y la librería
no oficial ytmusicapi. Solo lee: no cambia nada de tu cuenta.
"""
from __future__ import annotations

from dataclasses import dataclass

from yt_dlp.cookies import extract_cookies_from_browser
from ytmusicapi import YTMusic

from ytmd.browser_cookies import cookie_source
from ytmd.i18n import tr

ORIGIN = "https://music.youtube.com"
SKIP_PREFIXES = ("SE", "RDPN")     # pódcasts: "Episodios para más tarde", "Nuevos episodios"
# Ni yt-dlp ni ytmusicapi pueden leer hoy estas listas automáticas: Recaps (LR…),
# listas de YouTube Music (RDCLAK…, RDTMAK…) y mixes (RD…).
UNSUPPORTED_PREFIXES = ("LR", "RD")


@dataclass
class RemoteItem:
    kind: str           # playlist | album
    id: str             # id de la lista (PL…, LM, OLAK5uy_…) o del álbum (MPREb_…)
    title: str
    subtitle: str       # autor / artista • año
    count: int | None   # nº de canciones, si YouTube lo da
    url: str
    alt_ids: tuple = ()  # otros ids que identifican lo mismo (el OLAK5uy_ de un álbum)

    @property
    def supported(self) -> bool:
        return self.id == "LM" or not self.id.startswith(UNSUPPORTED_PREFIXES)


def _client(browser: str) -> YTMusic:
    jar = extract_cookies_from_browser(*cookie_source(browser))
    cookies = {c.name: c.value for c in jar if c.domain.endswith("youtube.com")}
    if "__Secure-3PAPISID" not in cookies:
        raise RuntimeError(tr("There is no YouTube session signed in on {browser}. "
                              "Sign in at music.youtube.com with your account and try again.", browser=browser))
    headers = {
        "cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        # ytmusicapi reconoce la sesión de navegador por esta cabecera y la recalcula en cada petición
        "authorization": "SAPISIDHASH 0",
        "origin": ORIGIN,
        "x-origin": ORIGIN,
        "x-goog-authuser": "0",
    }
    return YTMusic(auth=headers, language="es")


def _count(value) -> int | None:
    try:
        return int(str(value).split()[0].replace(".", "").replace(",", ""))
    except (TypeError, ValueError, IndexError):
        return None


def fetch_library(browser: str) -> list[RemoteItem]:
    yt = _client(browser)
    items: list[RemoteItem] = []

    for p in yt.get_library_playlists(limit=None):
        pid = p.get("playlistId") or ""
        if not pid or pid.startswith(SKIP_PREFIXES):
            continue
        authors = ", ".join(a["name"] for a in p.get("author") or [] if a.get("name"))
        items.append(RemoteItem(
            kind="playlist", id=pid, title=p.get("title") or pid,
            subtitle=authors or (tr("Automatic playlist") if pid == "LM" else ""),
            count=_count(p.get("count")),
            url=f"{ORIGIN}/playlist?list={pid}"))

    for a in yt.get_library_albums(limit=None):
        bid = a.get("browseId") or ""
        if not bid:
            continue
        artists = ", ".join(x["name"] for x in a.get("artists") or [] if x.get("name"))
        sub = " • ".join(x for x in (a.get("type"), artists, a.get("year")) if x)
        items.append(RemoteItem(
            kind="album", id=bid, title=a.get("title") or bid, subtitle=sub, count=None,
            url=f"{ORIGIN}/browse/{bid}",
            alt_ids=tuple(x for x in (a.get("playlistId"), a.get("audioPlaylistId")) if x)))
    return items
