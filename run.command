#!/bin/zsh
# Double-click in Finder to open the app. The first time it installs what it needs.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Setting up the environment (first time only)…"
  if command -v uv >/dev/null; then
    uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
  else
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
  fi
fi
command -v ffmpeg >/dev/null || { echo "ffmpeg is missing: brew install ffmpeg"; exit 1; }
exec .venv/bin/python app.py
