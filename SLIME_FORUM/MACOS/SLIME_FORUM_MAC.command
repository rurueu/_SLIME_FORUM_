#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
osascript -e 'tell application "Terminal" to set bounds of front window to {0, 0, 2000, 1200}' >/dev/null 2>&1 || true
sleep 0.6

PYTHON="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON" ]; then
  echo "[ERREUR] Python 3 est requis."
  read -r -p "Appuie sur Entrée pour fermer..."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  "$PYTHON" -m venv .venv || exit 1
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt || exit 1
clear
.venv/bin/python client.py
code=$?
if [ "$code" -ne 0 ]; then
  echo
  echo "[ERREUR] SLIME FORUM s'est arrêté avec le code $code."
  read -r -p "Appuie sur Entrée pour fermer..."
fi
exit "$code"
