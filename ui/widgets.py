"""Piezas reutilizables: delegados de listas, barra del reproductor y filas de la cola."""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSlider, QStyle,
    QStyledItemDelegate, QVBoxLayout,
)

import library
from ui import style
from ui.covers import Covers

ROLE = Qt.UserRole + 1


def fmt_time(seconds: float) -> str:
    s = int(seconds or 0)
    if s >= 3600:
        return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


def fmt_long(seconds: float) -> str:
    m = int(seconds or 0) // 60
    h, m = divmod(m, 60)
    if h:
        return f"{h} hora{'s' if h != 1 else ''} y {m} minuto{'s' if m != 1 else ''}"
    return f"{m} minuto{'s' if m != 1 else ''}"


def icon_button(name: str, size: int = 40, icon_size: int = 22, obj: str = "iconbtn",
                tip: str = "", color: str = style.TEXT) -> QPushButton:
    b = QPushButton(objectName=obj)
    b.setIcon(style.icon(name, color))
    b.setIconSize(QSize(icon_size, icon_size))
    b.setFixedSize(size, size)
    b.setCursor(Qt.PointingHandCursor)
    if tip:
        b.setToolTip(tip)
    return b


def _hover_bg(p: QPainter, opt, rect: QRect, radius: float = 6, active: bool = False):
    """Sombreado de la fila: `active` = la que está sonando (como la fila resaltada de YT Music)."""
    selected = opt.state & QStyle.State_Selected
    hovered = opt.state & QStyle.State_MouseOver
    if active or selected or hovered:
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        p.fillPath(path, style.C_SELECTED if (active or selected) else style.C_HOVER)


def _elide(p: QPainter, text: str, width: int) -> str:
    return QFontMetrics(p.font()).elidedText(text, Qt.ElideRight, max(width, 0))


# ------------------------------------------------------------------ canciones
LEAD_X, LEAD_W = 10, 48     # zona clicable a la izquierda de cada fila (nº o portada): ahí va el play


@lru_cache(maxsize=None)
def _icon(name: str):
    return style.icon(name)


def draw_icon(p: QPainter, name: str, rect: QRect, size: int):
    box = QRect(0, 0, size, size)
    box.moveCenter(rect.center())
    _icon(name).paint(p, box)


class TrackDelegate(QStyledItemDelegate):
    """Fila tipo YT Music: nº de pista o portada (que al pasar el ratón pasa a ser ▶/⏸),
    título, artista • álbum y duración."""

    H = 64

    def __init__(self, covers: Covers, parent=None):
        super().__init__(parent)
        self.covers = covers
        self.playing: str | None = None     # ruta de la canción que suena
        self.is_playing = False             # ... y si está en marcha o en pausa
        self.numbered = False               # álbumes y biblioteca: nº en vez de portada
        self.full_sub = False               # artista • álbum también en las listas numeradas

    def sizeHint(self, opt, index):
        return QSize(opt.rect.width(), self.H)

    def paint(self, p: QPainter, opt, index):
        t: library.Track = index.data(ROLE)
        if t is None:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = opt.rect.adjusted(0, 2, -8, -2)
        playing = t.path == self.playing
        hovered = bool(opt.state & QStyle.State_MouseOver)
        _hover_bg(p, opt, r, active=playing)
        cy = r.center().y()

        # símbolo de la izquierda: al pasar el ratón, play/pausa; si suena, el altavoz
        glyph = None
        if hovered:
            glyph = "pause" if (playing and self.is_playing) else "play"
        elif playing:
            glyph = "volume-high"
        lead = QRect(r.left() + LEAD_X, r.top(), LEAD_W, r.height())
        if self.numbered:
            if glyph:
                draw_icon(p, glyph, lead, 26)
            else:
                p.setFont(style.font(15))
                p.setPen(style.C_MUTED)
                p.drawText(lead, Qt.AlignCenter, str(index.row() + 1))
        else:
            cover = QRect(lead.left(), cy - 24, 48, 48)
            p.drawPixmap(cover.topLeft(), self.covers.track(t, 48))
            if glyph:
                shade = QPainterPath()
                shade.addRoundedRect(QRectF(cover), 4, 4)
                p.fillPath(shade, QColor(0, 0, 0, 130))
                draw_icon(p, glyph, cover, 26)

        x = r.left() + LEAD_X + 64
        dur_w = 60
        text_w = r.right() - x - dur_w - 10
        p.setFont(style.font(15, QFont.DemiBold))
        p.setPen(style.C_TEXT)
        p.drawText(QRect(x, cy - 21, text_w, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   _elide(p, t.title, text_w))
        p.setFont(style.font(14))
        p.setPen(style.C_MUTED)
        sub = t.main_artist if (self.numbered and not self.full_sub) else t.subtitle
        p.drawText(QRect(x, cy + 2, text_w, 20), Qt.AlignLeft | Qt.AlignVCenter, _elide(p, sub, text_w))
        p.drawText(QRect(r.right() - dur_w - 6, r.top(), dur_w, r.height()),
                   Qt.AlignRight | Qt.AlignVCenter, fmt_time(t.duration))
        p.restore()


# ------------------------------------------------------------------ tarjetas de colección
class CardDelegate(QStyledItemDelegate):
    COVER = 176
    BTN = 40        # diámetro del botón de play que aparece al pasar el ratón

    def __init__(self, covers: Covers, parent=None):
        super().__init__(parent)
        self.covers = covers

    @classmethod
    def cover_rect(cls, rect: QRect) -> QRect:
        r = rect.adjusted(4, 4, -4, -4)
        return QRect(r.left() + 8, r.top() + 8, cls.COVER, cls.COVER)

    @classmethod
    def play_rect(cls, rect: QRect) -> QRect:
        """Círculo de play: esquina inferior derecha de la portada."""
        c = cls.cover_rect(rect)
        return QRect(c.right() - 10 - cls.BTN + 1, c.bottom() - 10 - cls.BTN + 1, cls.BTN, cls.BTN)

    def sizeHint(self, opt, index):
        return QSize(self.COVER + 24, self.COVER + 78)

    def paint(self, p: QPainter, opt, index):
        c: library.Collection = index.data(ROLE)
        if c is None:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        _hover_bg(p, opt, opt.rect.adjusted(4, 4, -4, -4), 10)
        cover = self.cover_rect(opt.rect)
        x, y, w = cover.left(), cover.top(), self.COVER
        p.drawPixmap(cover.topLeft(), self.covers.collection(c, self.COVER, 6))
        if opt.state & QStyle.State_MouseOver:
            btn = self.play_rect(opt.rect)
            p.setPen(QColor(255, 255, 255, 60))     # aro fino: se ve también sobre portadas oscuras
            p.setBrush(QColor(0, 0, 0, 190))
            p.drawEllipse(btn)
            draw_icon(p, "play", btn.translated(1, 0), 28)
        p.setFont(style.font(15, QFont.DemiBold))
        p.setPen(style.C_TEXT)
        p.drawText(QRect(x, y + w + 8, w, 20), Qt.AlignLeft | Qt.AlignVCenter, _elide(p, c.title, w))
        p.setFont(style.font(13))
        p.setPen(style.C_MUTED)
        sub = c.subtitle if c.kind != "singles" else f"{len(c.tracks)} canciones"
        p.drawText(QRect(x, y + w + 30, w, 36), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                   QFontMetrics(p.font()).elidedText(sub, Qt.ElideRight, w * 2 - 20))
        p.restore()


# ------------------------------------------------------------------ barra lateral
class SidebarDelegate(QStyledItemDelegate):
    def sizeHint(self, opt, index):
        return QSize(opt.rect.width(), 54)

    def paint(self, p: QPainter, opt, index):
        c: library.Collection = index.data(ROLE)
        if c is None:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = opt.rect.adjusted(0, 1, 0, -1)
        _hover_bg(p, opt, r, 8)
        w = r.width() - 28
        p.setFont(style.font(14, QFont.Medium))
        p.setPen(style.C_TEXT)
        p.drawText(QRect(r.left() + 14, r.top() + 8, w, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   _elide(p, c.title, w))
        p.setFont(style.font(12))
        p.setPen(style.C_MUTED)
        sub = " • ".join(x for x in (c.kind_label, c.artist) if x)
        p.drawText(QRect(r.left() + 14, r.top() + 28, w, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   _elide(p, sub, w))
        p.restore()


# ------------------------------------------------------------------ barra de progreso
class SeekBar(QSlider):
    """Barra fina pegada al borde superior del reproductor, como en YT Music.
    El punto rojo y el grosor extra solo aparecen al pasar el ratón por encima."""

    H = 12

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.setFixedHeight(self.H)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)

    def _value_at(self, x: float) -> int:
        x = min(max(int(x), 0), self.width())
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), x, max(self.width(), 1))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.maximum() > 0:
            self.setSliderDown(True)           # emite sliderPressed
            self.setValue(self._value_at(e.position().x()))
            e.accept()

    def mouseMoveEvent(self, e):
        if self.isSliderDown():
            self.setValue(self._value_at(e.position().x()))
            e.accept()

    def mouseReleaseEvent(self, e):
        if self.isSliderDown() and e.button() == Qt.LeftButton:
            self.setValue(self._value_at(e.position().x()))
            self.setSliderDown(False)          # emite sliderReleased
            e.accept()

    def enterEvent(self, e):
        self.update()

    def leaveEvent(self, e):
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hot = self.underMouse() or self.isSliderDown()
        w = self.width()
        thick = 5 if hot else 3
        span = self.maximum() - self.minimum()
        x = w * (self.value() - self.minimum()) / span if span > 0 else 0
        p.fillRect(QRectF(0, 0, w, thick), QColor(255, 255, 255, 50))
        p.fillRect(QRectF(0, 0, x, thick), style.C_ACCENT)
        if hot and span > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(style.C_ACCENT)
            p.drawEllipse(QPointF(min(max(x, 6), w - 6), 6), 6, 6)


# ------------------------------------------------------------------ reproductor
class PlayerBar(QFrame):
    play_clicked = Signal()
    prev_clicked = Signal()
    next_clicked = Signal()
    seek_to = Signal(int)
    volume_changed = Signal(int)
    shuffle_toggled = Signal(bool)
    repeat_changed = Signal(str)       # off | all | one
    open_current = Signal()

    REPEAT = ["off", "all", "one"]

    def __init__(self, covers: Covers):
        super().__init__(objectName="playerbar")
        self.covers = covers
        self.seeking = False
        self.repeat = "off"
        self.setFixedHeight(76)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.seek = SeekBar()
        self.seek.sliderPressed.connect(lambda: setattr(self, "seeking", True))
        self.seek.sliderReleased.connect(self._released)
        outer.addWidget(self.seek)

        row = QHBoxLayout()
        row.setContentsMargins(12, 0, 16, 6)
        outer.addLayout(row)

        self.btn_prev = icon_button("skip-previous", 40, 28)
        self.btn_play = icon_button("play", 48, 36)
        self.btn_next = icon_button("skip-next", 40, 28)
        self.btn_prev.clicked.connect(self.prev_clicked)
        self.btn_play.clicked.connect(self.play_clicked)
        self.btn_next.clicked.connect(self.next_clicked)
        self.lbl_time = QLabel("0:00 / 0:00", objectName="small")
        self.lbl_time.setMinimumWidth(90)
        for w in (self.btn_prev, self.btn_play, self.btn_next):
            row.addWidget(w)
        row.addSpacing(8)
        row.addWidget(self.lbl_time)
        row.addStretch(1)

        self.cover = QLabel()
        self.cover.setFixedSize(40, 40)
        self.cover.setCursor(Qt.PointingHandCursor)
        self.cover.installEventFilter(self)
        info = QVBoxLayout()
        info.setSpacing(0)
        self.lbl_title = QLabel("", objectName="")
        self.lbl_title.setFont(style.font(14, QFont.DemiBold))
        self.lbl_sub = QLabel("", objectName="small")
        for l in (self.lbl_title, self.lbl_sub):
            l.setMaximumWidth(420)
            l.setCursor(Qt.PointingHandCursor)
            l.installEventFilter(self)
        info.addWidget(self.lbl_title)
        info.addWidget(self.lbl_sub)
        row.addWidget(self.cover)
        row.addSpacing(6)
        row.addLayout(info)
        row.addStretch(1)

        self.btn_vol = icon_button("volume-high", 36, 22, tip="Silenciar")
        self.btn_vol.setCheckable(True)
        self.btn_vol.toggled.connect(self._mute)
        self.volume = QSlider(Qt.Horizontal, objectName="volume", maximum=100)
        self.volume.setFixedWidth(100)
        self.volume.valueChanged.connect(self.volume_changed)
        self.btn_repeat = icon_button("repeat-off", 36, 22, tip="Repetir")
        self.btn_repeat.clicked.connect(self._cycle_repeat)
        self.btn_shuffle = icon_button("shuffle-variant", 36, 22, tip="Aleatorio")
        self.btn_shuffle.setCheckable(True)
        self.btn_shuffle.toggled.connect(self._shuffle)
        self._shuffle(False)
        for w in (self.btn_vol, self.volume, self.btn_repeat, self.btn_shuffle):
            row.addWidget(w)
        self.set_track(None)

    def eventFilter(self, obj, e):
        if e.type() == QEvent.MouseButtonRelease:
            self.open_current.emit()
        return False

    def _released(self):
        self.seeking = False
        self.seek_to.emit(self.seek.value())

    def _mute(self, on: bool):
        self.btn_vol.setIcon(style.icon("volume-off" if on else "volume-high"))
        self.volume_changed.emit(0 if on else self.volume.value())

    def _shuffle(self, on: bool):
        self.btn_shuffle.setIcon(style.icon("shuffle-variant", style.TEXT if on else "#777777"))
        self.shuffle_toggled.emit(on)

    def _cycle_repeat(self):
        self.set_repeat(self.REPEAT[(self.REPEAT.index(self.repeat) + 1) % 3])
        self.repeat_changed.emit(self.repeat)

    def set_repeat(self, mode: str):
        self.repeat = mode if mode in self.REPEAT else "off"
        name = {"off": "repeat-off", "all": "repeat", "one": "repeat-once"}[self.repeat]
        self.btn_repeat.setIcon(style.icon(name, "#777777" if self.repeat == "off" else style.TEXT))

    def set_playing(self, playing: bool):
        self.btn_play.setIcon(style.icon("pause" if playing else "play"))

    def set_track(self, t: library.Track | None):
        if t is None:
            self.cover.setPixmap(self.covers.track(library.Track("", "", "", "", 0, ""), 40))
            self.lbl_title.setText("Nada sonando")
            self.lbl_sub.setText("Elige una canción de tu biblioteca")
            return
        self.cover.setPixmap(self.covers.track(t, 40))
        fm = QFontMetrics(self.lbl_title.font())
        self.lbl_title.setText(fm.elidedText(t.title, Qt.ElideRight, 420))
        sub = " • ".join(x for x in (t.main_artist, t.album, t.year) if x)
        self.lbl_sub.setText(QFontMetrics(self.lbl_sub.font()).elidedText(sub, Qt.ElideRight, 420))

    def set_position(self, ms: int, total: int):
        if not self.seeking:
            self.seek.setValue(ms)
        self.lbl_time.setText(f"{fmt_time(ms / 1000)} / {fmt_time(total / 1000)}")

    def set_duration(self, ms: int):
        self.seek.setRange(0, ms)


# ------------------------------------------------------------------ fila de la cola
class QueueRow(QFrame):
    remove = Signal()
    retry = Signal()

    KIND = {"album": "ÁLBUM", "playlist": "LISTA", "single": "CANCIÓN", "": "…"}

    def __init__(self, url: str):
        super().__init__(objectName="queuerow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 8, 10)
        lay.setSpacing(12)
        self.state_icon = QLabel()
        self.state_icon.setFixedSize(22, 22)
        lay.addWidget(self.state_icon)

        col = QVBoxLayout()
        col.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.tag = QLabel("…", objectName="tag")
        self.title = QLabel(url)
        self.title.setFont(style.font(14, QFont.DemiBold))
        self.title.setMinimumWidth(10)
        top.addWidget(self.tag)
        top.addWidget(self.title, 1)
        col.addLayout(top)
        self.status = QLabel("En cola", objectName="small")
        self.status.setMinimumWidth(10)     # textos largos: se cortan en vez de ensanchar la fila
        col.addWidget(self.status)
        self.bar = QProgressBar(textVisible=False, maximum=1000)
        col.addWidget(self.bar)
        lay.addLayout(col, 1)

        self.btn_retry = icon_button("reload", 34, 20, tip="Reintentar")
        self.btn_retry.clicked.connect(self.retry)
        self.btn_remove = icon_button("close", 34, 20, tip="Quitar de la cola / cancelar")
        self.btn_remove.clicked.connect(self.remove)
        lay.addWidget(self.btn_retry)
        lay.addWidget(self.btn_remove)
        self.set_state("pending")

    def set_state(self, state: str, text: str | None = None):
        icons = {"pending": ("clock-outline", style.MUTED), "running": ("download", style.TEXT),
                 "done": ("check-circle", "#3ec46d"), "error": ("alert-circle", "#ff5a5a"),
                 "cancelled": ("close", style.MUTED)}
        name, color = icons.get(state, icons["pending"])
        self.state_icon.setPixmap(style.icon(name, color).pixmap(22, 22))
        self.btn_retry.setVisible(state in ("error", "cancelled", "done"))
        self.bar.setVisible(state == "running")
        if text is not None:
            self.status.setText(text)

    def set_info(self, title: str, kind: str):
        self.title.setText(title)
        self.tag.setText(self.KIND.get(kind, kind.upper()))
