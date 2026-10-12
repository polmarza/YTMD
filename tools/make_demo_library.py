"""Builds a fake music library (invented artists, generated covers, silent audio) for screenshots.

    python tools/make_demo_library.py /path/to/demo-library

Everything is made up: no real artists, artwork or audio, so the screenshots can be published.
Needs ffmpeg. The audio is silence (FLAC compresses it to a few KB), with realistic durations and tags.
"""
from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys

from mutagen.flac import FLAC, Picture
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen

ALBUMS = [
    ("Neon Harbor", "Midnight Tides", "2023", "waves", (210, 280)),
    ("Aurora Vale", "Paper Lanterns", "2021", "sun", (35, 330)),
    ("Low Tide Society", "Salt & Static", "2019", "stripes", (190, 20)),
    ("Marisol Quintero", "Tierra de Nadie", "2022", "circles", (15, 45)),
    ("Kite Theory", "Small Machines", "2020", "grid", (160, 200)),
    ("Velvet Static", "Afterglow FM", "2024", "sun", (300, 20)),
    ("Nordlys", "Polar Hours", "2018", "waves", (170, 260)),
    ("Cobalt Garden", "Greenhouse Sessions", "2025", "circles", (110, 70)),
    ("The Lantern Club", "Night Bus Home", "2017", "grid", (250, 330)),
    ("Rita Sol", "Calle Luna", "2016", "stripes", (40, 5)),
]
PLAYLISTS = ["Road Trip", "Focus Mode", "Sunday Morning"]
LOOSE = [("Kite Theory", "Paper Planes (Live)"), ("Aurora Vale", "First Light"), ("Nordlys", "Snowfall")]

WORDS_A = ["Golden", "Quiet", "Electric", "Silver", "Lost", "Velvet", "Hidden", "Broken", "Northern",
           "Paper", "Slow", "Wild", "Distant", "Little", "Burning", "Glass", "Summer", "Midnight"]
WORDS_B = ["Hours", "Lights", "Rivers", "Signals", "Engines", "Gardens", "Tides", "Echoes", "Letters",
           "Streets", "Maps", "Satellites", "Mornings", "Wires", "Horizons", "Bridges", "Radios"]


def cover(path: str, style: str, hues: tuple[int, int], seed: int, size: int = 600):
    """Abstract original cover art."""
    rnd = random.Random(seed)
    img = QImage(size, size, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor.fromHsv(hues[0], 170, 230))
    g.setColorAt(1, QColor.fromHsv(hues[1], 200, 90))
    p.fillRect(0, 0, size, size, g)
    p.setPen(Qt.NoPen)
    if style == "sun":
        for i in range(6, 0, -1):
            c = QColor.fromHsv(hues[0], 120 + i * 12, 255)
            c.setAlpha(60 + i * 25)
            p.setBrush(c)
            r = size * 0.06 * i
            p.drawEllipse(QPointF(size * 0.5, size * 0.62), r, r)
        p.fillRect(QRectF(0, size * 0.72, size, size * 0.28), QColor(0, 0, 0, 90))
    elif style == "waves":
        for k in range(9):
            wave = QPainterPath()
            y0 = size * (0.2 + k * 0.09)
            wave.moveTo(0, y0)
            for x in range(0, size + 10, 10):
                wave.lineTo(x, y0 + math.sin(x / size * math.pi * 3 + k) * size * 0.04)
            p.setPen(QPen(QColor(255, 255, 255, 40 + k * 18), 3 + k * 0.6))
            p.drawPath(wave)
    elif style == "circles":
        for _ in range(14):
            c = QColor.fromHsv(rnd.choice(hues), 160, 255)
            c.setAlpha(rnd.randint(60, 170))
            p.setBrush(c)
            r = rnd.uniform(size * 0.05, size * 0.22)
            p.drawEllipse(QPointF(rnd.uniform(0, size), rnd.uniform(0, size)), r, r)
    elif style == "grid":
        n = 6
        cell = size / n
        for i in range(n):
            for j in range(n):
                if rnd.random() < 0.45:
                    c = QColor.fromHsv(rnd.choice(hues), 140, 255)
                    c.setAlpha(rnd.randint(70, 200))
                    p.setBrush(c)
                    p.drawRoundedRect(QRectF(i * cell + 8, j * cell + 8, cell - 16, cell - 16), 14, 14)
    elif style == "stripes":
        for k in range(12):
            c = QColor(255, 255, 255, 25 + (k % 3) * 25)
            p.setBrush(c)
            p.save()
            p.translate(size / 2, size / 2)
            p.rotate(-30)
            p.drawRect(QRectF(-size, -size + k * size * 0.18, size * 2, size * 0.07))
            p.restore()
    p.end()
    img.save(path, quality=90)


def silent_flac(path: str, seconds: int, tags: dict):
    meta = []
    for k, v in tags.items():
        meta += ["-metadata", f"{k}={v}"]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "anullsrc=r=44100:cl=stereo", "-t", str(seconds), "-sample_fmt", "s16",
                    *meta, "-c:a", "flac", path], check=True)


def embed(path: str, jpg: str):
    f = FLAC(path)
    pic = Picture()
    pic.type, pic.mime = 3, "image/jpeg"
    pic.data = open(jpg, "rb").read()
    f.add_picture(pic)
    f.save()


def main(root: str):
    QGuiApplication.instance() or QGuiApplication(["demo"])
    rnd = random.Random(7)
    os.makedirs(root, exist_ok=True)
    every = []          # (ruta relativa, artista, título)
    for n, (artist, album, year, style, hues) in enumerate(ALBUMS):
        folder = os.path.join(root, f"{artist} - {album}")
        os.makedirs(folder, exist_ok=True)
        art = os.path.join(folder, "cover.jpg")
        cover(art, style, hues, seed=n)
        titles = set()
        while len(titles) < rnd.randint(7, 11):
            titles.add(f"{rnd.choice(WORDS_A)} {rnd.choice(WORDS_B)}")
        for i, title in enumerate(sorted(titles, key=lambda _t: rnd.random()), 1):
            name = f"{i:02d} - {artist} - {title}.flac"
            path = os.path.join(folder, name)
            silent_flac(path, rnd.randint(150, 330), {"title": title, "artist": artist, "album": album,
                                                       "date": year, "track": str(i)})
            embed(path, art)
            every.append((os.path.relpath(path, root), artist, title))
        with open(os.path.join(folder, ".coleccion.json"), "w", encoding="utf-8") as fh:
            json.dump({"kind": "album", "title": album, "artist": artist, "year": year}, fh)

    # listas: enlazan canciones de los álbumes (como hace la app al evitar duplicados)
    for name in PLAYLISTS:
        folder = os.path.join(root, name)
        os.makedirs(folder, exist_ok=True)
        picks = rnd.sample(every, rnd.randint(14, 24))
        refs = [{"pos": i, "path": rel} for i, (rel, _a, _t) in enumerate(picks, 1)]
        with open(os.path.join(folder, ".coleccion.json"), "w", encoding="utf-8") as fh:
            json.dump({"kind": "playlist", "title": name, "artist": "You", "refs": refs}, fh)

    for i, (artist, title) in enumerate(LOOSE):
        path = os.path.join(root, f"{artist} - {title}.flac")
        art = path[:-5] + ".jpg"
        cover(art, "circles", (rnd.randint(0, 359), rnd.randint(0, 359)), seed=100 + i)
        silent_flac(path, rnd.randint(170, 260), {"title": title, "artist": artist, "date": "2024"})
    print(f"Demo library ready in {root}: {len(every) + len(LOOSE)} songs")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo-library")
