"""Genera icon.png y 'YT Music Downloader.app' (lanzador de doble clic). Ejecutar una vez."""
import os, plistlib, shutil, stat, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "YT Music Downloader.app")


def make_icon(path):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPolygonF
    QGuiApplication.instance() or QGuiApplication(["x"])
    n = 1024
    img = QImage(n, n, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    path_ = QPainterPath()
    path_.addRoundedRect(60, 60, n - 120, n - 120, 200, 200)
    p.fillPath(path_, QColor("#ff3d5a"))
    p.setBrush(QColor("white")); p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(400, 700), 130, 105)               # cabeza de la nota
    p.drawRect(500, 250, 62, 450)                            # plica
    p.drawPolygon(QPolygonF([QPointF(562, 250), QPointF(760, 380), QPointF(760, 480), QPointF(562, 360)]))
    p.end()
    img.save(path)


def main():
    if sys.platform != "darwin":
        sys.exit("make_app.py solo sirve en macOS. En Windows usa run.bat.")
    icon_png = os.path.join(HERE, "icon.png")
    make_icon(icon_png)

    shutil.rmtree(APP, ignore_errors=True)
    macos = os.path.join(APP, "Contents", "MacOS")
    res = os.path.join(APP, "Contents", "Resources")
    os.makedirs(macos); os.makedirs(res)

    iconset = os.path.join(HERE, "icon.iconset")
    os.makedirs(iconset, exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = size * scale
            out = os.path.join(iconset, f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png")
            subprocess.run(["sips", "-z", str(px), str(px), icon_png, "--out", out],
                           check=True, capture_output=True)
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(res, "icon.icns")], check=True)
    shutil.rmtree(iconset)

    launcher = os.path.join(macos, "launcher")
    with open(launcher, "w") as f:
        f.write(f'''#!/bin/zsh
DIR={HERE!r}
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [ ! -d "$DIR" ]; then
  osascript -e 'display alert "No encuentro la carpeta del proyecto" message "¿Está conectado el disco SAMSUNG 4TB?"'
  exit 1
fi
cd "$DIR"
if [ ! -x .venv/bin/python ]; then      # primera vez: que se vea la instalación
  exec open -a Terminal "$DIR/run.command"
fi
exec .venv/bin/python app.py
''')
    os.chmod(launcher, os.stat(launcher).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    with open(os.path.join(APP, "Contents", "Info.plist"), "wb") as f:
        plistlib.dump({
            "CFBundleName": "YT Music Downloader", "CFBundleDisplayName": "YT Music Downloader",
            "CFBundleIdentifier": "io.github.ytmusicdownloader", "CFBundleExecutable": "launcher",
            "CFBundleIconFile": "icon", "CFBundlePackageType": "APPL", "CFBundleVersion": "1.0",
            "LSMinimumSystemVersion": "11.0", "NSHighResolutionCapable": True,
        }, f)
    subprocess.run(["touch", APP])
    print("Creada:", APP)


if __name__ == "__main__":
    main()
