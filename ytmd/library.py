"""Biblioteca: colecciones (álbumes / listas / sueltas), etiquetas y portadas.

Cada subcarpeta de la carpeta de música es una colección. Su tipo y datos se guardan en
un `.coleccion.json` dentro de la propia carpeta, así viajan con las canciones.
Las canciones que están directamente en la raíz forman la colección "Canciones sueltas".

Sin duplicados: si una lista incluye una canción que ya tienes en otra carpeta, no se vuelve
a descargar; la lista guarda una referencia ("refs" en su .coleccion.json) a ese archivo.
"""
from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3
from mutagen.mp4 import MP4

from ytmd.i18n import tr, trn

AUDIO_EXT = {".flac", ".wav", ".mp3", ".m4a", ".opus", ".ogg", ".aac"}
META_FILE = ".coleccion.json"
CACHE_FILE = ".biblioteca-cache.json"
INDEX_FILE = ".indice.json"         # id de vídeo de YouTube -> archivo (ruta relativa a la raíz)


def kind_label(kind: str) -> str:
    return {"album": tr("Album"), "playlist": tr("Playlist"), "singles": tr("Loose"),
            "all": tr("Library")}.get(kind, kind)


# Grupos con coma en el nombre: no se pueden partir por ", " sin romperlos.
_COMMA_NAMES = ("Tyler, The Creator", "Earth, Wind & Fire", "Crosby, Stills, Nash & Young",
                "Emerson, Lake & Palmer", "Blood, Sweat & Tears", "Peter, Paul and Mary")


def main_artist(artist: str, hint: str = "") -> str:
    """Artista principal de "A, B, C" (YouTube mete todos los créditos en la etiqueta).
    `hint` = artista del álbum, si se conoce: es la pista más fiable."""
    if not artist:
        return ""
    if hint and (artist == hint or artist.startswith(hint + ", ")):
        return hint
    for name in _COMMA_NAMES:
        if artist == name or artist.startswith(name + ", "):
            return name
    return artist.split(", ")[0]


@dataclass
class Track:
    path: str
    title: str
    artist: str
    album: str
    duration: float
    ext: str
    year: str = ""
    ref: bool = False   # vive en otra carpeta; esta lista solo la referencia
    collection: "Collection | None" = field(default=None, repr=False, compare=False)

    @property
    def main_artist(self) -> str:
        """Solo el artista principal, para mostrar (la etiqueta guarda todos los créditos)."""
        hint = self.collection.artist if self.collection and self.collection.kind == "album" else ""
        return main_artist(self.artist, hint)

    @property
    def subtitle(self) -> str:
        return " • ".join(x for x in (self.main_artist, self.album) if x)


@dataclass
class Collection:
    id: str           # carpeta relativa a la raíz ("" = canciones sueltas)
    path: str
    title: str
    kind: str         # album | playlist | singles
    artist: str = ""
    year: str = ""
    url: str = ""
    source: str = ""  # id de la lista/álbum en YouTube (para reconocerla al importar)
    tracks: list[Track] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return sum(t.duration for t in self.tracks)

    @property
    def kind_label(self) -> str:
        return kind_label(self.kind)

    @property
    def subtitle(self) -> str:
        if self.kind == "album":
            parts = [self.kind_label, self.artist, self.year]
        else:
            parts = [self.kind_label, trn(len(self.tracks), "{n} song", "{n} songs")]
        return " • ".join(p for p in parts if p)


def write_json(path: str, data, indent: int | None = None):
    """Escribe a un temporal y lo renombra: nunca deja un JSON a medias."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ------------------------------------------------------------------ metadatos de colección
def read_meta(folder: str) -> dict:
    try:
        with open(os.path.join(folder, META_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def update_meta(folder: str, data: dict, overwrite: bool = True) -> dict:
    """Mezcla `data` en el .coleccion.json. Con overwrite=False solo rellena lo que falte."""
    meta = read_meta(folder)
    for k, v in data.items():
        if v is None:
            continue
        if overwrite or not meta.get(k):
            meta[k] = v
    os.makedirs(folder, exist_ok=True)
    write_json(os.path.join(folder, META_FILE), meta, indent=2)
    return meta


def add_refs(folder: str, refs: list[dict]):
    """Añade referencias {"pos": nº en la lista, "path": ruta relativa a la raíz} sin repetir."""
    meta = read_meta(folder)
    have = {(r["pos"], r["path"]) for r in meta.get("refs", [])}
    meta["refs"] = meta.get("refs", []) + [r for r in refs if (r["pos"], r["path"]) not in have]
    write_json(os.path.join(folder, META_FILE), meta, indent=2)


# ------------------------------------------------------------------ índice de vídeos
def load_index(root: str) -> dict:
    try:
        with open(os.path.join(root, INDEX_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def add_to_index(root: str, entries: dict):
    if entries:
        index = load_index(root)
        index.update(entries)
        write_json(os.path.join(root, INDEX_FILE), index)


# ------------------------------------------------------------------ etiquetas
def _first(tags, *keys) -> str:
    for k in keys:
        try:
            v = tags[k]
        except Exception:
            continue
        v = getattr(v, "text", v)  # los frames ID3 guardan el valor en .text
        if isinstance(v, list):
            v = v[0] if v else ""
        if v:
            return str(v)
    return ""


def read_track(path: str) -> Track:
    stem, ext = os.path.splitext(os.path.basename(path))
    title = artist = album = year = ""
    duration = 0.0
    try:
        f = mutagen.File(path, easy=True)
        if f is not None:
            duration = getattr(f.info, "length", 0.0) or 0.0
            title = _first(f.tags, "title")
            artist = _first(f.tags, "artist")
            album = _first(f.tags, "album")
            year = _first(f.tags, "date")[:4]
        if ext.lower() == ".wav" and not title:
            raw = mutagen.File(path)  # WAV guarda ID3 o INFO; probamos ID3
            tags = getattr(raw, "tags", None)
            title = _first(tags, "TIT2")
            artist = _first(tags, "TPE1")
    except Exception:
        pass
    if not title:  # sacamos lo que se pueda del nombre "NN - Artista - Título"
        parts = [p.strip() for p in stem.split(" - ")]
        if len(parts) >= 2 and parts[0].isdigit():
            parts = parts[1:]
        if len(parts) >= 2:
            artist = artist or parts[0]
            title = " - ".join(parts[1:])
        else:
            title = stem
    return Track(path, title, artist, album, duration, ext.lstrip(".").upper(), year)


class _TagCache:
    """Evita releer las etiquetas de ficheros que no han cambiado (mtime + tamaño)."""

    FIELDS = ("title", "artist", "album", "duration", "ext", "year")

    def __init__(self, root: str):
        self.file = os.path.join(root, CACHE_FILE)
        try:
            with open(self.file, encoding="utf-8") as f:
                self.old = json.load(f)
        except (OSError, ValueError):
            self.old = {}
        self.new: dict = {}

    def get(self, path: str, rel: str) -> Track:
        st = os.stat(path)
        sig = [st.st_mtime, st.st_size]
        hit = self.old.get(rel)
        if hit and hit[0] == sig:
            t = Track(path, *hit[1])
        else:
            t = read_track(path)
        self.new[rel] = [sig, [getattr(t, k) for k in self.FIELDS]]
        return t

    def save(self):
        if self.new != self.old:
            try:
                write_json(self.file, self.new)
            except OSError:
                pass


# ------------------------------------------------------------------ escaneo
def _natural(name: str):
    """Ordena "2 - …" antes que "10 - …" (descargas antiguas con 2 cifras en listas largas)."""
    m = re.match(r"\s*(\d+)", name)
    return (int(m.group(1)) if m else float("inf"), name.lower())


def _guess_kind(folder_name: str, tracks: list[Track]) -> str:
    albums = {t.album for t in tracks if t.album}
    if folder_name.lower().startswith(("album - ", "ep - ", "single - ")) or (
            len(tracks) > 1 and len(albums) == 1):
        return "album"
    return "playlist"


def _most_common(values) -> str:
    c = Counter(v for v in values if v)
    return c.most_common(1)[0][0] if c else ""


def scan(root: str) -> list[Collection]:
    if not os.path.isdir(root):
        return []
    cache = _TagCache(root)
    loose = Collection("", root, tr("Loose songs"), "singles")
    folders: list[Collection] = []
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        rel_dir = os.path.relpath(dirpath, root)
        ordered = []        # (posición en la lista, nombre, Track)
        for name in files:
            if name.startswith(".") or os.path.splitext(name)[1].lower() not in AUDIO_EXT:
                continue
            path = os.path.join(dirpath, name)
            try:
                ordered.append((*_natural(name), cache.get(path, os.path.join(rel_dir, name))))
            except OSError:
                continue
        if rel_dir == ".":
            loose.tracks = [t for *_k, t in sorted(ordered, key=lambda x: x[:2])]
            continue
        meta = read_meta(dirpath)
        for ref in meta.get("refs", []):      # canciones que ya tenías en otra carpeta
            path = os.path.join(root, ref["path"])
            if os.path.isfile(path):
                t = cache.get(path, ref["path"])
                t.ref = True
                ordered.append((ref["pos"], "", t))
        tracks = [t for *_k, t in sorted(ordered, key=lambda x: x[:2])]
        if not tracks and not meta:
            continue
        base = os.path.basename(dirpath)
        kind = meta.get("kind") or _guess_kind(base, tracks)
        title = meta.get("title") or base
        if kind == "album" and not meta.get("title"):
            title = _most_common(t.album for t in tracks) or title
        folders.append(Collection(
            id=rel_dir, path=dirpath, title=title, kind=kind,
            artist=meta.get("artist") or (_most_common(t.artist for t in tracks) if kind == "album" else ""),
            # en una lista, el año más repetido de sus canciones no dice nada
            year=meta.get("year") or (_most_common(t.year for t in tracks) if kind == "album" else ""),
            url=meta.get("url", ""), source=meta.get("id", ""), tracks=tracks))
    cache.save()
    out = sorted(folders, key=lambda c: c.title.lower())
    if loose.tracks:
        out.append(loose)
    for c in out:
        for t in c.tracks:
            t.collection = c
    return out


def all_songs(collections: list[Collection], root: str) -> Collection:
    """Colección virtual con todas las canciones, para verlas y reproducirlas como una lista más."""
    tracks = sorted((t for c in collections for t in c.tracks if not t.ref),
                    key=lambda t: (t.artist.lower(), t.album.lower(), t.title.lower()))
    return Collection(id="__all__", path=root, title=tr("Songs"), kind="all", tracks=tracks)


# ------------------------------------------------------------------ duplicados
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def song_key(artist: str, title: str) -> tuple[str, str]:
    """Clave artista principal + título, sin tildes ni signos: para reconocer la misma canción
    aunque venga de otro vídeo (versión del álbum, videoclip…)."""
    artist = re.sub(r"\s*-\s*Topic$", "", artist or "")   # canal automático "Artista - Topic"
    return _norm(main_artist(artist)), _norm(title)


class Matcher:
    """Responde «¿esta canción ya la tengo?» por id de vídeo o por artista + título + duración."""

    def __init__(self, root: str):
        self.root = root
        self.by_id = {vid: rel for vid, rel in load_index(root).items()
                      if os.path.isfile(os.path.join(root, rel))}
        self.by_key: dict[tuple, list[tuple[str, float]]] = {}
        for c in scan(root):
            for t in c.tracks:
                if not t.ref:
                    rel = os.path.relpath(t.path, root)
                    self.by_key.setdefault(song_key(t.artist, t.title), []).append((rel, t.duration))

    def find(self, vid: str, artist: str, title: str, duration: float | None) -> str | None:
        """Ruta relativa del archivo que ya tienes, o None."""
        if vid in self.by_id:
            return self.by_id[vid]
        for rel, dur in self.by_key.get(song_key(artist, title), []):
            # misma clave y duración parecida (si se conoce): es la misma canción
            if not duration or not dur or abs(duration - dur) <= 6:
                return rel
        return None


# ------------------------------------------------------------------ portadas
def cover_bytes(path: str) -> bytes | None:
    """Portada incrustada, o .jpg con el mismo nombre, o cover/folder.jpg de la carpeta."""
    ext = os.path.splitext(path)[1].lower()
    base = os.path.splitext(path)[0]
    # el .jpg suelto es lo más rápido de leer, así que va primero
    for cand in (base + ".jpg", base + ".png"):
        if os.path.isfile(cand):
            with open(cand, "rb") as fh:
                return fh.read()
    try:
        if ext == ".flac":
            pics = FLAC(path).pictures
            if pics:
                return pics[0].data
        elif ext in (".mp3", ".wav"):
            f = mutagen.File(path)
            tags = f.tags if f is not None else None
            if isinstance(tags, ID3):
                apic = tags.getall("APIC")
                if apic:
                    return apic[0].data
        elif ext in (".m4a", ".aac"):
            covr = (MP4(path).tags or {}).get("covr")
            if covr:
                return bytes(covr[0])
        elif ext in (".opus", ".ogg"):
            f = mutagen.File(path)
            for b64 in (f.tags or {}).get("metadata_block_picture", []):
                return Picture(base64.b64decode(b64)).data
    except Exception:
        pass
    return folder_cover(os.path.dirname(path))


def folder_cover(folder: str) -> bytes | None:
    for name in ("cover.jpg", "cover.png", "folder.jpg"):
        cand = os.path.join(folder, name)
        if os.path.isfile(cand):
            with open(cand, "rb") as fh:
                return fh.read()
    return None
