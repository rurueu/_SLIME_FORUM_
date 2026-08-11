from flask import Flask, request, jsonify
from datetime import datetime, timezone
import os
import sqlite3

app = Flask(__name__)

MAX_INFO = 1000
MAX_PSEUDO = 30

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_DB = os.environ.get("SLIME_FORUM_DB", "forum.db")

USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row


def pg_conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def sqlite_conn():
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS posts (
                        id BIGSERIAL PRIMARY KEY,
                        pseudo TEXT NOT NULL,
                        info TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        parent_id BIGINT NULL
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_posts_parent_id
                    ON posts(parent_id)
                """)
            conn.commit()
        migrate_sqlite_to_postgres_if_needed()
    else:
        conn = sqlite_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pseudo TEXT NOT NULL,
                info TEXT NOT NULL,
                created_at TEXT NOT NULL,
                parent_id INTEGER
            )
        """)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}
        if "parent_id" not in cols:
            conn.execute("ALTER TABLE posts ADD COLUMN parent_id INTEGER")
        conn.commit()
        conn.close()


def migrate_sqlite_to_postgres_if_needed():
    """Importe l'ancienne base forum.db une seule fois si Postgres est vide."""
    if not os.path.exists(SQLITE_DB):
        return

    try:
        old = sqlite_conn()
        cols = {row["name"] for row in old.execute("PRAGMA table_info(posts)").fetchall()}
        if not cols:
            old.close()
            return

        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS total FROM posts")
                total = cur.fetchone()["total"]
                if total != 0:
                    old.close()
                    return

                if "parent_id" in cols:
                    rows = old.execute(
                        "SELECT id, pseudo, info, created_at, parent_id FROM posts ORDER BY id"
                    ).fetchall()
                else:
                    rows = old.execute(
                        "SELECT id, pseudo, info, created_at, NULL AS parent_id FROM posts ORDER BY id"
                    ).fetchall()

                for row in rows:
                    cur.execute("""
                        INSERT INTO posts (id, pseudo, info, created_at, parent_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                    """, (row["id"], row["pseudo"], row["info"], row["created_at"], row["parent_id"]))

                cur.execute("""
                    SELECT setval(
                        pg_get_serial_sequence('posts', 'id'),
                        COALESCE((SELECT MAX(id) FROM posts), 1),
                        true
                    )
                """)
            conn.commit()
        old.close()
    except Exception as e:
        print("Migration SQLite -> PostgreSQL ignorée :", e)


def fetch_posts():
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, pseudo, info, created_at, parent_id
                    FROM posts
                    ORDER BY id DESC
                    LIMIT 300
                """)
                return cur.fetchall()

    conn = sqlite_conn()
    rows = conn.execute("""
        SELECT id, pseudo, info, created_at, parent_id
        FROM posts
        ORDER BY id DESC
        LIMIT 300
    """).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


def post_exists(post_id):
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM posts WHERE id = %s", (post_id,))
                return cur.fetchone() is not None

    conn = sqlite_conn()
    row = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
    conn.close()
    return row is not None


def insert_post(pseudo, info, created_at, parent_id):
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO posts (pseudo, info, created_at, parent_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (pseudo, info, created_at, parent_id))
                post_id = cur.fetchone()["id"]
            conn.commit()
            return post_id

    conn = sqlite_conn()
    cur = conn.execute("""
        INSERT INTO posts (pseudo, info, created_at, parent_id)
        VALUES (?, ?, ?, ?)
    """, (pseudo, info, created_at, parent_id))
    conn.commit()
    post_id = cur.lastrowid
    conn.close()
    return post_id


@app.get("/api/posts")
def posts():
    return jsonify(fetch_posts())


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

        if not post_exists(parent_id):
            return jsonify({"error": "La publication à laquelle tu réponds n'existe pas."}), 404

    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    post_id = insert_post(pseudo, info, created, parent_id)

    return jsonify({
        "id": post_id,
        "pseudo": pseudo,
        "info": info,
        "created_at": created,
        "parent_id": parent_id
    }), 201


@app.get("/health")
def health():
    return {
        "ok": True,
        "database": "postgresql" if USE_POSTGRES else "sqlite"
    }


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
