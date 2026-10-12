"""Caché de portadas ya escaladas (nunca guarda la imagen original en memoria)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap

from ytmd import library
from ytmd.ui import style


def _decode(data: bytes | None, size: int) -> QImage | None:
    img = QImage()
    if not data or not img.loadFromData(data):
        return None
    return img.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)


def _rounded(img: QImage | None, size: int, radius: float) -> QPixmap:
    pix = QPixmap(size, size)
    pix.setDevicePixelRatio(1)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.setClipPath(path)
    if img is None:
        p.fillRect(0, 0, size, size, QColor("#2a2a2a"))
        p.setPen(QColor("#5a5a5a"))
        p.setFont(style.font(int(size * 0.4)))
        p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "♪")
    else:
        x = (img.width() - size) // 2
        y = (img.height() - size) // 2
        p.drawImage(0, 0, img, x, y, size, size)
    p.end()
    return pix


class Covers:
    def __init__(self, dpr: float = 2.0):
        self.dpr = dpr                      # pantallas Retina: se pinta al doble
        self._pix: dict[tuple, QPixmap] = {}
        self._img: dict[tuple, QImage | None] = {}
        self._accent: dict[str, QColor] = {}

    def clear(self):
        self._pix.clear()
        self._img.clear()
        self._accent.clear()

    def _image(self, path: str, px: int) -> QImage | None:
        key = (path, px)
        if key not in self._img:
            self._img[key] = _decode(library.cover_bytes(path), px)
        return self._img[key]

    def _finish(self, key, img: QImage | None, size: int, radius: float) -> QPixmap:
        px = int(size * self.dpr)
        pix = _rounded(img, px, radius * self.dpr)
        pix.setDevicePixelRatio(self.dpr)
        self._pix[key] = pix
        return pix

    def track(self, t: library.Track, size: int, radius: float = 4) -> QPixmap:
        key = ("t", t.path, size, radius)
        if key in self._pix:
            return self._pix[key]
        return self._finish(key, self._image(t.path, int(size * self.dpr)), size, radius)

    def _mosaic_sources(self, c: library.Collection) -> list[library.Track]:
        """Hasta 4 canciones de álbumes distintos, como hace YouTube Music con las listas."""
        seen, out = set(), []
        for t in c.tracks:
            k = t.album or t.path
            if k not in seen:
                seen.add(k)
                out.append(t)
            if len(out) == 4:
                break
        return out

    def collection(self, c: library.Collection, size: int, radius: float = 6) -> QPixmap:
        key = ("c", c.path, c.kind, len(c.tracks), size, radius)
        if key in self._pix:
            return self._pix[key]
        px = int(size * self.dpr)
        img = None
        if c.kind == "album":
            img = _decode(library.folder_cover(c.path), px)
            if img is None and c.tracks:
                img = self._image(c.tracks[0].path, px)
        else:
            src = self._mosaic_sources(c)
            if len(src) == 4:
                half = px // 2
                img = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
                img.fill(QColor("#2a2a2a"))
                p = QPainter(img)
                for i, t in enumerate(src):
                    tile = self._image(t.path, half)
                    if tile is not None:
                        p.drawImage((i % 2) * half, (i // 2) * half, tile,
                                    (tile.width() - half) // 2, (tile.height() - half) // 2, half, half)
                p.end()
            elif src:
                img = self._image(src[0].path, px)
        return self._finish(key, img, size, radius)

    def accent(self, c: library.Collection) -> QColor:
        """Color medio de la portada, oscurecido: para el degradado de fondo."""
        key = (c.path, c.kind)
        if key in self._accent:
            return self._accent[key]
        img = self.collection(c, 48).toImage().scaled(1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        col = QColor(img.pixel(0, 0)) if not img.isNull() else QColor("#333333")
        h, s, v, _ = col.getHsv()
        col = QColor.fromHsv(max(h, 0), min(s, 200), min(max(v, 60), 140))
        self._accent[key] = col
        return col
