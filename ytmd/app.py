"""Ventana principal de YT Music Downloader. Se arranca con el `app.py` de la raíz del proyecto."""
from __future__ import annotations

import json
import os
import random
import time
import subprocess
import sys
import traceback
from dataclasses import asdict, dataclass, fields

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg*=false")

from PySide6.QtCore import (
    QLibraryInfo, QObject, QProcess, QSettings, QSize, Qt, QThread, QTimer, QTranslator, QUrl, Signal, Slot,
)
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QKeySequence, QPalette, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from ytmd import i18n
from ytmd import library
from ytmd import onboarding
from ytmd import updater
from ytmd.downloader import (
    DEFAULT_FORMAT, DEFAULT_PAUSE, NO_BROWSER, PAUSES, Callbacks, Downloader, Options, Result, migrate,
)
from ytmd.i18n import tr, trn
from ytmd.version import GITHUB_REPO, __version__
from ytmd.ui import style
from ytmd.ui.covers import Covers
from ytmd.ui.import_dialog import ImportDialog
from ytmd.ui.pages import CollectionPage, DownloadsPage, HomePage, SettingsPage
from ytmd.ui.widgets import ROLE, PlayerBar, QueueRow, SidebarDelegate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # carpeta del proyecto


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
# YTMD_PROFILE permite pruebas con ajustes aparte, sin tocar los tuyos
PROFILE = os.environ.get("YTMD_PROFILE", "YTMusicDownloader")


def set_combo(combo, data):
    """Selecciona en un desplegable el elemento con ese dato (si existe)."""
    i = combo.findData(data)
    if i >= 0:
        combo.setCurrentIndex(i)


def relaunch():
    """Abre otra copia de la app (para cambiar de idioma o aplicar una actualización)."""
    QProcess.startDetached(sys.executable, sys.argv)


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
        self.settings = QSettings("polmarza", PROFILE)
        self.covers = Covers(self.devicePixelRatioF() or 2.0)
        pal = QApplication.instance().palette()          # enlaces de texto en el rojo de la app
        pal.setColor(QPalette.Link, QColor(style.ACCENT))
        QApplication.instance().setPalette(pal)
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

        self._tasks: list[QThread] = []
        self._manual_check = False
        self._build()
        self._wire_player()
        self._load_settings()
        self.rescan()
        self._restore_queue()
        self.settings_page.set_versions(__version__, updater.ytdlp_version())
        self._check_tools()
        QTimer.singleShot(3000, self.check_updates)      # sin molestar al arrancar

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
        self.settings_page = SettingsPage()
        self.stack = QStackedWidget()
        for page in (self.home, self.colpage, self.downloads, self.settings_page):
            self.stack.addWidget(page)
        right = QVBoxLayout()
        right.setSpacing(0)
        right.addWidget(self._build_banner())
        right.addWidget(self.stack, 1)
        main.addLayout(right, 1)

        self.bar = PlayerBar(self.covers)
        outer.addWidget(self.bar)

        # señales de las páginas
        self.home.open_collection.connect(self.open_collection)
        self.home.play_collection.connect(self.play_collection)
        self.home.download_url.connect(self.download_from_home)
        self.home.import_requested.connect(self.import_from_account)
        self.home.sample_requested.connect(self.download_sample)
        self.home.recheck_requested.connect(self._check_tools)
        g = self.home.guide
        g.use_folder.connect(self.confirm_folder)
        g.change_folder.connect(self.choose_dir)
        g.choose_browser.connect(self.choose_browser)
        g.try_sample.connect(self.download_sample)
        g.open_import.connect(self.import_from_account)
        g.hide_requested.connect(self.hide_guide)
        self.colpage.play_requested.connect(self.play_list)
        self.colpage.shuffle_requested.connect(self.play_shuffled)
        self.colpage.kind_changed.connect(self.change_kind)
        self.colpage.update_requested.connect(self.update_collection)
        self.colpage.reveal_requested.connect(self.reveal)
        self.colpage.tracks.toggle_requested.connect(self.toggle_play)
        self.downloads.enqueue.connect(self.enqueue)
        self.downloads.import_requested.connect(self.import_from_account)
        sp = self.settings_page
        sp.check_updates.connect(lambda: self.check_updates(manual=True))
        sp.apply_update.connect(self.apply_update)
        sp.update_ytdlp.connect(self.update_ytdlp)
        sp.language_selected.connect(self.change_language)
        sp.restart_requested.connect(self.restart)
        sp.show_guide.connect(self.show_guide)
        self.downloads.cmb_browser.currentIndexChanged.connect(lambda _i: self._refresh_guide())
        self.downloads.pause_toggled.connect(self._set_queue_paused)
        self.downloads.clear_finished.connect(self.clear_finished)
        self.downloads.choose_dir.connect(self.choose_dir)
        self.downloads.open_dir.connect(lambda: open_folder(self.out_dir))

        QShortcut(QKeySequence(Qt.Key_Space), self, self.toggle_play)
        QShortcut(QKeySequence.Find, self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+D"), self, self.go_downloads)

    def _build_banner(self) -> QWidget:
        """Aviso de versión nueva, arriba del contenido. Oculto hasta que haya una."""
        self.banner = QFrame(objectName="banner")
        row = QHBoxLayout(self.banner)
        row.setContentsMargins(40, 8, 20, 8)
        self.banner_label = QLabel()
        row.addWidget(self.banner_label, 1)
        self.banner_open = QPushButton(tr("See what's new"))
        self.banner_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self._release.url)))
        row.addWidget(self.banner_open)
        update = QPushButton(tr("Update"))
        update.clicked.connect(lambda: self.go("settings"))
        row.addWidget(update)
        close = QPushButton(tr("Not now"))
        close.clicked.connect(self._dismiss_banner)
        row.addWidget(close)
        self.banner.hide()
        self._release: updater.Release | None = None
        return self.banner

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
        logo.addWidget(QLabel(tr("My Music"), objectName="logo"))
        logo.addStretch(1)
        lay.addLayout(logo)

        self.nav = QButtonGroup(self)
        self.nav_buttons = {}
        for key, label, ic in (("home", tr("Home"), "home-outline"), ("songs", tr("Songs"), "music-note"),
                               ("downloads", tr("Downloads"), "download"), ("settings", tr("Settings"), "cog-outline")):
            b = QPushButton(f"  {label}", objectName="nav", checkable=True)
            b.setIcon(style.icon(ic))
            b.setIconSize(QSize(22, 22))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav.addButton(b)
            self.nav_buttons[key] = b
            lay.addWidget(b)

        lay.addWidget(QFrame(objectName="sep"))
        add = QPushButton("  " + tr("Download"), objectName="pill")
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
        self.stack.setCurrentWidget({"home": self.home, "downloads": self.downloads,
                                     "settings": self.settings_page}[key])
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
        self._refresh_guide()
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
        self.downloads.add_log(tr("Updating «{title}»…", title=c.title))
        self._pump()

    # ------------------------------------------------------------ ajustes
    def _load_settings(self):
        s = self.settings
        d = self.downloads
        # Primera vez = sin carpeta guardada: se pregunta dónde guardar la música y se enseña la guía.
        # Quien ya usaba la app no necesita la guía.
        first_run = not s.contains("out_dir")
        self.folder_confirmed = s.value("folder_confirmed", not first_run, type=bool)
        if not first_run and not s.contains("guide_hidden"):
            s.setValue("guide_hidden", True)
        self.out_dir = s.value("out_dir", DEFAULT_DIR)
        d.set_dir(self.out_dir)
        # los ajustes de versiones anteriores guardaban el texto en español: migrate() lo convierte
        set_combo(d.cmb_format, migrate(s.value("format", DEFAULT_FORMAT)))
        set_combo(d.cmb_browser, migrate(s.value("browser", NO_BROWSER)))
        set_combo(d.cmb_pause, migrate(s.value("pause", DEFAULT_PAUSE)))
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
        s.setValue("folder_confirmed", self.folder_confirmed)
        s.setValue("format", d.cmb_format.currentData())
        s.setValue("browser", d.cmb_browser.currentData())
        s.setValue("pause", d.cmb_pause.currentData())
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
            out_dir=self.out_dir, format_name=d.cmb_format.currentData(),
            browser=d.cmb_browser.currentData(), pause=d.cmb_pause.currentData(),
            compat_44k=d.chk_44k.isChecked(), ascii_names=d.chk_ascii.isChecked(),
            cover_file=d.chk_cover.isChecked(), skip_existing=d.chk_skip.isChecked())

    def choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, tr("Music folder"), self.out_dir)
        if d:
            self.out_dir = d
            self.downloads.set_dir(d)
            self.folder_confirmed = True
            self.settings.setValue("folder_confirmed", True)
            self.settings.setValue("out_dir", d)
            self.rescan()

    def closeEvent(self, e):
        self._save_settings()
        self._save_queue()
        if self.worker:
            self.worker.cancel()
        if self.thread:
            self.thread.quit()
            self.thread.wait(5000)
        for t in list(self._tasks):
            t.quit()
            t.wait(3000)
        super().closeEvent(e)

    # ------------------------------------------------------------ actualizaciones
    def _run_task(self, fn, slot):
        """Ejecuta `fn` en un hilo; `slot` (método de la ventana) recibe (resultado, error)."""
        thread = QThread(self)
        task = updater.Task(fn)
        thread._task = task                  # mantiene vivo el objeto mientras trabaja
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.done.connect(slot)
        task.done.connect(thread.quit)
        thread.finished.connect(lambda t=thread: self._tasks.remove(t))
        thread.finished.connect(thread.deleteLater)
        self._tasks.append(thread)
        thread.start()

    def check_updates(self, manual: bool = False):
        """Busca una versión nueva en GitHub. Sola: como mucho una vez al día."""
        sp = self.settings_page
        if not GITHUB_REPO:
            if manual:
                sp.set_app_status(tr("This copy has no repository configured (GITHUB_REPO in ytmd/version.py)."))
            return
        now = time.time()
        if not manual and now - self.settings.value("last_update_check", 0, type=float) < 86400:
            return
        self._manual_check = manual
        if manual:
            sp.set_app_status(tr("Checking…"))
        self.settings.setValue("last_update_check", now)
        self._run_task(lambda: updater.latest_release(GITHUB_REPO), self._on_update_checked)

    @Slot(object, str)
    def _on_update_checked(self, rel: updater.Release | None, error: str):
        sp = self.settings_page
        manual, self._manual_check = self._manual_check, False
        if error:
            if manual:
                sp.set_app_status(tr("Couldn't check: {error}", error=error))
            return
        if rel is None or not updater.is_newer(rel.tag, __version__):
            sp.hide_offer()
            if manual:
                sp.set_app_status(tr("You're up to date (version {version}).", version=__version__))
            return
        self._release = rel
        sp.offer_update(rel.tag, updater.is_git_checkout())
        sp.set_app_status(tr("Version {tag} is available.", tag=rel.tag))
        if not manual and self.settings.value("dismissed_version", "") == rel.tag:
            return                         # ya dijiste «ahora no» a esta versión
        self.banner_label.setText(tr("A new version is available: <b>{tag}</b> (you have {current}).",
                                     tag=rel.tag, current=__version__))
        self.banner.show()

    def _dismiss_banner(self):
        if self._release:
            self.settings.setValue("dismissed_version", self._release.tag)
        self.banner.hide()

    def _busy_downloading(self) -> bool:
        if self.running:
            self.settings_page.set_app_status(tr("Wait for the current download to finish before updating."))
        return self.running is not None

    def apply_update(self):
        """Actualiza la app (git pull) o, si no se instaló con git, abre la página de la versión."""
        if not updater.is_git_checkout():
            if self._release:
                QDesktopServices.openUrl(QUrl(self._release.url))
            return
        if self._busy_downloading():
            return
        self.settings_page.btn_apply.setEnabled(False)
        self.settings_page.set_app_status(tr("Updating…"))
        self._run_task(updater.update_app, self._on_app_updated)

    @Slot(object, str)
    def _on_app_updated(self, result, error: str):
        sp = self.settings_page
        sp.btn_apply.setEnabled(True)
        if error:
            sp.set_app_status(tr("Couldn't update: {error}", error=error))
            return
        old, new = result
        if old == new:
            sp.set_app_status(tr("Already up to date."))
            return
        sp.hide_offer()
        self.banner.hide()
        sp.set_app_status(tr("Updated ({old} → {new}). Restart to use the new version.", old=old, new=new))
        sp.show_restart()

    def update_ytdlp(self):
        if self._busy_downloading():
            return
        sp = self.settings_page
        sp.btn_ytdlp.setEnabled(False)
        sp.set_ytdlp_status(tr("Updating yt-dlp…"))
        self._run_task(updater.update_ytdlp, self._on_ytdlp_updated)

    @Slot(object, str)
    def _on_ytdlp_updated(self, result, error: str):
        sp = self.settings_page
        sp.btn_ytdlp.setEnabled(True)
        if error:
            sp.set_ytdlp_status(tr("Couldn't update yt-dlp: {error}", error=error))
            return
        before, after = result
        if before == after:
            sp.set_ytdlp_status(tr("yt-dlp is already on the latest version ({version}).", version=after))
        else:
            sp.set_ytdlp_status(tr("yt-dlp updated: {before} → {after}. Restart to use it.",
                                   before=before, after=after))
            sp.show_restart()

    # ------------------------------------------------------------ idioma y reinicio
    def change_language(self, code: str):
        if code == i18n.language():
            return
        busy = self.running is not None or self._pending()
        answer = QMessageBox.question(
            self, tr("Change language"),
            tr("The app will restart to apply the language.")
            + ("\n\n" + tr("The download queue will be kept, paused, so you can resume it.") if busy else ""),
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            self.settings_page.revert_language()
            return
        self.settings.setValue("language", code)
        self.restart()

    def restart(self):
        self.close()              # guarda ajustes y cola, y cancela lo que esté en marcha
        relaunch()
        QApplication.quit()

    # ------------------------------------------------------------ primeros pasos
    def _check_tools(self):
        self.home.set_missing(onboarding.missing_tools())

    def _refresh_guide(self):
        if not hasattr(self, "folder_confirmed"):
            return                       # aún construyendo la ventana
        done = {
            "folder": self.folder_confirmed,
            "browser": self.downloads.cmb_browser.currentData() != NO_BROWSER,
            "song": any(c.tracks for c in self.collections),
            "import": self.settings.value("imported", False, type=bool),
        }
        hidden = self.settings.value("guide_hidden", False, type=bool) or all(done.values())
        self.home.guide.setVisible(not hidden)
        if not hidden:
            self.home.guide.set_state(self.out_dir, done)

    def confirm_folder(self):
        os.makedirs(self.out_dir, exist_ok=True)
        self.folder_confirmed = True
        self.settings.setValue("folder_confirmed", True)
        self.settings.setValue("out_dir", self.out_dir)
        self._refresh_guide()

    def ensure_folder(self) -> bool:
        """La primera vez, antes de descargar nada, pregunta dónde guardar la música."""
        if self.folder_confirmed:
            return True
        box = QMessageBox(self)
        box.setWindowTitle(tr("Where should your music go?"))
        box.setText(tr("Choose the folder where your music will be saved."))
        box.setInformativeText(tr("Suggested: {path}", path=self.out_dir))
        use = box.addButton(tr("Use this folder"), QMessageBox.AcceptRole)
        other = box.addButton(tr("Choose another…"), QMessageBox.ActionRole)
        box.addButton(tr("Cancel"), QMessageBox.RejectRole)
        box.setDefaultButton(use)
        box.exec()
        if box.clickedButton() is use:
            self.confirm_folder()
        elif box.clickedButton() is other:
            self.choose_dir()
        return self.folder_confirmed

    def choose_browser(self):
        self.go("downloads")
        self.downloads.cmb_browser.setFocus()
        self.downloads.cmb_browser.showPopup()

    def download_from_home(self, url: str):
        if "youtube.com" not in url and "youtu.be" not in url:
            QMessageBox.information(self, tr("That's not a YouTube Music link"),
                                    tr("Paste a link from music.youtube.com: a song, an album or a playlist."))
            return
        if self.enqueue([url]):
            self.home.url.clear()
            self.go("downloads")

    def download_sample(self):
        if self.enqueue([onboarding.SAMPLE_URL]):
            self.downloads.add_log(tr("Sample song: {credit}", credit=onboarding.SAMPLE_CREDIT))
            self.go("downloads")

    def hide_guide(self):
        self.settings.setValue("guide_hidden", True)
        self._refresh_guide()

    def show_guide(self):
        self.settings.setValue("guide_hidden", False)
        self._refresh_guide()
        self.go("home")

    # ------------------------------------------------------------ importar
    def import_from_account(self):
        browser = self.downloads.cmb_browser.currentData()
        if browser == NO_BROWSER:
            QMessageBox.information(
                self, tr("Choose your browser"),
                tr("To read your library, choose in «Cookies» the browser where you're signed in to "
                   "YouTube Music (for example, chrome) and press Import again."))
            self.downloads.cmb_browser.setFocus()
            return
        self.settings.setValue("imported", True)
        self._refresh_guide()
        if not self.downloads.chk_skip.isChecked():
            self.downloads.chk_skip.setChecked(True)    # sin esto no se evitan los duplicados
            self.downloads.add_log(tr("«Skip already downloaded» turned on so songs aren't duplicated."))
        dlg = ImportDialog(self, browser, self.collections, self.downloads.cmb_format.currentData())
        if dlg.exec() and dlg.urls:
            self.enqueue(dlg.urls)

    # ------------------------------------------------------------ cola de descargas
    def enqueue(self, urls: list[str]) -> bool:
        if not self.ensure_folder():
            return False
        opts = self.current_options()
        for u in urls:
            self._add_job(u, Options(**asdict(opts)))   # cada trabajo guarda sus opciones
        self.downloads.add_log(tr("＋ {n} link(s) added to the queue", n=len(urls)))
        self._pump()
        return True

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
            job.row.set_state("running", tr("Cancelling…"))
            return
        self.jobs.remove(job)
        self.downloads.remove_row(job.row)
        self._refresh_queue_label()
        self._save_queue()

    def _retry_job(self, job: Job):
        job.state = "pending"
        job.row.set_state("pending", tr("Queued"))
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
                j.row.set_state("pending", tr("Queued"))
            self._refresh_queue_label()
        else:
            self._pump()

    def _pending(self) -> list[Job]:
        return [j for j in self.jobs if j.state == "pending"]

    def _refresh_queue_label(self):
        n = len(self._pending()) + (1 if self.running else 0)
        self.downloads.lbl_queue.setText("  " + trn(n, "{n} item pending", "{n} items pending")
                                         + (tr(" · paused") if self.queue_paused else ""))
        self.nav_buttons["downloads"].setText("  " + (tr("Downloads ({n})", n=n) if n else tr("Downloads")))

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
        job.row.set_state("running", tr("Analyzing link…"))
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
        job.row.set_state("running", trn(total, "{n} song", "{n} songs"))

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
            job.row.set_state("error", tr("Error: {error}", error=error.splitlines()[0][:160]))
            self.downloads.add_log("✖ " + error)
        elif res.cancelled:
            job.state = "cancelled"
            job.row.set_state("cancelled", tr("Cancelled · {n} downloaded", n=res.done))
        elif res.errors and not res.done:
            job.state = "error"
            job.row.set_state("error", tr("Couldn't download ({n} errors, see the log)", n=res.errors))
        else:
            job.state = "done"
            extra = tr(" · {n} with errors", n=res.errors) if res.errors else ""
            if res.already:
                extra += tr(" · {n} already in your library", n=res.already)
            job.row.set_state("done", tr("Done · {n} new", n=res.done) + extra)
        self._save_queue()
        self.rescan()

        if res.blocked:
            self.downloads.btn_pause.setChecked(True)     # pausa la cola
            QMessageBox.warning(
                self, tr("YouTube has throttled the downloads"),
                tr("YouTube has started rejecting requests (too many in a row).") + "\n\n" +
                tr("I've paused the queue. Wait a while (30–60 min), set the pauses to «Safe» "
                   "and resume: what's already downloaded is skipped."))
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
                nxt[0].row.set_state("pending", tr("Queued"))
            self._pump()
            return
        nxt[0].row.set_state("pending", tr("Starts in {secs} s (anti-block pause)", secs=self.wait_left))

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
            opts = {k: v for k, v in item["opts"].items() if k in names}
            for k in ("format_name", "browser", "pause"):        # colas guardadas con el texto antiguo
                if k in opts:
                    opts[k] = migrate(opts[k])
            self._add_job(item["url"], Options(**opts))
        if saved:
            # no arranca sola al abrir la app: que lo decidas tú
            self.downloads.btn_pause.setChecked(True)
            self.downloads.add_log(tr("Queue restored: {n} pending. Press «Resume».", n=len(saved)))

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
        self.player.errorOccurred.connect(lambda _e, msg: self.downloads.add_log(tr("✖ Player: {msg}", msg=msg)))

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
            self.downloads.add_log(tr("✖ Doesn't exist: {path}", path=t.path))
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
    # el idioma se fija antes de crear nada: los textos se traducen al construirlos
    i18n.set_language(QSettings("polmarza", PROFILE).value("language", i18n.DEFAULT))
    app = QApplication(sys.argv)
    app.setApplicationName("YT Music Downloader")
    if i18n.language() != "en":            # botones y diálogos estándar de Qt en el mismo idioma
        qt_tr = QTranslator(app)
        if qt_tr.load(f"qtbase_{i18n.language()}", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
            app.installTranslator(qt_tr)
    app.setStyleSheet(style.stylesheet())
    icon = os.path.join(ROOT, "assets", "icon.png")
    if os.path.isfile(icon):
        app.setWindowIcon(QIcon(icon))  # también cambia el icono del Dock en macOS
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
