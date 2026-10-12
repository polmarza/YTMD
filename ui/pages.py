"""Páginas principales: Inicio, Colección (también la de todas las canciones) y Descargas."""
from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMenu, QPlainTextEdit,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import library
from downloader import BROWSERS, FORMATS, PAUSES
from ui import style
from ui.covers import Covers
from ui.widgets import LEAD_W, LEAD_X, ROLE, CardDelegate, QueueRow, TrackDelegate, fmt_long, icon_button


def search_box(placeholder: str) -> QLineEdit:
    box = QLineEdit(placeholderText=placeholder, objectName="search", clearButtonEnabled=True)
    box.addAction(QAction(style.icon("magnify", style.MUTED), "", box), QLineEdit.LeadingPosition)
    return box


class TrackList(QListWidget):
    """Lista de canciones con el aspecto de YT Music."""

    play_requested = Signal(list, int)          # (lista de Track, índice)
    toggle_requested = Signal()                 # pausa/reanuda la que ya suena
    reveal_requested = Signal(str)

    def __init__(self, covers: Covers):
        super().__init__()
        self.delegate = TrackDelegate(covers, self)
        self.setItemDelegate(self.delegate)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.itemDoubleClicked.connect(lambda it: self._play(it))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def set_tracks(self, tracks: list[library.Track]):
        self.clear()
        for t in tracks:
            it = QListWidgetItem()
            it.setData(ROLE, t)
            it.setToolTip(t.path)
            self.addItem(it)

    def visible_tracks(self) -> list[library.Track]:
        return [self.item(i).data(ROLE) for i in range(self.count()) if not self.item(i).isHidden()]

    def filter(self, text: str):
        q = text.lower().strip()
        for i in range(self.count()):
            t: library.Track = self.item(i).data(ROLE)
            hay = f"{t.title} {t.artist} {t.album}".lower()
            self.item(i).setHidden(bool(q) and q not in hay)

    def set_playing(self, path: str | None, active: bool = True):
        self.delegate.playing = path
        self.delegate.is_playing = active
        self.viewport().update()

    def _over_lead(self, e) -> QListWidgetItem | None:
        """El item si el cursor está sobre su zona de play (nº o portada), si no None."""
        pos = e.position().toPoint()
        it = self.itemAt(pos)
        if it is None:
            return None
        x = pos.x() - self.visualItemRect(it).left()
        return it if LEAD_X <= x <= LEAD_X + LEAD_W else None

    def mouseMoveEvent(self, e):
        self.viewport().setCursor(Qt.PointingHandCursor if self._over_lead(e) else Qt.ArrowCursor)
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        it = self._over_lead(e) if e.button() == Qt.LeftButton else None
        if it is None:
            super().mousePressEvent(e)
            return
        self.setCurrentItem(it)
        if it.data(ROLE).path == self.delegate.playing:
            self.toggle_requested.emit()
        else:
            self._play(it)
        e.accept()

    def _play(self, it: QListWidgetItem):
        tracks = self.visible_tracks()
        t = it.data(ROLE)
        self.play_requested.emit(tracks, tracks.index(t))

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.currentItem():
            self._play(self.currentItem())
        else:
            super().keyPressEvent(e)

    def _menu(self, pos):
        it = self.itemAt(pos)
        if not it:
            return
        m = QMenu(self)
        m.addAction("Reproducir", lambda: self._play(it))
        m.addAction(f"Mostrar en {style.FILE_MANAGER}", lambda: self.reveal_requested.emit(it.data(ROLE).path))
        m.exec(self.viewport().mapToGlobal(pos))


# ------------------------------------------------------------------ Inicio
class CardGrid(QListWidget):
    """Rejilla de portadas: el círculo de play (al pasar el ratón) reproduce la colección sin abrirla."""

    play_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self._on_button = False

    def _button_item(self, e) -> QListWidgetItem | None:
        pos = e.position().toPoint()
        it = self.itemAt(pos)
        if it is not None and CardDelegate.play_rect(self.visualItemRect(it)).contains(pos):
            return it
        return None

    def mouseMoveEvent(self, e):
        self.viewport().setCursor(Qt.PointingHandCursor if self._button_item(e) else Qt.ArrowCursor)
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        it = self._button_item(e) if e.button() == Qt.LeftButton else None
        if it is None:
            super().mousePressEvent(e)
            return
        self._on_button = True
        self.play_requested.emit(it.data(ROLE))
        e.accept()

    def mouseReleaseEvent(self, e):
        if self._on_button:         # el clic fue del botón: que no abra la colección
            self._on_button = False
            e.accept()
            return
        super().mouseReleaseEvent(e)


class HomePage(QWidget):
    open_collection = Signal(object)
    play_collection = Signal(object)

    FILTERS = [("Todo", None), ("Listas", "playlist"), ("Álbumes", "album"), ("Sueltas", "singles")]

    def __init__(self, covers: Covers):
        super().__init__()
        self.kind_filter = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 20, 28, 0)
        lay.setSpacing(16)

        self.search = search_box("Buscar en tus listas, álbumes y artistas")
        self.search.setMaximumWidth(480)
        self.search.textChanged.connect(self.apply_filter)
        lay.addWidget(self.search)

        chips = QHBoxLayout()
        chips.setSpacing(10)
        self.group = QButtonGroup(self)
        for i, (label, kind) in enumerate(self.FILTERS):
            b = QPushButton(label, objectName="chip", checkable=True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=kind: self._set_kind(k))
            self.group.addButton(b, i)
            chips.addWidget(b)
        self.group.button(0).setChecked(True)
        chips.addStretch(1)
        lay.addLayout(chips)

        lay.addWidget(QLabel("Tu biblioteca", objectName="h1"))
        self.empty = QLabel("Aún no hay nada. Ve a <b>Descargas</b> y pega un enlace de YouTube Music.",
                            objectName="muted")
        lay.addWidget(self.empty)

        self.grid = CardGrid()
        self.grid.play_requested.connect(self.play_collection)
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setMovement(QListView.Static)
        self.grid.setUniformItemSizes(True)
        self.grid.setMouseTracking(True)
        self.grid.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.grid.verticalScrollBar().setSingleStep(30)
        self.grid.setItemDelegate(CardDelegate(covers, self.grid))
        self.grid.setGridSize(QSize(CardDelegate.COVER + 28, CardDelegate.COVER + 84))
        self.grid.itemClicked.connect(lambda it: self.open_collection.emit(it.data(ROLE)))
        lay.addWidget(self.grid, 1)

    def set_collections(self, cols: list[library.Collection]):
        self.grid.clear()
        for c in cols:
            it = QListWidgetItem()
            it.setData(ROLE, c)
            self.grid.addItem(it)
        self.empty.setVisible(not cols)
        self.apply_filter()

    def _set_kind(self, kind):
        self.kind_filter = kind
        self.apply_filter()

    def apply_filter(self, *_):
        q = self.search.text().lower().strip()
        for i in range(self.grid.count()):
            c: library.Collection = self.grid.item(i).data(ROLE)
            hay = f"{c.title} {c.artist} " + " ".join(t.artist for t in c.tracks[:50])
            hide = (self.kind_filter and c.kind != self.kind_filter) or (q and q not in hay.lower())
            self.grid.item(i).setHidden(bool(hide))


# ------------------------------------------------------------------ Colección
class CollectionPage(QWidget):
    play_requested = Signal(list, int)
    shuffle_requested = Signal(list)
    kind_changed = Signal(object, str)
    update_requested = Signal(object)
    reveal_requested = Signal(str)

    KIND_CHOICES = [("playlist", "Lista"), ("album", "Álbum")]

    def __init__(self, covers: Covers):
        super().__init__()
        self.covers = covers
        self.col: library.Collection | None = None
        self.accent = QColor("#333333")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(56, 40, 28, 0)
        lay.setSpacing(48)

        left = QVBoxLayout()
        left.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        left.setSpacing(10)
        self.cover = QLabel()
        self.cover.setFixedSize(264, 264)
        left.addWidget(self.cover, 0, Qt.AlignHCenter)
        left.addSpacing(8)
        self.title = QLabel(objectName="coltitle", wordWrap=True, alignment=Qt.AlignHCenter)
        self.title.setFixedWidth(300)
        left.addWidget(self.title, 0, Qt.AlignHCenter)

        # El selector para clasificar: lista o álbum
        self.kind = QComboBox()
        for key, label in self.KIND_CHOICES:
            self.kind.addItem(label, key)
        self.kind.setToolTip("Clasifica esta colección como lista o como álbum")
        self.kind.activated.connect(self._kind_activated)
        left.addWidget(self.kind, 0, Qt.AlignHCenter)

        self.sub = QLabel(objectName="muted", wordWrap=True, alignment=Qt.AlignHCenter)
        self.stats = QLabel(objectName="muted", alignment=Qt.AlignHCenter)
        self.sub.setFixedWidth(300)
        left.addWidget(self.sub, 0, Qt.AlignHCenter)
        left.addWidget(self.stats, 0, Qt.AlignHCenter)
        left.addSpacing(10)

        actions = QHBoxLayout()
        actions.setSpacing(16)
        self.btn_update = icon_button("sync", 44, 22, "roundbtn",
                                      "Actualizar: descarga solo las canciones nuevas de la lista")
        self.btn_update.clicked.connect(lambda: self.col and self.update_requested.emit(self.col))
        self.btn_play = icon_button("play", 64, 40, "bigplay", "Reproducir", color="#000000")
        self.btn_play.clicked.connect(lambda: self.play_requested.emit(self.tracks.visible_tracks(), 0))
        self.btn_shuffle = icon_button("shuffle-variant", 44, 22, "roundbtn", "Aleatorio")
        self.btn_shuffle.clicked.connect(lambda: self.shuffle_requested.emit(self.tracks.visible_tracks()))
        self.btn_folder = icon_button("folder-open-outline", 44, 22, "roundbtn", f"Mostrar en {style.FILE_MANAGER}")
        self.btn_folder.clicked.connect(lambda: self.col and self.reveal_requested.emit(self.col.path))
        for b in (self.btn_update, self.btn_play, self.btn_shuffle, self.btn_folder):
            actions.addWidget(b)
        left.addLayout(actions)
        lay.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(10)
        self.search = search_box("Buscar en esta colección")
        self.search.setMaximumWidth(360)
        right.addWidget(self.search)
        self.tracks = TrackList(covers)
        self.tracks.play_requested.connect(self.play_requested)
        self.tracks.reveal_requested.connect(self.reveal_requested)
        self.search.textChanged.connect(self.tracks.filter)
        right.addWidget(self.tracks, 1)
        lay.addLayout(right, 1)

    def show_collection(self, c: library.Collection):
        self.col = c
        self.accent = self.covers.accent(c)
        self.cover.setPixmap(self.covers.collection(c, 264, 8))
        self.title.setText(c.title)
        self.kind.setVisible(c.kind in ("album", "playlist"))
        self.kind.setCurrentIndex(max(0, self.kind.findData(c.kind)))
        if c.kind == "album":
            sub = " • ".join(x for x in (c.artist, c.year) if x)
        elif c.kind == "playlist":
            sub = " • ".join(x for x in (c.artist and f"de {c.artist}", c.year) if x)
        elif c.kind == "all":
            sub = "Toda tu biblioteca"
        else:
            sub = "Canciones descargadas sueltas"
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))
        n = len(c.tracks)
        self.stats.setText(f"{n} pista{'s' if n != 1 else ''} • {fmt_long(c.duration)}")
        self.btn_update.setVisible(bool(c.url))
        self.tracks.delegate.numbered = c.kind in ("album", "all")
        self.tracks.delegate.full_sub = c.kind == "all"      # artista • álbum en la lista conjunta
        self.search.clear()
        self.tracks.set_tracks(c.tracks)
        self.update()

    def _kind_activated(self, _i):
        if self.col and self.kind.currentData() != self.col.kind:
            self.kind_changed.emit(self.col, self.kind.currentData())

    def paintEvent(self, e):
        # degradado con el color de la portada, como el fondo de YT Music
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height() * 0.8)
        top = QColor(self.accent)
        top.setAlpha(150)
        g.setColorAt(0, top)
        g.setColorAt(1, QColor(style.BG))
        p.fillRect(self.rect(), g)


# ------------------------------------------------------------------ Descargas
class DownloadsPage(QWidget):
    """Dos mitades: la cola a la izquierda y el formulario para añadir enlaces a la derecha."""

    enqueue = Signal(list)             # lista de URLs
    import_requested = Signal()
    pause_toggled = Signal(bool)
    clear_finished = Signal()
    choose_dir = Signal()
    open_dir = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 20, 28, 20)
        lay.setSpacing(16)

        head = QHBoxLayout()
        head.addWidget(QLabel("Descargas", objectName="h1"))
        head.addStretch(1)
        self.btn_import = QPushButton("  Importar desde mi cuenta", objectName="accent")
        self.btn_import.setIcon(style.icon("account-music"))
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.setToolTip("Elige listas (también privadas), «Música que me gusta» y álbumes "
                                   "guardados de tu YouTube Music. Usa el navegador de «Cookies».")
        self.btn_import.clicked.connect(self.import_requested)
        head.addWidget(self.btn_import)
        lay.addLayout(head)

        cols = QHBoxLayout()
        cols.setSpacing(28)
        cols.addLayout(self._build_queue(), 1)
        # el formulario también puede desplazarse: en ventanas bajas se desplaza en vez de aplastarse
        form = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame)
        form.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        form.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        holder = QWidget()                  # contenedor transparente: la tarjeta conserva su fondo
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self._build_form())
        form.setWidget(holder)
        cols.addWidget(form, 1)
        lay.addLayout(cols, 1)

    # ------------------------------------------------------------ columna izquierda: cola
    def _build_queue(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(QLabel("Cola", objectName="h2"))
        self.lbl_queue = QLabel(objectName="muted")
        self.lbl_queue.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        head.addWidget(self.lbl_queue, 1)
        self.btn_pause = QPushButton("Pausar")
        self.btn_pause.setCheckable(True)
        self.btn_pause.toggled.connect(self._pause)
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setToolTip("Quita de la lista las descargas terminadas o canceladas")
        self.btn_clear.clicked.connect(self.clear_finished)
        head.addWidget(self.btn_pause)
        head.addWidget(self.btn_clear)
        col.addLayout(head)

        # la cola tiene su propio scroll; el formulario de al lado se queda quieto
        area = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        box = QWidget()
        area.setWidget(box)
        self.queue_box = QVBoxLayout(box)
        self.queue_box.setContentsMargins(0, 0, 6, 0)
        self.queue_box.setSpacing(8)
        self.queue_empty = QLabel("La cola está vacía. Añade enlaces con el formulario o importa "
                                  "desde tu cuenta.", objectName="muted", wordWrap=True)
        self.queue_box.addWidget(self.queue_empty)
        self.queue_box.addStretch(1)
        self._rows = 0
        col.addWidget(area, 1)

        self.btn_log = QPushButton("Mostrar registro")
        self.btn_log.setCheckable(True)
        self.btn_log.setStyleSheet("text-align: left; background: transparent; color: #aaa; padding-left: 0;")
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setFixedHeight(160)
        self.log.setVisible(False)
        self.log.setMaximumBlockCount(3000)
        self.btn_log.toggled.connect(lambda on: (self.log.setVisible(on),
                                                 self.btn_log.setText("Ocultar registro" if on else "Mostrar registro")))
        col.addWidget(self.btn_log, 0, Qt.AlignLeft)
        col.addWidget(self.log)
        return col

    # ------------------------------------------------------------ columna derecha: formulario
    def _build_form(self) -> QWidget:
        panel = QFrame(objectName="panel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(20, 18, 20, 20)
        pl.setSpacing(12)
        pl.addWidget(QLabel("Añadir enlaces", objectName="h2"))

        self.urls = QPlainTextEdit()
        self.urls.setPlaceholderText(
            "Pega uno o varios enlaces de YouTube Music, uno por línea: canciones, álbumes o "
            "listas (también las tuyas privadas, con cookies).")
        self.urls.setMinimumHeight(96)
        pl.addWidget(self.urls, 1)

        self.cmb_format = QComboBox()
        self.cmb_format.addItems(FORMATS.keys())
        self.cmb_format.setToolTip(
            "FLAC: sin pérdida y con portada/etiquetas (recomendado).\n"
            "WAV: PCM puro, el más fácil de decodificar en un microcontrolador; portada como .jpg aparte.\n"
            "MP3 320: máxima compatibilidad (DFPlayer, VS1053…), pero recodifica con pérdida.\n"
            "Original: el Opus/AAC tal cual lo sirve YouTube, sin tocar.")
        self.cmb_browser = QComboBox()
        self.cmb_browser.addItems(BROWSERS)
        self.cmb_browser.setToolTip(
            "Usa la sesión de YouTube Music de ese navegador.\n"
            "Con Premium desbloquea AAC 256 kbps y permite bajar tus listas privadas.")
        self.cmb_pause = QComboBox()
        self.cmb_pause.addItems(PAUSES.keys())
        self.cmb_pause.setToolTip(
            "Espera aleatoria antes de cada canción para que YouTube no te frene.\n"
            "Para listas grandes o si usas cookies de tu cuenta, mejor «Segura».")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        for r, (label, w) in enumerate((("Formato", self.cmb_format), ("Cookies", self.cmb_browser),
                                         ("Pausas", self.cmb_pause))):
            grid.addWidget(QLabel(label, objectName="muted"), r, 0)
            grid.addWidget(w, r, 1)
        pl.addLayout(grid)

        self.chk_44k = QCheckBox("44.1 kHz / 16 bit")
        self.chk_44k.setToolTip("Formato de CD: el más compatible con DACs I2S y decodificadores.")
        self.chk_ascii = QCheckBox("Nombres solo ASCII")
        self.chk_ascii.setToolTip("Sin tildes, ñ ni espacios: por si tu firmware lee la SD sin nombres largos.")
        self.chk_cover = QCheckBox("Portada .jpg aparte")
        self.chk_skip = QCheckBox("Saltar ya descargadas")
        self.chk_skip.setToolTip("No vuelve a bajar lo que ya tienes (ni otro vídeo de la misma canción).")
        checks = QVBoxLayout()
        checks.setSpacing(8)
        for w in (self.chk_44k, self.chk_ascii, self.chk_cover, self.chk_skip):
            checks.addWidget(w)
        pl.addLayout(checks)

        pl.addWidget(QFrame(objectName="sep"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Carpeta", objectName="muted"))
        row.addStretch(1)
        b = QPushButton("Cambiar…")
        b.clicked.connect(self.choose_dir)
        row.addWidget(b)
        b = QPushButton("Abrir")
        b.clicked.connect(self.open_dir)
        row.addWidget(b)
        pl.addLayout(row)
        self.lbl_dir = QLabel(objectName="small")
        self.lbl_dir.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # rutas largas: que se corten en vez de ensanchar el formulario
        self.lbl_dir.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        pl.addWidget(self.lbl_dir)

        self.btn_add = QPushButton("Añadir a la cola", objectName="primary")
        self.btn_add.setIcon(style.icon("plus", "#000000"))
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self._add)
        pl.addSpacing(4)
        pl.addWidget(self.btn_add)
        return panel

    def set_dir(self, path: str):
        home = os.path.expanduser("~")
        self.lbl_dir.setText("~" + path[len(home):] if path.startswith(home) else path)
        self.lbl_dir.setToolTip(path)

    def _add(self):
        urls = [u.strip() for u in self.urls.toPlainText().split() if u.strip()]
        good = [u for u in urls if "youtube.com" in u or "youtu.be" in u]
        if good:
            self.enqueue.emit(good)
            self.urls.clear()
        bad = len(urls) - len(good)
        if bad:
            self.add_log(f"⚠ Ignorados {bad} enlaces que no son de YouTube.")

    def _pause(self, on: bool):
        self.btn_pause.setText("Reanudar" if on else "Pausar")
        self.pause_toggled.emit(on)

    def add_row(self, row: QueueRow):
        self.queue_empty.hide()
        self.queue_box.insertWidget(self.queue_box.count() - 1, row)   # antes del espacio final
        self._rows += 1

    def remove_row(self, row: QueueRow):
        self.queue_box.removeWidget(row)
        row.deleteLater()
        self._rows -= 1
        self.queue_empty.setVisible(self._rows == 0)

    def add_log(self, msg: str):
        self.log.appendPlainText(msg)
