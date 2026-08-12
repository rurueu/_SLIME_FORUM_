#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ "${SLIME_FORUM_MAXIMIZED:-0}" != "1" ]; then
  export SLIME_FORUM_MAXIMIZED=1
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal --maximize -- bash -lc "export SLIME_FORUM_MAXIMIZED=1; cd '$SCRIPT_DIR'; exec ./SLIME_FORUM_LINUX.sh"
    exit 0
  elif command -v mate-terminal >/dev/null 2>&1; then
    mate-terminal --maximize -- bash -lc "export SLIME_FORUM_MAXIMIZED=1; cd '$SCRIPT_DIR'; exec ./SLIME_FORUM_LINUX.sh"
    exit 0
  elif command -v xfce4-terminal >/dev/null 2>&1; then
    xfce4-terminal --maximize --command="bash -lc 'export SLIME_FORUM_MAXIMIZED=1; cd \"$SCRIPT_DIR\"; exec ./SLIME_FORUM_LINUX.sh'"
    exit 0
  elif command -v konsole >/dev/null 2>&1; then
    konsole --fullscreen -e bash -lc "export SLIME_FORUM_MAXIMIZED=1; cd '$SCRIPT_DIR'; exec ./SLIME_FORUM_LINUX.sh"
    exit 0
  fi
  printf '\033[9;1t' 2>/dev/null || true
fi

sleep 0.8
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
