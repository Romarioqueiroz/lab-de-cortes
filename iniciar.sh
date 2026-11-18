#!/usr/bin/env bash
# Lab de Cortes — macOS / Linux
set -e
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "[!] Instale o FFmpeg (macOS: brew install ffmpeg | Ubuntu: sudo apt install ffmpeg)"; exit 1; }
command -v deno >/dev/null || echo "[i] Recomendado instalar o Deno (https://deno.com) para baixar do YouTube."
PY=$(command -v python3 || command -v python)
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
python -m pip install -q -U "yt-dlp[default,curl-cffi]"
python app.py
