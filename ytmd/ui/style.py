"""Colores, hoja de estilo e iconos (inspirado en el tema oscuro de YouTube Music)."""
from __future__ import annotations

import os
import sys

import qtawesome as qta
from PySide6.QtGui import QColor, QFont

from ytmd.i18n import tr



def file_manager() -> str:
    """Nombre del explorador de archivos del sistema, para los textos de la interfaz."""
    return {"darwin": "Finder", "win32": tr("Explorer")}.get(sys.platform, tr("the file manager"))


BG = "#030303"
SIDEBAR = "#0a0a0a"
SURFACE = "#212121"
HOVER = "rgba(255,255,255,0.10)"
TEXT = "#ffffff"
MUTED = "#aaaaaa"
ACCENT = "#ff0033"

C_TEXT = QColor(TEXT)
C_MUTED = QColor(MUTED)
C_ACCENT = QColor(ACCENT)
C_HOVER = QColor(255, 255, 255, 22)
C_SELECTED = QColor(255, 255, 255, 40)


def _chevron_path() -> str:
    """Flecha de los desplegables: Qt solo acepta un fichero de imagen, así que se genera."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chevron-down.png")
    if not os.path.isfile(path):
        from PySide6.QtWidgets import QApplication
        if QApplication.instance():
            qta.icon("mdi6.chevron-down", color=MUTED).pixmap(28, 28).save(path)
    return path.replace("\\", "/")


def icon(name: str, color: str = TEXT, **kw):
    return qta.icon(f"mdi6.{name}", color=color, color_disabled="#555555", **kw)


def font(size: int, weight: QFont.Weight = QFont.Normal) -> QFont:
    f = QFont()
    f.setPixelSize(size)
    f.setWeight(weight)
    return f


def stylesheet() -> str:
    return STYLE.replace("{CHEVRON}", _chevron_path())


STYLE = f"""
* {{ color: {TEXT}; font-size: 14px; }}
QMainWindow, #root {{ background: {BG}; }}
QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid #333; padding: 4px 6px; }}

/* ---- barra lateral ---- */
#sidebar {{ background: {SIDEBAR}; border-right: 1px solid #1f1f1f; }}
#logo {{ font-size: 20px; font-weight: 800; letter-spacing: -0.5px; }}
#nav {{ background: transparent; border: none; border-radius: 8px; text-align: left;
        padding: 10px 14px; font-size: 15px; }}
#nav:hover {{ background: {HOVER}; }}
#nav:checked {{ background: rgba(255,255,255,0.14); font-weight: 600; }}
#pill {{ background: #212121; border: none; border-radius: 17px; min-height: 34px; padding: 0 16px; font-weight: 600; }}
#pill:hover {{ background: #303030; }}
#sep {{ background: #2a2a2a; max-height: 1px; min-height: 1px; margin: 6px 4px; }}

/* ---- listas ---- */
QListView, QListWidget {{ background: transparent; border: none; outline: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #4a4a4a; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #6a6a6a; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; height: 0; }}
QScrollBar:horizontal {{ height: 0; }}

/* ---- campos ---- */
QLineEdit, QPlainTextEdit, QComboBox {{
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.10);
    border-radius: 8px; padding: 8px 12px; selection-background-color: {ACCENT};
}}
QLineEdit:focus, QPlainTextEdit:focus {{ border-color: rgba(255,255,255,0.35); }}
#search {{ min-height: 24px; border-radius: 8px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url("{{CHEVRON}}"); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; border: 1px solid #333;
    selection-background-color: rgba(255,255,255,0.15); padding: 4px; }}
QCheckBox {{ spacing: 8px; color: {MUTED}; }}
QCheckBox:checked {{ color: {TEXT}; }}

/* ---- botones ----
   Los redondos necesitan su tamaño exacto aquí: si no, Qt ignora el border-radius. */
QPushButton {{ background: rgba(255,255,255,0.10); border: none; border-radius: 16px;
    min-height: 32px; padding: 0 16px; font-weight: 600; }}
QPushButton:hover {{ background: rgba(255,255,255,0.18); }}
QPushButton:disabled {{ color: #666; }}
#primary {{ background: {TEXT}; color: #000; }}
#primary:hover {{ background: #dddddd; }}
#accent {{ background: {ACCENT}; color: {TEXT}; }}
#accent:hover {{ background: #ff3355; }}
#chip {{ background: rgba(255,255,255,0.10); border-radius: 8px; padding: 7px 12px; font-weight: 500; }}
#chip:hover {{ background: rgba(255,255,255,0.18); }}
#chip:checked {{ background: {TEXT}; color: #000; }}
#iconbtn {{ background: transparent; border-radius: 17px; padding: 0; min-height: 0; }}
#iconbtn:hover {{ background: {HOVER}; }}
#iconbtn:checked {{ background: transparent; }}
#roundbtn {{ background: rgba(255,255,255,0.10); border-radius: 22px; padding: 0;
    min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; }}
#roundbtn:hover {{ background: rgba(255,255,255,0.20); }}
#bigplay {{ background: {TEXT}; border-radius: 32px; padding: 0;
    min-width: 64px; max-width: 64px; min-height: 64px; max-height: 64px; }}
#bigplay:hover {{ background: #e6e6e6; }}

/* ---- textos ---- */
#h1 {{ font-size: 30px; font-weight: 800; }}
#h2 {{ font-size: 22px; font-weight: 700; }}
#coltitle {{ font-size: 28px; font-weight: 800; }}
#muted {{ color: {MUTED}; }}
#small {{ color: {MUTED}; font-size: 12px; }}
#tag {{ background: rgba(255,255,255,0.12); border-radius: 4px; padding: 1px 6px;
    font-size: 11px; font-weight: 700; color: {MUTED}; }}

/* ---- árbol de la ventana de importar ---- */
QDialog#root {{ background: {SURFACE}; }}
QTreeWidget {{ background: rgba(255,255,255,0.04); border: none; border-radius: 10px; outline: none;
    padding: 4px; }}
QTreeWidget::item {{ padding: 5px 2px; }}
QTreeWidget::item:hover {{ background: rgba(255,255,255,0.06); }}
QTreeWidget::item:selected {{ background: rgba(255,255,255,0.12); color: {TEXT}; }}
QTreeWidget::item:disabled {{ color: #666666; }}
QHeaderView::section {{ background: transparent; color: {MUTED}; border: none;
    border-bottom: 1px solid #333; padding: 6px 4px; font-weight: 600; }}

/* ---- banner de versión nueva ---- */
#banner {{ background: #1f2a44; border-radius: 0; }}
#banner QLabel {{ color: {TEXT}; }}

/* ---- bienvenida y primeros pasos ---- */
#hero {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2a0f17, stop:0.65 #141414);
    border: 1px solid #2c2c2c; border-radius: 14px; }}
#step {{ background: rgba(255,255,255,0.05); border-radius: 12px; }}
#stepnum {{ color: {ACCENT}; font-weight: 700; font-size: 13px; }}
#guidecard {{ background: rgba(255,255,255,0.05); border-radius: 12px; }}
#guideicon {{ background: rgba(255,255,255,0.10); border-radius: 22px; }}
#guideicon[done="true"] {{ background: rgba(62,196,109,0.16); }}
#warn {{ background: #2b1e08; border: 1px solid #5a3e10; border-radius: 10px; }}
#warn QLabel {{ color: #f3c27a; }}

/* ---- tarjetas y cola ---- */
#panel {{ background: rgba(255,255,255,0.05); border-radius: 12px; }}
#queuerow {{ background: rgba(255,255,255,0.05); border-radius: 10px; }}
#dropline {{ background: {ACCENT}; border-radius: 1px; }}
QProgressBar {{ background: rgba(255,255,255,0.12); border: none; border-radius: 2px; max-height: 4px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}

/* ---- barra del reproductor ---- */
#playerbar {{ background: {SURFACE}; }}
#volume::groove:horizontal {{ height: 3px; background: rgba(255,255,255,0.25); border-radius: 1px; }}
#volume::sub-page:horizontal {{ background: {TEXT}; border-radius: 1px; }}
#volume::handle:horizontal {{ background: {TEXT}; width: 10px; height: 10px; margin: -4px 0; border-radius: 5px; }}
"""
