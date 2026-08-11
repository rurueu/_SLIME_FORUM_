from flask import Flask, request, jsonify
from datetime import datetime, timezone
import sqlite3
import os

app = Flask(__name__)
DB = os.environ.get("SLIME_FORUM_DB", "forum.db")
MAX_INFO = 1000
MAX_PSEUDO = 30


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pseudo TEXT NOT NULL,
            info TEXT NOT NULL,
            created_at TEXT NOT NULL,
            parent_id INTEGER
        )
    """)

    # Mise à jour automatique d'une ancienne base SLIME FORUM.
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}
    if "parent_id" not in columns:
        conn.execute("ALTER TABLE posts ADD COLUMN parent_id INTEGER")

    conn.commit()
    conn.close()


@app.get("/api/posts")
def posts():
    conn = db()
    rows = conn.execute(
        """SELECT id, pseudo, info, created_at, parent_id
           FROM posts
           ORDER BY id DESC
           LIMIT 300"""
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.post("/api/posts")
def create_post():
    data = request.get_json(silent=True) or {}
    pseudo = str(data.get("pseudo", "")).strip()
    info = str(data.get("info", "")).strip()
    parent_id = data.get("parent_id")

    if not pseudo or not info:
        return jsonify({"error": "Pseudo et message sont obligatoires."}), 400
    if len(pseudo) > MAX_PSEUDO:
        return jsonify({"error": f"Pseudo trop long (max {MAX_PSEUDO})."}), 400
    if len(info) > MAX_INFO:
        return jsonify({"error": f"Message trop long (max {MAX_INFO} caractères)."}), 400

    if parent_id in ("", None):
        parent_id = None
    else:
        try:
            parent_id = int(parent_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Publication parent invalide."}), 400

    conn = db()

    if parent_id is not None:
        parent = conn.execute("SELECT id FROM posts WHERE id = ?", (parent_id,)).fetchone()
        if parent is None:
            conn.close()
            return jsonify({"error": "La publication à laquelle tu réponds n'existe pas."}), 404

    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO posts (pseudo, info, created_at, parent_id) VALUES (?, ?, ?, ?)",
        (pseudo, info, created, parent_id)
    )
    conn.commit()
    post_id = cur.lastrowid
    conn.close()

    return jsonify({
        "id": post_id,
        "pseudo": pseudo,
        "info": info,
        "created_at": created,
        "parent_id": parent_id
    }), 201


@app.get("/health")
def health():
    return {"ok": True}


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
