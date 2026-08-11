#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1

if [ ! -f "client.py" ]; then
  echo "[ERREUR] client.py introuvable. Decompresse d'abord tout le ZIP."
  read -r -p "Appuie sur Entrée pour fermer..."
  exit 1
fi

PYTHON="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON" ]; then
  echo "[ERREUR] Python 3 est requis."
  read -r -p "Appuie sur Entrée pour fermer..."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  "$PYTHON" -m venv .venv || {
    echo "[ERREUR] Creation de l'environnement Python impossible."
    read -r -p "Appuie sur Entrée pour fermer..."
    exit 1
  }
fi

.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt || {
  echo "[ERREUR] Installation des dependances impossible."
  read -r -p "Appuie sur Entrée pour fermer..."
  exit 1
}

.venv/bin/python client.py
code=$?
if [ "$code" -ne 0 ]; then
  echo
  echo "[ERREUR] SLIME FORUM s'est arrete avec le code $code."
  read -r -p "Appuie sur Entrée pour fermer..."
fi
exit "$code"
