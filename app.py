"""YT Music Downloader + reproductor. Ejecuta: .venv/bin/python app.py"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import traceback
from dataclasses import asdict, dataclass, fields

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg*=false")

from PySide6.QtCore import QObject, QSettings, QSize, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

import library
from downloader import FORMATS, PAUSES, Callbacks, Downloader, Options, Result
from ui import style
from ui.covers import Covers
from ui.import_dialog import ImportDialog
from ui.pages import CollectionPage, DownloadsPage, HomePage
from ui.widgets import ROLE, PlayerBar, QueueRow, SidebarDelegate

HERE = os.path.dirname(os.path.abspath(__file__))


def open_folder(path: str):
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def reveal_in_file_manager(path: str):
    """Abre la carpeta con el archivo seleccionado (Finder / Explorador); en Linux, solo la carpeta."""
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", path])
    elif sys.platform == "win32":
        subprocess.run(["explorer", "/select,", os.path.normpath(path)])
    else:
        open_folder(os.path.dirname(path))
DEFAULT_DIR = os.path.expanduser("~/Music/YT Music")


# ---------------------------------------------------------------- descarga en hilo
class DownloadWorker(QObject):
    log = Signal(str)
    info = Signal(str, int, str)
    item = Signal(int, int, str)
    progress = Signal(float, str)
    done_item = Signal(str)
    finished = Signal(object, str)          # (Result, mensaje de error)

    def __init__(self, url: str, opts: Options):
        super().__init__()
        self.url = url
        self.dl = Downloader(opts, Callbacks(
            log=self.log.emit, info=self.info.emit, item=self.item.emit,
            progress=self.progress.emit, done_item=self.done_item.emit))

    @Slot()
    def run(self):
        try:
            self.finished.emit(self.dl.run(self.url), "")
        except Exception as e:  # noqa: BLE001 - se muestra en la interfaz
            traceback.print_exc()
            self.finished.emit(self.dl.result, str(e))

    def cancel(self):
        self.dl.cancel()


@dataclass
class Job:
    url: str
    opts: Options
    row: QueueRow
    state: str = "pending"      # pending | running | done | error | cancelled
    index: int = 1
    total: int = 1
    name: str = ""


# ---------------------------------------------------------------- ventana
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YT Music Downloader")
        self.resize(1360, 880)
        self.setMinimumSize(1000, 640)
        # YTMD_PROFILE permite pruebas con ajustes aparte, sin tocar los tuyos
        self.settings = QSettings("polmarza", os.environ.get("YTMD_PROFILE", "YTMusicDownloader"))
        self.covers = Covers(self.devicePixelRatioF() or 2.0)
        self.collections: list[library.Collection] = []
        self.all_col: library.Collection | None = None

        # reproductor
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.play_queue: list[library.Track] = []
        self.order: list[int] = []
        self.pos = -1
        self.shuffle = False
        self.repeat = "off"

        # cola de descargas
        self.jobs: list[Job] = []
        self.thread: QThread | None = None
        self.worker: DownloadWorker | None = None
        self.running: Job | None = None
        self.queue_paused = False
        self.wait_left = 0
        self.wait_timer = QTimer(self, interval=1000)
        self.wait_timer.timeout.connect(self._tick_wait)
        self.rescan_timer = QTimer(self, singleShot=True, interval=2500)
        self.rescan_timer.timeout.connect(self.rescan)

        self._build()
        self._wire_player()
        self._load_settings()
        self.rescan()
        self._restore_queue()

    # ------------------------------------------------------------ construcción
    def _build(self):
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        main = QHBoxLayout()
        main.setSpacing(0)
        outer.addLayout(main, 1)

        main.addWidget(self._build_sidebar())

        self.home = HomePage(self.covers)
        self.colpage = CollectionPage(self.covers)
        self.downloads = DownloadsPage()
        self.stack = QStackedWidget()
        for page in (self.home, self.colpage, self.downloads):
            self.stack.addWidget(page)
        main.addWidget(self.stack, 1)

        self.bar = PlayerBar(self.covers)
        outer.addWidget(self.bar)

        # señales de las páginas
        self.home.open_collection.connect(self.open_collection)
        self.home.play_collection.connect(self.play_collection)
        self.colpage.play_requested.connect(self.play_list)
        self.colpage.shuffle_requested.connect(self.play_shuffled)
        self.colpage.kind_changed.connect(self.change_kind)
        self.colpage.update_requested.connect(self.update_collection)
        self.colpage.reveal_requested.connect(self.reveal)
        self.colpage.tracks.toggle_requested.connect(self.toggle_play)
        self.downloads.enqueue.connect(self.enqueue)
        self.downloads.import_requested.connect(self.import_from_account)
        self.downloads.pause_toggled.connect(self._set_queue_paused)
        self.downloads.clear_finished.connect(self.clear_finished)
        self.downloads.choose_dir.connect(self.choose_dir)
        self.downloads.open_dir.connect(lambda: open_folder(self.out_dir))

        QShortcut(QKeySequence(Qt.Key_Space), self, self.toggle_play)
        QShortcut(QKeySequence.Find, self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+D"), self, self.go_downloads)

    def _build_sidebar(self) -> QWidget:
        side = QFrame(objectName="sidebar")
        side.setFixedWidth(250)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(10, 18, 10, 10)
        lay.setSpacing(4)

        logo = QHBoxLayout()
        logo.setContentsMargins(12, 0, 0, 12)
        mark = QLabel()
        mark.setPixmap(style.icon("music-circle", style.ACCENT).pixmap(30, 30))
        logo.addWidget(mark)
        logo.addWidget(QLabel("Mi Música", objectName="logo"))
        logo.addStretch(1)
        lay.addLayout(logo)

        self.nav = QButtonGroup(self)
        self.nav_buttons = {}
        for key, label, ic in (("home", "Inicio", "home-outline"), ("songs", "Canciones", "music-note"),
                               ("downloads", "Descargas", "download")):
            b = QPushButton(f"  {label}", objectName="nav", checkable=True)
            b.setIcon(style.icon(ic))
            b.setIconSize(QSize(22, 22))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav.addButton(b)
            self.nav_buttons[key] = b
            lay.addWidget(b)

        lay.addWidget(QFrame(objectName="sep"))
        add = QPushButton("  Descargar", objectName="pill")
        add.setIcon(style.icon("plus"))
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(self.go_downloads)
        lay.addSpacing(6)
        lay.addWidget(add)
        lay.addSpacing(10)

        self.side_list = QListWidget()
        self.side_list.setItemDelegate(SidebarDelegate(self.side_list))
        self.side_list.setMouseTracking(True)
        self.side_list.itemClicked.connect(lambda it: self.open_collection(it.data(ROLE)))
        lay.addWidget(self.side_list, 1)
        return side

    # ------------------------------------------------------------ navegación
    def go(self, key: str):
        if key == "songs":      # "Canciones" es una lista más: todas las canciones juntas
            self.open_collection(self.all_col)
            return
        self.stack.setCurrentWidget({"home": self.home, "downloads": self.downloads}[key])
        self._set_nav(key)
        self.side_list.clearSelection()

    def _set_nav(self, key: str | None):
        """Marca una sección del menú (o ninguna)."""
        self.nav.setExclusive(False)
        for b in self.nav_buttons.values():
            b.setChecked(False)
        self.nav.setExclusive(True)
        if key:
            self.nav_buttons[key].setChecked(True)

    def go_downloads(self):
        self.go("downloads")
        self.downloads.urls.setFocus()

    def open_collection(self, c: library.Collection | None):
        if c is None:
            return
        self.colpage.show_collection(c)
        self.colpage.tracks.set_playing(self.current_path(), self._is_playing())
        self.stack.setCurrentWidget(self.colpage)
        self._set_nav("songs" if c.kind == "all" else None)
        self.side_list.clearSelection()
        for i in range(self.side_list.count()):
            if self.side_list.item(i).data(ROLE).id == c.id:
                self.side_list.setCurrentRow(i)

    def _focus_search(self):
        box = getattr(self.stack.currentWidget(), "search", None)
        if box:
            box.setFocus()
            box.selectAll()

    def reveal(self, path: str):
        reveal_in_file_manager(path)

    # ------------------------------------------------------------ biblioteca
    def rescan(self):
        self.collections = cols = library.scan(self.out_dir)
        self.covers.clear()
        self.home.set_collections(cols)
        self.side_list.clear()
        for c in cols:
            it = QListWidgetItem()
            it.setData(ROLE, c)
            self.side_list.addItem(it)
        self.all_col = library.all_songs(cols, self.out_dir)
        self.colpage.tracks.set_playing(self.current_path(), self._is_playing())
        if self.stack.currentWidget() is self.colpage and self.colpage.col:
            shown = self.colpage.col
            same = self.all_col if shown.kind == "all" else next((c for c in cols if c.id == shown.id), None)
            if same:  # refresca la colección abierta sin perder scroll ni búsqueda
                bar = self.colpage.tracks.verticalScrollBar()
                pos, query = bar.value(), self.colpage.search.text()
                self.open_collection(same)
                self.colpage.search.setText(query)
                bar.setValue(pos)
            else:
                self.go("home")

    def change_kind(self, c: library.Collection, kind: str):
        library.update_meta(c.path, {"kind": kind})
        self.rescan()

    def update_collection(self, c: library.Collection):
        opts = self.current_options()
        opts.skip_existing = True        # actualizar = bajar solo lo nuevo
        self._add_job(c.url, opts)
        self.downloads.add_log(f"Actualizando «{c.title}»…")
        self._pump()

    # ------------------------------------------------------------ ajustes
    def _load_settings(self):
        s = self.settings
        d = self.downloads
        self.out_dir = s.value("out_dir", DEFAULT_DIR)
        d.set_dir(self.out_dir)
        d.cmb_format.setCurrentText(s.value("format", next(iter(FORMATS))))
        d.cmb_browser.setCurrentText(s.value("browser", "Ninguno"))
        d.cmb_pause.setCurrentText(s.value("pause", "Prudente (3–8 s)"))
        d.chk_44k.setChecked(s.value("compat_44k", True, type=bool))
        d.chk_ascii.setChecked(s.value("ascii", False, type=bool))
        d.chk_cover.setChecked(s.value("cover_file", True, type=bool))
        d.chk_skip.setChecked(s.value("skip", True, type=bool))
        self.bar.volume.setValue(s.value("volume", 80, type=int))
        self.audio.setVolume(self.bar.volume.value() / 100)
        self.bar.btn_shuffle.setChecked(s.value("shuffle", False, type=bool))
        self.repeat = s.value("repeat", "off")
        self.bar.set_repeat(self.repeat)
        if s.value("geometry"):
            self.restoreGeometry(s.value("geometry"))
        self.go("home")

    def _save_settings(self):
        s = self.settings
        d = self.downloads
        s.setValue("out_dir", self.out_dir)
        s.setValue("format", d.cmb_format.currentText())
        s.setValue("browser", d.cmb_browser.currentText())
        s.setValue("pause", d.cmb_pause.currentText())
        s.setValue("compat_44k", d.chk_44k.isChecked())
        s.setValue("ascii", d.chk_ascii.isChecked())
        s.setValue("cover_file", d.chk_cover.isChecked())
        s.setValue("skip", d.chk_skip.isChecked())
        s.setValue("volume", self.bar.volume.value())
        s.setValue("shuffle", self.shuffle)
        s.setValue("repeat", self.repeat)
        s.setValue("geometry", self.saveGeometry())

    def current_options(self) -> Options:
        d = self.downloads
        return Options(
            out_dir=self.out_dir, format_name=d.cmb_format.currentText(),
            browser=d.cmb_browser.currentText(), pause=d.cmb_pause.currentText(),
            compat_44k=d.chk_44k.isChecked(), ascii_names=d.chk_ascii.isChecked(),
            cover_file=d.chk_cover.isChecked(), skip_existing=d.chk_skip.isChecked())

    def choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de música", self.out_dir)
        if d:
            self.out_dir = d
            self.downloads.set_dir(d)
            self.rescan()

    def closeEvent(self, e):
        self._save_settings()
        self._save_queue()
        if self.worker:
            self.worker.cancel()
        if self.thread:
            self.thread.quit()
            self.thread.wait(5000)
        super().closeEvent(e)

    # ------------------------------------------------------------ importar
    def import_from_account(self):
        browser = self.downloads.cmb_browser.currentText()
        if browser == "Ninguno":
            QMessageBox.information(
                self, "Elige tu navegador",
                "Para leer tu biblioteca, elige en «Cookies» el navegador donde tienes abierta "
                "tu sesión de YouTube Music (por ejemplo, chrome) y vuelve a pulsar Importar.")
            self.downloads.cmb_browser.setFocus()
            return
        if not self.downloads.chk_skip.isChecked():
            self.downloads.chk_skip.setChecked(True)    # sin esto no se evitan los duplicados
            self.downloads.add_log("«Saltar ya descargadas» activado para no duplicar canciones.")
        dlg = ImportDialog(self, browser, self.collections, self.downloads.cmb_format.currentText())
        if dlg.exec() and dlg.urls:
            self.enqueue(dlg.urls)

    # ------------------------------------------------------------ cola de descargas
    def enqueue(self, urls: list[str]):
        opts = self.current_options()
        for u in urls:
            self._add_job(u, Options(**asdict(opts)))   # cada trabajo guarda sus opciones
        self.downloads.add_log(f"＋ {len(urls)} enlace(s) añadidos a la cola")
        self._pump()

    def _add_job(self, url: str, opts: Options) -> Job:
        row = QueueRow(url)
        job = Job(url, opts, row)
        row.remove.connect(lambda j=job: self._remove_job(j))
        row.retry.connect(lambda j=job: self._retry_job(j))
        self.jobs.append(job)
        self.downloads.add_row(row)
        self._refresh_queue_label()
        self._save_queue()
        return job

    def _remove_job(self, job: Job):
        if job is self.running:
            self.worker.cancel()
            job.row.set_state("running", "Cancelando…")
            return
        self.jobs.remove(job)
        self.downloads.remove_row(job.row)
        self._refresh_queue_label()
        self._save_queue()

    def _retry_job(self, job: Job):
        job.state = "pending"
        job.row.set_state("pending", "En cola")
        self._save_queue()
        self._pump()

    def clear_finished(self):
        for job in [j for j in self.jobs if j.state in ("done", "cancelled")]:
            self._remove_job(job)

    def _set_queue_paused(self, paused: bool):
        self.queue_paused = paused
        if paused:
            self.wait_timer.stop()
            for j in self._pending()[:1]:
                j.row.set_state("pending", "En cola")
            self._refresh_queue_label()
        else:
            self._pump()

    def _pending(self) -> list[Job]:
        return [j for j in self.jobs if j.state == "pending"]

    def _refresh_queue_label(self):
        n = len(self._pending()) + (1 if self.running else 0)
        self.downloads.lbl_queue.setText(f"  {n} pendiente{'s' if n != 1 else ''}"
                                         + (" · en pausa" if self.queue_paused else ""))
        self.nav_buttons["downloads"].setText(f"  Descargas ({n})" if n else "  Descargas")

    def _pump(self):
        """Arranca el siguiente trabajo si no hay ninguno en marcha ni esperando."""
        self._refresh_queue_label()
        if self.running or self.queue_paused or self.wait_timer.isActive():
            return
        pending = self._pending()
        if pending:
            self._start_job(pending[0])

    def _start_job(self, job: Job):
        self.running = job
        job.state = "running"
        job.index, job.total, job.name = 1, 1, ""
        job.row.set_state("running", "Analizando enlace…")
        job.row.bar.setValue(0)
        self.thread = QThread(self)
        self.worker = DownloadWorker(job.url, job.opts)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        # Solo métodos de la ventana: así Qt ejecuta cada aviso en el hilo de la interfaz.
        # (Una lambda se ejecutaría en el hilo de descarga y tocaría widgets desde ahí → cuelgue.)
        self.worker.log.connect(self.downloads.add_log)
        self.worker.info.connect(self._on_info)
        self.worker.item.connect(self._on_item)
        self.worker.progress.connect(self._on_progress)
        self.worker.done_item.connect(self._on_done_item)
        self.worker.finished.connect(self._on_finished)
        self._refresh_queue_label()
        self.thread.start()

    @Slot(str, int, str)
    def _on_info(self, title: str, total: int, kind: str):
        job = self.running
        job.total = total
        job.row.set_info(title, kind)
        job.row.set_state("running", f"{total} canción{'es' if total != 1 else ''}")

    @Slot(int, int, str)
    def _on_item(self, i: int, n: int, name: str):
        job = self.running
        job.index, job.total, job.name = i, n, name
        job.row.bar.setValue(int((i - 1) / max(n, 1) * 1000))
        job.row.status.setText(f"{i}/{n} · {name}" if n > 1 else name)

    @Slot(float, str)
    def _on_progress(self, pct: float, text: str):
        job = self.running
        job.row.bar.setValue(int(((job.index - 1) + pct / 100) / max(job.total, 1) * 1000))
        prefix = f"{job.index}/{job.total} · {job.name}" if job.total > 1 else job.name
        job.row.status.setText(f"{prefix} — {text}" if prefix else text)

    @Slot(str)
    def _on_done_item(self, _path: str):
        self.rescan_timer.start()   # refresca la biblioteca poco después, no en cada canción

    @Slot(object, str)
    def _on_finished(self, res: Result, error: str):
        job = self.running
        self.thread.quit()
        self.thread.wait()
        self.thread = self.worker = self.running = None
        if error:
            job.state = "error"
            job.row.set_state("error", f"Error: {error.splitlines()[0][:160]}")
            self.downloads.add_log("✖ " + error)
        elif res.cancelled:
            job.state = "cancelled"
            job.row.set_state("cancelled", f"Cancelado · {res.done} descargadas")
        elif res.errors and not res.done:
            job.state = "error"
            job.row.set_state("error", f"No se pudo descargar ({res.errors} errores, mira el registro)")
        else:
            job.state = "done"
            extra = f" · {res.errors} con error" if res.errors else ""
            job.row.set_state("done", f"Hecho · {res.done} nuevas{extra}")
        self._save_queue()
        self.rescan()

        if res.blocked:
            self.downloads.btn_pause.setChecked(True)     # pausa la cola
            QMessageBox.warning(
                self, "YouTube ha frenado las descargas",
                "YouTube ha empezado a rechazar peticiones (demasiadas seguidas).\n\n"
                "He pausado la cola. Espera un rato (30–60 min), pon las pausas en «Segura» "
                "y reanuda: lo ya descargado se salta.")
            return
        # pausa entre trabajos de la cola, igual que entre canciones
        lo, hi, _ = PAUSES.get(job.opts.pause, (0, 0, 0))
        if hi and self._pending() and not self.queue_paused:
            self.wait_left = int(random.uniform(lo, hi))
            self._tick_wait(first=True)
            self.wait_timer.start()
        else:
            self._pump()

    def _tick_wait(self, first: bool = False):
        nxt = self._pending()
        if not first:
            self.wait_left -= 1
        if self.wait_left <= 0 or not nxt:
            self.wait_timer.stop()
            if nxt:
                nxt[0].row.set_state("pending", "En cola")
            self._pump()
            return
        nxt[0].row.set_state("pending", f"Empieza en {self.wait_left} s (pausa anti-bloqueo)")

    def _save_queue(self):
        keep = [{"url": j.url, "opts": asdict(j.opts)} for j in self.jobs
                if j.state in ("pending", "running")]
        self.settings.setValue("queue", json.dumps(keep, ensure_ascii=False))

    def _restore_queue(self):
        try:
            saved = json.loads(self.settings.value("queue", "[]"))
        except (TypeError, ValueError):
            saved = []
        names = {f.name for f in fields(Options)}
        for item in saved:
            self._add_job(item["url"], Options(**{k: v for k, v in item["opts"].items() if k in names}))
        if saved:
            # no arranca sola al abrir la app: que lo decidas tú
            self.downloads.btn_pause.setChecked(True)
            self.downloads.add_log(f"Cola restaurada: {len(saved)} pendiente(s). Pulsa «Reanudar cola».")

    # ------------------------------------------------------------ reproductor
    def _wire_player(self):
        b = self.bar
        b.play_clicked.connect(self.toggle_play)
        b.next_clicked.connect(lambda: self.step(1, manual=True))
        b.prev_clicked.connect(self.prev)
        b.seek_to.connect(self.player.setPosition)
        b.volume_changed.connect(lambda v: self.audio.setVolume(v / 100))
        b.shuffle_toggled.connect(self.set_shuffle)
        b.repeat_changed.connect(lambda m: setattr(self, "repeat", m))
        b.open_current.connect(self._open_current_collection)
        self.player.positionChanged.connect(lambda ms: b.set_position(ms, self.player.duration()))
        self.player.durationChanged.connect(b.set_duration)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.errorOccurred.connect(lambda _e, msg: self.downloads.add_log("✖ Reproductor: " + msg))

    def _is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlayingState

    def _on_state(self, _state):
        self.bar.set_playing(self._is_playing())
        self.colpage.tracks.set_playing(self.current_path(), self._is_playing())

    def current(self) -> library.Track | None:
        if 0 <= self.pos < len(self.order):
            return self.play_queue[self.order[self.pos]]
        return None

    def current_path(self) -> str | None:
        t = self.current()
        return t.path if t else None

    def play_list(self, tracks: list, index: int):
        if not tracks:
            return
        self.play_queue = list(tracks)
        self._make_order(index)
        self._play_current()

    def play_collection(self, c: library.Collection):
        self.play_list(c.tracks, 0)

    def play_shuffled(self, tracks: list):
        if not tracks:
            return
        self.bar.btn_shuffle.setChecked(True)
        self.play_list(tracks, random.randrange(len(tracks)))

    def _make_order(self, start: int):
        n = len(self.play_queue)
        if self.shuffle:
            rest = [i for i in range(n) if i != start]
            random.shuffle(rest)
            self.order = [start] + rest
            self.pos = 0
        else:
            self.order = list(range(n))
            self.pos = start

    def set_shuffle(self, on: bool):
        self.shuffle = on
        if self.current() is not None:  # rehace el orden manteniendo la canción actual
            self._make_order(self.order[self.pos])

    def _play_current(self):
        t = self.current()
        if t is None:
            return
        if not os.path.isfile(t.path):
            self.downloads.add_log("✖ No existe: " + t.path)
            return
        self.player.setSource(QUrl.fromLocalFile(t.path))
        self.player.play()
        self.bar.set_track(t)
        self.colpage.tracks.set_playing(t.path, True)
        self.setWindowTitle(f"{t.title} · {t.main_artist}" if t.artist else t.title)

    def toggle_play(self):
        if self._is_playing():
            self.player.pause()
        elif self.current():
            self.player.play()
        else:  # nada en cola: lo que se esté viendo
            lst = getattr(self.stack.currentWidget(), "tracks", None)
            if lst is not None and lst.visible_tracks():
                self.play_list(lst.visible_tracks(), 0)

    def step(self, delta: int, manual: bool = False):
        if not self.order:
            return
        j = self.pos + delta
        if 0 <= j < len(self.order):
            self.pos = j
        elif self.repeat == "all" or manual:
            self.pos = j % len(self.order)
        else:
            self.player.stop()
            return
        self._play_current()

    def prev(self):
        if self.player.position() > 3000:  # como cualquier reproductor: primero vuelve al inicio
            self.player.setPosition(0)
        else:
            self.step(-1, manual=True)

    def _on_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            if self.repeat == "one":
                self.player.setPosition(0)
                self.player.play()
            else:
                self.step(1)

    def _open_current_collection(self):
        t = self.current()
        if t is not None:
            self.open_collection(next(
                (c for c in self.collections if any(x.path == t.path for x in c.tracks)), None))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("YT Music Downloader")
    app.setStyleSheet(style.stylesheet())
    icon = os.path.join(HERE, "icon.png")
    if os.path.isfile(icon):
        app.setWindowIcon(QIcon(icon))  # también cambia el icono del Dock en macOS
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
