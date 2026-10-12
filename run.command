#!/bin/zsh
# Doble clic en Finder para abrir la app. La primera vez instala lo necesario.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Preparando entorno (solo la primera vez)…"
  if command -v uv >/dev/null; then
    uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
  else
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
  fi
fi
command -v ffmpeg >/dev/null || { echo "Falta ffmpeg: brew install ffmpeg"; exit 1; }
exec .venv/bin/python app.py
