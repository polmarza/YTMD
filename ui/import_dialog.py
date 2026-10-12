"""Ventana «Importar desde mi cuenta»: elige qué listas y álbumes de YouTube Music descargar."""
from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout,
)

import importer
import library
from ui import style

# MB aproximados por canción (~4 min) según el formato, para avisar del espacio
MB_PER_SONG = {"FLAC": 25, "WAV": 40, "MP3": 9, "Original": 4}


class _Fetcher(QObject):
    done = Signal(object, str)          # (lista de RemoteItem, error)

    def __init__(self, browser: str):
        super().__init__()
        self.browser = browser

    @Slot()
    def run(self):
        try:
            self.done.emit(importer.fetch_library(self.browser), "")
        except Exception as e:  # noqa: BLE001 - se muestra en la ventana
            traceback.print_exc()
            self.done.emit([], str(e))


def _norm(s: str) -> str:
    return library._norm(s)


class ImportDialog(QDialog):
    def __init__(self, parent, browser: str, collections: list[library.Collection], format_name: str):
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle("Importar desde YouTube Music")
        self.resize(820, 680)
        self.urls: list[str] = []
        self.mb = next((v for k, v in MB_PER_SONG.items() if format_name.startswith(k)), 25)
        # para reconocer lo que ya tienes: por id de origen, por enlace o por título
        self.local_by_id = {c.source: c for c in collections if c.source}
        self.local_by_url = {c.url: c for c in collections if c.url}
        self.local_by_title = {_norm(c.title): c for c in collections if c.kind in ("album", "playlist")}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(QLabel("Importar desde YouTube Music", objectName="h2"))
        self.info = QLabel(f"Leyendo tu biblioteca con la sesión de {browser}…", objectName="muted",
                           wordWrap=True)
        lay.addWidget(self.info)
        self.busy = QProgressBar(textVisible=False, maximum=0)     # indeterminada mientras carga
        lay.addWidget(self.busy)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Nombre", "Detalle", "Canciones", "En tu biblioteca"])
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setTextElideMode(Qt.ElideRight)
        h = self.tree.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.Stretch)          # el nombre se lleva el sitio que sobre
        h.setSectionResizeMode(1, QHeaderView.Interactive)
        h.resizeSection(1, 230)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.Interactive)
        h.resizeSection(3, 150)
        self.tree.itemChanged.connect(self._update_summary)
        self.tree.hide()
        lay.addWidget(self.tree, 1)

        row = QHBoxLayout()
        self.btn_new = QPushButton("Marcar lo que no tengo")
        self.btn_new.clicked.connect(self._check_new)
        self.btn_none = QPushButton("Desmarcar todo")
        self.btn_none.clicked.connect(lambda: self._set_all(Qt.Unchecked))
        row.addWidget(self.btn_new)
        row.addWidget(self.btn_none)
        row.addStretch(1)
        lay.addLayout(row)

        self.summary = QLabel("", objectName="muted", wordWrap=True)
        lay.addWidget(self.summary)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("Añadir a la cola", objectName="primary")
        self.btn_ok.setEnabled(False)
        self.btn_ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(self.btn_ok)
        lay.addLayout(row)
        for b in (self.btn_new, self.btn_none):
            b.setEnabled(False)

        # El hilo cuelga de la ventana principal, no de este diálogo: si lo cierras mientras
        # aún lee, el hilo termina por su cuenta en vez de destruirse a medias.
        thread = QThread(parent)
        fetcher = _Fetcher(browser)
        thread._fetcher = fetcher                   # mantiene vivo el objeto mientras trabaja
        fetcher.moveToThread(thread)
        thread.started.connect(fetcher.run)
        fetcher.done.connect(self._loaded)          # método de la ventana: llega al hilo de la interfaz
        fetcher.done.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    # ------------------------------------------------------------ carga
    def _local(self, it: importer.RemoteItem) -> library.Collection | None:
        for key in (it.id, *it.alt_ids):
            if key in self.local_by_id:
                return self.local_by_id[key]
        return self.local_by_url.get(it.url) or self.local_by_title.get(_norm(it.title))

    @Slot(object, str)
    def _loaded(self, items: list, error: str):
        self.busy.hide()
        if error:
            self.info.setText(f"No se pudo leer tu biblioteca: {error}")
            return
        self.tree.blockSignals(True)
        groups = {}
        for kind, label in (("playlist", "Listas"), ("album", "Álbumes")):
            g = QTreeWidgetItem([label])
            g.setFlags(g.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            g.setCheckState(0, Qt.Unchecked)
            g.setFont(0, style.font(14, QFont.Bold))
            self.tree.addTopLevelItem(g)
            groups[kind] = g
        for it in items:
            local = self._local(it)
            count = "" if it.count is None else str(it.count)
            have = ""
            if local:
                have = f"Sí · {len(local.tracks)} canciones"
            elif not it.supported:
                have = "No compatible"
            row = QTreeWidgetItem([it.title, it.subtitle, count, have])
            row.setData(0, Qt.UserRole, it)
            row.setData(0, Qt.UserRole + 1, bool(local))
            row.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
            if it.supported:
                row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
                row.setCheckState(0, Qt.Unchecked)
                if local:
                    row.setToolTip(0, "Ya la tienes: si la marcas, solo se descargará lo nuevo.")
            else:
                row.setFlags(row.flags() & ~Qt.ItemIsEnabled & ~Qt.ItemIsUserCheckable)
                row.setToolTip(0, "YouTube no deja leer este tipo de lista automática (Recaps, listas "
                                  "de YouTube Music, mixes). Truco: añade sus canciones a una lista tuya.")
            if it.id == "LM":
                row.setText(0, "Música que me gusta")
            groups[it.kind].addChild(row)
        for kind, g in groups.items():
            g.setText(0, f"{g.text(0)} ({g.childCount()})")
            g.setExpanded(True)
        self.tree.blockSignals(False)
        self.tree.show()
        n_pl = groups["playlist"].childCount()
        n_al = groups["album"].childCount()
        self.info.setText(
            f"{n_pl} listas y {n_al} álbumes en tu cuenta. Marca lo que quieras descargar: "
            "las canciones que ya tengas no se vuelven a bajar (si están en otra carpeta, "
            "la lista las enlaza).")
        for b in (self.btn_new, self.btn_none):
            b.setEnabled(True)
        self._update_summary()

    # ------------------------------------------------------------ selección
    def _rows(self):
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            for j in range(g.childCount()):
                yield g.child(j)

    def _selected(self) -> list[importer.RemoteItem]:
        return [r.data(0, Qt.UserRole) for r in self._rows()
                if r.flags() & Qt.ItemIsUserCheckable and r.checkState(0) == Qt.Checked]

    def _set_all(self, state):
        self.tree.blockSignals(True)
        for r in self._rows():
            if r.flags() & Qt.ItemIsUserCheckable:
                r.setCheckState(0, state)
        self.tree.blockSignals(False)
        self._update_summary()

    def _check_new(self):
        """Marca lo que aún no está en tu biblioteca (salvo «Música que me gusta», que es enorme)."""
        self.tree.blockSignals(True)
        for r in self._rows():
            if r.flags() & Qt.ItemIsUserCheckable:
                it = r.data(0, Qt.UserRole)
                new = not r.data(0, Qt.UserRole + 1) and it.id != "LM"
                r.setCheckState(0, Qt.Checked if new else Qt.Unchecked)
        self.tree.blockSignals(False)
        self._update_summary()

    def _update_summary(self, *_):
        sel = self._selected()
        self.btn_ok.setEnabled(bool(sel))
        self.btn_ok.setText(f"Añadir {len(sel)} a la cola" if sel else "Añadir a la cola")
        if not sel:
            self.summary.setText("")
            return
        known = sum(it.count or 0 for it in sel)
        unknown = sum(1 for it in sel if it.count is None)
        text = f"{len(sel)} seleccionadas · {known} canciones"
        if unknown:
            text += f" + {unknown} sin recuento (YouTube no da el nº de canciones de los álbumes)"
        gb = known * self.mb / 1024
        if known:
            text += f" · hasta ~{gb:.1f} GB (menos si ya tienes parte)"
        if known > 300:
            text += ("\n⚠ Son muchas: tardará horas. Usa pausas «Segura» y deja que la cola vaya "
                     "haciendo; puedes pausarla cuando quieras.")
        self.summary.setText(text)

    def _accept(self):
        self.urls = [it.url for it in self._selected()]
        self.accept()
