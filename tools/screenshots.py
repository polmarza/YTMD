"""Takes the README screenshots from a demo library (see make_demo_library.py).

    python tools/make_demo_library.py /tmp/demo-library
    python tools/screenshots.py /tmp/demo-library docs/screenshots

Uses its own settings profile and fake data for the queue and the import window: it never touches
your settings, your library or your YouTube account.
"""
from __future__ import annotations

import os
import sys

os.environ["YTMD_PROFILE"] = "YTMusicDownloader-screenshots"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QPoint, QSettings  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ytmd import i18n  # noqa: E402

LANG = os.environ.get("YTMD_LANG", "en")
i18n.set_language(LANG)


def main(library_dir: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    settings = QSettings("polmarza", os.environ["YTMD_PROFILE"])
    settings.clear()
    settings.setValue("out_dir", library_dir)
    settings.setValue("browser", "chrome")

    app = QApplication(sys.argv)
    from ytmd import app as ytmd_app
    from ytmd import importer
    from ytmd.ui import style
    from ytmd.ui.import_dialog import ImportDialog
    from ytmd.ui.widgets import CardDelegate
    app.setStyleSheet(style.stylesheet())

    w = ytmd_app.MainWindow()
    w.resize(1400, 880)
    w.show()
    QTest.qWait(500)

    def shot(name: str, widget=None):
        QTest.qWait(400)
        (widget or w).grab().save(os.path.join(out_dir, f"{name}.png"))
        print("  ", name)

    by_title = {c.title: c for c in w.collections}

    # 1) Inicio, con una canción sonando y el botón de play de una portada
    w.play_list(by_title["Midnight Tides"].tracks, 2)
    w.go("home")
    QTest.qWait(300)
    grid = w.home.grid
    item = grid.item(1)
    QTest.mouseMove(grid.viewport(), CardDelegate.play_rect(grid.visualItemRect(item)).center())
    shot("home")

    # 2) Una lista (mosaico) con la fila que suena y otra con el ratón encima
    road = by_title["Road Trip"]
    w.open_collection(road)
    w.play_list(road.tracks, 2)
    lst = w.colpage.tracks
    r = lst.visualItemRect(lst.item(5))
    QTest.mouseMove(lst.viewport(), QPoint(r.left() + 300, r.center().y()))
    shot("playlist")

    # 3) Un álbum (números de pista)
    w.open_collection(by_title["Paper Lanterns"])
    QTest.mouseMove(w.bar, QPoint(5, 40))
    shot("album")

    # 4) Descargas con una cola de ejemplo (en pausa: no descarga nada)
    w.go("downloads")
    w.downloads.btn_pause.setChecked(True)
    w.enqueue(["https://music.youtube.com/playlist?list=demo1", "https://music.youtube.com/browse/demo2",
               "https://music.youtube.com/watch?v=demo3", "https://music.youtube.com/browse/demo4"])
    j = w.jobs
    j[0].row.set_info("Road Trip", "playlist")
    j[0].row.set_state("running", "7/16 · Neon Harbor - Golden Signals — Downloading… 6.2MiB/s")
    j[0].row.bar.setValue(420)
    j[1].row.set_info("Greenhouse Sessions", "album")
    j[1].row.set_state("done", "Done · 9 new · 1 already in your library")
    j[2].row.set_info("Paper Planes (Live)", "single")
    j[2].row.set_state("pending", "Starts in 6 s (anti-block pause)")
    j[3].row.set_state("pending", "Queued")
    w.downloads.urls.setPlainText("https://music.youtube.com/playlist?list=PL…")
    w.downloads.set_dir(os.path.expanduser("~/Music/YT Music"))   # no mostrar la ruta real de la demo
    shot("downloads")
    w.jobs.clear()

    # 5) Importar desde la cuenta, con datos inventados
    fake = [
        importer.RemoteItem("playlist", "LM", "Liked Music", "Automatic playlist", 1240, ""),
        importer.RemoteItem("playlist", "PL1", "Road Trip", "You", 16, "https://x/1"),
        importer.RemoteItem("playlist", "PL2", "Late Night Coding", "You", 42, "https://x/2"),
        importer.RemoteItem("playlist", "PL3", "Gym Hype", "You", 35, "https://x/3"),
        importer.RemoteItem("playlist", "LRSR1", "2025 Recap", "", None, "https://x/4"),
        importer.RemoteItem("album", "MPREb1", "Midnight Tides", "Album • Neon Harbor • 2023", None, "https://x/5"),
        importer.RemoteItem("album", "MPREb2", "Tidal Bloom", "Album • Coral Avenue • 2022", None, "https://x/6"),
        importer.RemoteItem("album", "MPREb3", "Low Orbit", "EP • Kite Theory • 2024", None, "https://x/7"),
    ]
    importer.fetch_library = lambda browser: fake
    dlg = ImportDialog(w, "chrome", w.collections, "flac")
    dlg.resize(820, 600)
    dlg.show()
    QTest.qWait(800)
    for row in dlg._rows():
        if row.text(0) in ("Late Night Coding", "Gym Hype", "Tidal Bloom", "Low Orbit"):
            row.setCheckState(0, row.checkState(0).Checked)
    dlg._update_summary()
    shot("import", dlg)
    dlg.reject()

    # 6) Configuración, con una versión nueva disponible
    w.go("settings")
    sp = w.settings_page
    sp.offer_update("v1.2.0", True)
    sp.set_app_status(i18n.tr("Version {tag} is available.", tag="v1.2.0"))
    shot("settings")

    w.player.stop()
    w.close()

    # 7) Primer arranque: biblioteca vacía, guía de primeros pasos y bienvenida
    import tempfile
    empty = tempfile.mkdtemp(prefix="ytmd-empty-")
    settings.clear()
    settings.setValue("out_dir", empty)
    settings.setValue("folder_confirmed", False)
    settings.setValue("guide_hidden", False)
    w = ytmd_app.MainWindow()
    w.resize(1400, 880)
    w.show()
    QTest.qWait(400)
    done = {"folder": False, "browser": False, "song": False, "import": False}
    w.home.guide.set_state(os.path.expanduser("~/Music/YT Music"), done)   # ruta genérica en la imagen
    shot("welcome")
    w.close()
    settings.clear()
    settings.sync()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "docs", "screenshots"))
