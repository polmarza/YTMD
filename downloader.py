"""Descarga de YouTube Music con yt-dlp, pensada para un reproductor MP3 casero.

Nota sobre la calidad: YouTube Music sirve el audio ya comprimido (Opus ~130 kbps,
o AAC 256 kbps si usas cookies de una cuenta Premium). Convertir a FLAC/WAV no
recupera calidad, pero evita una segunda pérdida y da un formato fácil de decodificar.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import threading
from dataclasses import dataclass

import yt_dlp
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.postprocessor.metadataparser import MetadataParserPP
from yt_dlp.utils import sanitize_filename

import library
from browser_cookies import cookie_source

# nombre visible -> (códec para FFmpegExtractAudio, calidad)
FORMATS: dict[str, tuple[str, str]] = {
    "FLAC (sin pérdida)": ("flac", "0"),
    "WAV (PCM sin comprimir)": ("wav", "0"),
    "MP3 320 kbps": ("mp3", "320"),
    "Original (sin recodificar)": ("best", "0"),
}

BROWSERS = ["Ninguno", "chrome", "firefox", "brave", "edge"] + (["safari"] if sys.platform == "darwin" else [])

# Pausas para no parecer un bot: (mín, máx) segundos aleatorios antes de cada canción,
# y pausa entre peticiones de información.
PAUSES: dict[str, tuple[float, float, float]] = {
    "Sin pausa": (0, 0, 0),
    "Prudente (3–8 s)": (3, 8, 0.5),
    "Segura (10–20 s)": (10, 20, 1),
}

# YouTube rechaza al azar algunas descargas (HTTP 403); se reintentan solo las que fallan.
RETRY_PASSES = 2
RETRY_WAIT = 5

# Recorta la miniatura a cuadrado (YouTube suele dar 16:9 con bandas).
SQUARE_CROP = "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"

# Los álbumes de YT Music llegan como "Album - Nombre" (o "EP - …", "Single - …").
_ALBUM_PREFIX = re.compile(r"^(?:album|ep|single)\s*-\s*", re.I)
_TOPIC = re.compile(r"\s*-\s*Topic$")


class Cancelled(Exception):
    pass


# "(Official Video)", "[Official Music Video]", "(Lyric Video)", "(4K Remaster)", "(Audio)"…
_NOISE = re.compile(
    r"\s*[\(\[](?:official\b[^\)\]]*|[^\)\]]*\b(?:video|visualizer|lyrics?|audio)\b[^\)\]]*"
    r"|\d+k\s*remaster(?:ed)?|hd|4k)[\)\]]",
    re.I,
)


def clean_title(title: str, artist: str) -> str:
    """"Artista - Canción (Official Video)" -> "Canción"."""
    title = _NOISE.sub("", title or "").strip()
    if artist and title.lower().startswith(artist.lower() + " - "):
        title = title[len(artist) + 3:].strip()
    return title


def _artist_of(info: dict) -> str:
    return _TOPIC.sub("", info.get("artist") or info.get("uploader") or info.get("channel") or "")


class CleanTitlePP(PostProcessor):
    """Para vídeos sin metadatos de música: "Artista - Canción (Official Video)" -> track="Canción"."""

    def run(self, info):
        if not info.get("track"):
            title = clean_title(info.get("title"), info.get("artist") or info.get("uploader") or "")
            if title:
                info["track"] = title
        return [], info


@dataclass
class Options:
    out_dir: str
    format_name: str = "FLAC (sin pérdida)"
    browser: str = "Ninguno"
    pause: str = "Prudente (3–8 s)"
    compat_44k: bool = True       # 44.1 kHz / 16 bit: lo más compatible con DACs y decoders
    ascii_names: bool = False     # nombres seguros para librerías SD sin nombres largos
    cover_file: bool = True       # guardar también la portada como .jpg al lado
    skip_existing: bool = True


def _noop(*_a):
    pass


@dataclass
class Callbacks:
    log: callable = print
    info: callable = _noop        # (título, nº de pistas, tipo: single|album|playlist)
    item: callable = _noop        # (índice, total, nombre) de la pista actual
    progress: callable = _noop    # (% de la pista actual, texto)
    done_item: callable = _noop   # (ruta del fichero final)


@dataclass
class Result:
    cancelled: bool = False
    errors: int = 0
    done: int = 0
    folder: str = ""
    blocked: bool = False   # YouTube nos ha frenado (429 / "confirm you're not a bot")
    already: int = 0        # canciones que ya tenías (no se descargan otra vez)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def detect_kind(info: dict, url: str) -> str:
    if info.get("_type") != "playlist":
        return "single"
    if (info.get("id") or "").startswith("OLAK5uy_") or "browse/MPRE" in url:
        return "album"
    return "playlist"


class Downloader:
    def __init__(self, opts: Options, cb: Callbacks):
        self.opts = opts
        self.cb = cb
        self._cancel = threading.Event()
        self._total = 1
        self._index = 0
        self._current_id = None
        self._retrying = False
        self.result = Result()

    def cancel(self):
        self._cancel.set()

    # ---------- hooks de yt-dlp ----------
    def _progress_hook(self, d):
        if self._cancel.is_set():
            raise Cancelled()
        info = d.get("info_dict") or {}
        vid = info.get("id")
        if vid != self._current_id:
            self._current_id = vid
            self._index += 1
            name = _clean(f"{info.get('artist') or info.get('uploader') or ''} - "
                          f"{info.get('track') or info.get('title') or vid}").strip(" -")
            self.cb.item(self._index, self._total, name)
            self.cb.log(f"   origen: {info.get('acodec')} · {info.get('abr') or '?'} kbps"
                        f" · {info.get('format_note') or info.get('format_id')}")
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            got = d.get("downloaded_bytes") or 0
            pct = (got / total * 100) if total else 0
            speed = d.get("_speed_str", "").strip()
            self.cb.progress(pct, f"Descargando… {speed}")
        elif d["status"] == "finished":
            self.cb.progress(100, "Convirtiendo y etiquetando…")

    def _skipped(self, name):
        self._index += 1
        self.cb.item(self._index, self._total, name)
        if not self._retrying:  # en los reintentos, saltar lo ya bajado es lo esperado
            self.cb.log("↷ Ya descargada, se salta: " + name)

    def _pp_hook(self, d):
        if self._cancel.is_set():
            raise Cancelled()
        if d["status"] == "finished" and d["postprocessor"] == "MoveFiles":
            path = d["info_dict"].get("filepath")
            if path:
                self.result.done += 1
                vid = d["info_dict"].get("id")
                if vid:
                    library.add_to_index(self.opts.out_dir, {vid: os.path.relpath(path, self.opts.out_dir)})
                self.cb.done_item(path)
                self.cb.log(f"✔ {os.path.basename(path)}")

    def _on_error(self, msg):
        self.result.errors += 1
        if re.search(r"\b429\b|not a bot|rate.?limit", msg, re.I):
            self.result.blocked = True
        self.cb.log("✖ " + msg)

    def _logger(self):
        return _Logger(self.cb.log, self._on_error, self._skipped,
                       lambda secs: self.cb.progress(0, f"Pausa anti-bloqueo: {secs:.0f} s…"))

    # ---------- opciones ----------
    def _ydl_opts(self, dest: str, is_playlist: bool, width: int, archive: str) -> dict:
        o = self.opts
        codec, quality = FORMATS[o.format_name]

        name = "%(artist,uploader)s - %(track,title)s.%(ext)s"
        if is_playlist:
            # ancho fijo (01, 001…) para que el orden alfabético de la SD sea el de la lista
            name = f"%(playlist_index)0{width}d - " + name

        audio_args = []
        if o.compat_44k and codec != "best":
            audio_args += ["-ar", "44100"]
            if codec in ("flac", "wav"):
                audio_args += ["-sample_fmt", "s16"]

        pps = [
            {
                "key": "MetadataParser", "when": "pre_process",
                "actions": [
                    # "Artista - Topic" -> "Artista"
                    (MetadataParserPP.Actions.REPLACE, "uploader", _TOPIC.pattern, ""),
                    # nº de pista: el del álbum, o la posición en la playlist
                    (MetadataParserPP.Actions.INTERPRET, "%(track_number,playlist_index)s",
                     r"(?P<track_number>\d+)"),
                    # fuera descripción/URL del vídeo: engordan las etiquetas y no aportan
                    *[(MetadataParserPP.Actions.INTERPRET, "", f"(?P<meta_{k}>)")
                      for k in ("comment", "description", "synopsis", "purl")],
                ],
            },
            {"key": "FFmpegExtractAudio", "preferredcodec": codec, "preferredquality": quality},
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
        ]
        if codec != "wav":  # WAV no admite portada incrustada: queda como .jpg al lado
            pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": o.cover_file})

        sleep_min, sleep_max, sleep_req = PAUSES.get(o.pause, PAUSES["Prudente (3–8 s)"])
        ydl = {
            # 141 = AAC 256 kbps (solo con Premium); si no, el mejor audio disponible.
            "format": "141/bestaudio/best",
            "paths": {"home": dest},
            "outtmpl": {"default": name,
                        # miniatura de la propia playlist/álbum -> cover.jpg de la carpeta
                        "pl_thumbnail": "cover.%(ext)s"},
            "writethumbnail": True,
            "postprocessors": pps,
            "postprocessor_args": {
                "thumbnailsconvertor+ffmpeg_o": ["-c:v", "mjpeg", "-q:v", "2", "-vf", SQUARE_CROP],
                **({"extractaudio": audio_args} if audio_args else {}),
            },
            "windowsfilenames": True,          # sin : ? * " etc. (FAT32/exFAT)
            "restrictfilenames": o.ascii_names,
            "ignoreerrors": True,
            "noplaylist": not is_playlist,
            "retries": 10,
            "extractor_retries": 5,
            "js_runtimes": {"deno": {}, "node": {}},
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._pp_hook],
            "logger": self._logger(),
            "noprogress": True,
        }
        if sleep_max:
            ydl.update(sleep_interval=sleep_min, max_sleep_interval=sleep_max,
                       sleep_interval_requests=sleep_req)
        ydl["download_archive"] = archive
        if o.browser != "Ninguno":
            ydl["cookiesfrombrowser"] = cookie_source(o.browser)
        return ydl

    def _folder_name(self, info: dict, kind: str) -> tuple[str, str, str]:
        """(nombre de carpeta, título bonito, artista) de una playlist/álbum."""
        title = info.get("title") or "Playlist"
        artist = ""
        if kind == "album":
            title = _ALBUM_PREFIX.sub("", title)
            first = next((e for e in info.get("entries") or [] if e), {})
            artist = _TOPIC.sub("", first.get("artist") or first.get("uploader")
                                or first.get("channel") or "")
            folder = f"{artist} - {title}" if artist else title
        else:
            artist = _TOPIC.sub("", info.get("uploader") or info.get("channel") or "")
            folder = title
        folder = sanitize_filename(folder, restricted=self.opts.ascii_names).strip(" .") or "Playlist"
        return folder, title, artist

    # ---------- entrada ----------
    def run(self, url: str) -> Result:
        url = url.strip()
        os.makedirs(self.opts.out_dir, exist_ok=True)
        probe = {"extract_flat": "in_playlist", "quiet": True, "logger": self._logger(),
                 "js_runtimes": {"deno": {}, "node": {}}, "extractor_retries": 5,
                 "noplaylist": "list=" not in url or "v=" in url}
        if self.opts.browser != "Ninguno":
            probe["cookiesfrombrowser"] = cookie_source(self.opts.browser)

        self.cb.log(f"Analizando {url}")
        with yt_dlp.YoutubeDL(probe) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise RuntimeError("No se pudo leer el enlace (¿privado? prueba con cookies).")
        self.result.errors = 0  # los avisos del análisis no cuentan como canciones fallidas

        kind = detect_kind(info, url)
        dest = self.opts.out_dir
        # Con «Saltar ya descargadas» se compara con tu biblioteca: por id de vídeo y, si es
        # otro vídeo de la misma canción, por artista + título + duración.
        matcher = library.Matcher(self.opts.out_dir) if self.opts.skip_existing else None
        items = None    # nº de la lista que hay que descargar (None = todas)
        if kind == "single":
            self._total = 1
            title = info.get("track") or info.get("title") or url
            have = matcher and matcher.find(info.get("id"), _artist_of(info),
                                            clean_title(title, _artist_of(info)), info.get("duration"))
            if have:
                self.result.already = 1
                self.cb.info(title, 1, kind)
                self.cb.log(f"↷ Ya la tienes: {have}")
                return self.result
        else:
            entries = list(info.get("entries") or [])
            self._total = len([e for e in entries if e]) or 1
            folder, title, artist = self._folder_name(info, kind)
            dest = os.path.join(self.opts.out_dir, folder)
            os.makedirs(dest, exist_ok=True)
            # Se guarda junto a las canciones; si ya existía, se respeta lo que hayas cambiado.
            library.update_meta(dest, {
                "kind": kind, "title": title, "artist": artist, "url": url,
                "id": info.get("id"),
            }, overwrite=False)
            self.result.folder = dest
            label = "Álbum" if kind == "album" else "Lista"
            self.cb.log(f"{label} «{title}» · {self._total} canciones")
            if matcher:
                items = self._skip_known(entries, matcher, dest)
                if not items:
                    self.cb.info(title, self._total, kind)
                    self.cb.log("↷ Ya tenías todas las canciones: no hay nada que descargar.")
                    return self.result
        self.cb.info(title, self._total, kind)
        if items is not None:
            self._total = len(items)

        width = max(2, len(str(self._total)))
        # El registro de descargas permite reintentar solo lo que falló. Si no quieres
        # "saltar ya descargadas", se usa uno temporal que solo vale para esta descarga.
        tmp = None
        if self.opts.skip_existing:
            archive = os.path.join(self.opts.out_dir, ".descargadas.txt")
        else:
            fd, tmp = tempfile.mkstemp(prefix="ytmd-", suffix=".txt")
            os.close(fd)
            archive = tmp
        try:
            for attempt in range(RETRY_PASSES + 1):
                self._retrying = attempt > 0
                self._index, self._current_id = 0, None
                self.result.errors = 0
                opts = self._ydl_opts(dest, kind != "single", width, archive)
                if items is not None:
                    opts["playlist_items"] = ",".join(map(str, items))
                self._download(url, opts)
                r = self.result
                if r.cancelled or r.blocked or not r.errors or attempt == RETRY_PASSES:
                    break
                self.cb.log(f"↻ {r.errors} canción(es) fallaron (YouTube a veces responde 403). "
                            f"Reintento {attempt + 1}/{RETRY_PASSES} en {RETRY_WAIT} s…")
                self.cb.progress(0, f"Reintentando {r.errors} que fallaron…")
                if self._cancel.wait(RETRY_WAIT):
                    self.result.cancelled = True
                    break
        finally:
            if tmp:
                os.unlink(tmp)
        if self.result.cancelled:
            self.cb.log("Cancelado.")
        return self.result

    def _skip_known(self, entries: list, matcher: "library.Matcher", dest: str) -> list[int]:
        """Separa lo que ya tienes de lo que falta. Lo que ya tienes en otra carpeta queda
        enlazado a esta lista (sin copiar el archivo). Devuelve los nº de la lista a descargar."""
        todo, refs, learned = [], [], {}
        rel_dest = os.path.relpath(dest, self.opts.out_dir)
        for pos, e in enumerate(entries, 1):
            if not e:
                continue
            artist = _artist_of(e)
            have = matcher.find(e.get("id"), artist, clean_title(e.get("title"), artist), e.get("duration"))
            if not have:
                todo.append(pos)
                continue
            self.result.already += 1
            if e.get("id"):
                learned[e["id"]] = have     # la próxima vez se reconoce directamente por id
            if os.path.dirname(have) != rel_dest:
                refs.append({"pos": pos, "path": have})
        library.add_to_index(self.opts.out_dir, learned)
        if refs:
            library.add_refs(dest, refs)
        if self.result.already:
            self.cb.log(f"↷ {self.result.already} ya las tenías: no se descargan otra vez"
                        + (f" ({len(refs)} enlazadas desde otras carpetas)" if refs else ""))
        return todo

    def _download(self, url: str, ydl_opts: dict):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.add_post_processor(CleanTitlePP(ydl), when="pre_process")
                ydl.download([url])
        except Cancelled:
            self.result.cancelled = True
        except yt_dlp.utils.DownloadError as e:
            if not (self._cancel.is_set() or (e.exc_info and isinstance(e.exc_info[1], Cancelled))):
                raise
            self.result.cancelled = True


class _Logger:
    def __init__(self, log, on_error, on_skip=None, on_sleep=None):
        self.log = log
        self.on_error = on_error
        self.on_skip = on_skip
        self.on_sleep = on_sleep

    def debug(self, msg):
        if not msg.startswith("[download] "):
            return
        if self.on_skip and "has already been recorded" in msg:
            self.on_skip(msg[len("[download] "):].split(" has already")[0])
        elif self.on_sleep and msg.startswith("[download] Sleeping "):
            m = re.search(r"Sleeping ([\d.]+)", msg)
            if m:
                self.on_sleep(float(m.group(1)))

    def info(self, msg):
        pass

    def warning(self, msg):
        if "Cancelled" not in msg:
            self.log("⚠ " + msg)

    def error(self, msg):
        if "Cancelled" not in msg:
            self.on_error(msg)
