from flask import Flask, request, jsonify
from datetime import datetime, timezone, timedelta
import os
import sqlite3
import hmac
import hashlib

app = Flask(__name__)

MAX_INFO = 1000
MAX_PSEUDO = 30

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_DB = os.environ.get("SLIME_FORUM_DB", "forum.db")
ADMIN_SECRET = os.environ.get("SLIME_ADMIN_SECRET", "").strip()
ADMIN_SECRET_HASH = "bcd328efd1b0cf954cccf06c9314338cdf2bb37728ebd15f16a90056f2b97f90"

USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds")


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
                        parent_id BIGINT NULL,
                        client_id TEXT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS banned_clients (
                        client_id TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NULL,
                        reason TEXT NOT NULL
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_parent_id ON posts(parent_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_client_id ON posts(client_id)")
            conn.commit()
        return

    conn = sqlite_conn()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pseudo TEXT NOT NULL,
            info TEXT NOT NULL,
            created_at TEXT NOT NULL,
            parent_id INTEGER NULL,
            client_id TEXT NULL
        )
    """)

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(posts)").fetchall()}
    if "parent_id" not in cols:
        conn.execute("ALTER TABLE posts ADD COLUMN parent_id INTEGER")
    if "client_id" not in cols:
        conn.execute("ALTER TABLE posts ADD COLUMN client_id TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS banned_clients (
            client_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            expires_at TEXT NULL,
            reason TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def client_id():
    return request.headers.get("X-Slime-Client", "").strip()


def admin_authorized():
    supplied = request.headers.get("X-Slime-Admin-Secret", "")
    if not supplied:
        return False

    # Priorité à la variable privée Render si elle existe.
    if ADMIN_SECRET:
        return hmac.compare_digest(supplied, ADMIN_SECRET)

    # Secours : comparaison via empreinte SHA-256.
    supplied_hash = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
    return hmac.compare_digest(supplied_hash, ADMIN_SECRET_HASH)


def require_admin():
    if not admin_authorized():
        return jsonify({"error": "Accès personnel refusé."}), 403
    return None


def admin_role():
    role = request.headers.get("X-Slime-Admin-Role", "").strip().lower()
    if role not in {"creator", "staff", "admin"}:
        return None
    return role


def is_creator_pseudo(pseudo):
    return str(pseudo or "").startswith("@C@")


def is_staff_pseudo(pseudo):
    value = str(pseudo or "")
    return value.startswith("@S@")


def can_moderate_target(requester_role, target_pseudo):
    # Le Créateur peut modérer tout le monde.
    if requester_role == "creator":
        return True

    # Staff/Admin ne peuvent jamais modérer le Créateur.
    if is_creator_pseudo(target_pseudo):
        return False

    return requester_role in {"staff", "admin"}


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def human_remaining(expires_at):
    if not expires_at:
        return "À vie"

    end = parse_iso(expires_at)
    if end is None:
        return "Durée inconnue"

    delta = end - utcnow()
    seconds = int(delta.total_seconds())

    if seconds <= 0:
        return "Expiré"

    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60

    if days >= 365:
        years = days // 365
        return f"{years} an" + ("s" if years > 1 else "")
    if days >= 30:
        months = days // 30
        return f"{months} mois"
    if days >= 7:
        weeks = days // 7
        return f"{weeks} semaine" + ("s" if weeks > 1 else "")
    if days > 0:
        return f"{days} jour" + ("s" if days > 1 else "")
    if hours > 0:
        return f"{hours} h {minutes} min"
    return f"{max(1, minutes)} min"


def get_ban(cid):
    if not cid:
        return None

    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT client_id, created_at, expires_at, reason FROM banned_clients WHERE client_id = %s",
                    (cid,)
                )
                row = cur.fetchone()
    else:
        conn = sqlite_conn()
        row = conn.execute(
            "SELECT client_id, created_at, expires_at, reason FROM banned_clients WHERE client_id = ?",
            (cid,)
        ).fetchone()
        conn.close()
        row = dict(row) if row else None

    if not row:
        return None

    expires = row["expires_at"]
    end = parse_iso(expires)

    if end is not None and end <= utcnow():
        unban(cid)
        return None

    return row


def unban(cid):
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM banned_clients WHERE client_id = %s", (cid,))
            conn.commit()
    else:
        conn = sqlite_conn()
        conn.execute("DELETE FROM banned_clients WHERE client_id = ?", (cid,))
        conn.commit()
        conn.close()


def ban_response(row):
    return jsonify({
        "banned": True,
        "error": "Cette installation est bannie du forum.",
        "remaining": human_remaining(row["expires_at"]),
        "expires_at": row["expires_at"],
        "reason": row["reason"],
    }), 403


@app.before_request
def check_current_ban():
    if not request.path.startswith("/api/"):
        return None

    if request.path.startswith("/api/admin/"):
        return None

    row = get_ban(client_id())
    if row:
        return ban_response(row)

    return None


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


def find_post(post_id, include_client=False):
    fields = "id, pseudo, info, created_at, parent_id"
    if include_client:
        fields += ", client_id"

    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {fields} FROM posts WHERE id = %s", (post_id,))
                return cur.fetchone()

    conn = sqlite_conn()
    row = conn.execute(f"SELECT {fields} FROM posts WHERE id = ?", (post_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def insert_post(pseudo, info, created_at, parent_id, cid):
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO posts (pseudo, info, created_at, parent_id, client_id)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (pseudo, info, created_at, parent_id, cid))
                post_id = cur.fetchone()["id"]
            conn.commit()
            return post_id

    conn = sqlite_conn()
    cur = conn.execute("""
        INSERT INTO posts (pseudo, info, created_at, parent_id, client_id)
        VALUES (?, ?, ?, ?, ?)
    """, (pseudo, info, created_at, parent_id, cid))
    conn.commit()
    post_id = cur.lastrowid
    conn.close()
    return post_id


def delete_post_tree(post_id):
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM posts WHERE parent_id = %s", (post_id,))
                cur.execute("DELETE FROM posts WHERE id = %s", (post_id,))
            conn.commit()
        return

    conn = sqlite_conn()
    conn.execute("DELETE FROM posts WHERE parent_id = ?", (post_id,))
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()


def ban_client(cid, duration_code, reason):
    now = utcnow()

    mapping = {
        "1d": timedelta(days=1),
        "1w": timedelta(days=7),
        "1m": timedelta(days=30),
        "1y": timedelta(days=365),
    }

    expires = None
    if duration_code != "forever":
        delta = mapping.get(duration_code)
        if delta is None:
            raise ValueError("Durée invalide")
        expires = iso(now + delta)

    created = iso(now)

    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO banned_clients (client_id, created_at, expires_at, reason)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (client_id)
                    DO UPDATE SET created_at = EXCLUDED.created_at,
                                  expires_at = EXCLUDED.expires_at,
                                  reason = EXCLUDED.reason
                """, (cid, created, expires, reason))
            conn.commit()
        return expires

    conn = sqlite_conn()
    conn.execute("""
        INSERT INTO banned_clients (client_id, created_at, expires_at, reason)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(client_id)
        DO UPDATE SET created_at=excluded.created_at,
                      expires_at=excluded.expires_at,
                      reason=excluded.reason
    """, (cid, created, expires, reason))
    conn.commit()
    conn.close()
    return expires


@app.get("/api/status")
def status():
    return {"ok": True, "banned": False}


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

        if not find_post(parent_id):
            return jsonify({"error": "La publication à laquelle tu réponds n'existe pas."}), 404

    created = iso(utcnow())
    post_id = insert_post(pseudo, info, created, parent_id, client_id())

    return jsonify({
        "id": post_id,
        "pseudo": pseudo,
        "info": info,
        "created_at": created,
        "parent_id": parent_id,
    }), 201


@app.get("/api/admin/auth")
def admin_auth():
    denied = require_admin()
    if denied:
        return denied

    role = admin_role()
    if role is None:
        return jsonify({"error": "Rôle personnel invalide."}), 403

    return {"ok": True, "role": role}


@app.delete("/api/admin/posts/<int:post_id>")
def admin_delete(post_id):
    denied = require_admin()
    if denied:
        return denied

    role = admin_role()
    if role is None:
        return jsonify({"error": "Rôle personnel invalide."}), 403

    post = find_post(post_id)
    if not post:
        return jsonify({"error": "Message introuvable."}), 404

    if not can_moderate_target(role, post.get("pseudo")):
        return jsonify({
            "error": "Impossible : le Créateur est protégé contre les actions de modération du Staff/Admin."
        }), 403

    delete_post_tree(post_id)
    return jsonify({"message": f"Message #{post_id} supprimé."})


@app.post("/api/admin/ban-by-post/<int:post_id>")
def admin_ban_by_post(post_id):
    denied = require_admin()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    duration = str(data.get("duration", "")).strip()

    role = admin_role()
    if role is None:
        return jsonify({"error": "Rôle personnel invalide."}), 403

    post = find_post(post_id, include_client=True)
    if not post:
        return jsonify({"error": "Message introuvable."}), 404

    if not can_moderate_target(role, post.get("pseudo")):
        return jsonify({
            "error": "Impossible : le Créateur ne peut pas être banni par le Staff/Admin."
        }), 403

    cid = (post.get("client_id") or "").strip()
    if not cid:
        return jsonify({
            "error": "Ce message est trop ancien : aucun identifiant d'installation n'y est associé."
        }), 400

    try:
        expires = ban_client(
            cid,
            duration,
            f"Bannissement appliqué à partir de la publication #{post_id}."
        )
    except ValueError:
        return jsonify({"error": "Durée de bannissement invalide."}), 400

    label_map = {
        "1d": "1 jour",
        "1w": "1 semaine",
        "1m": "1 mois",
        "1y": "1 an",
        "forever": "à vie",
    }

    return jsonify({
        "message": f"Installation liée au message #{post_id} bannie {label_map.get(duration, '')}.",
        "expires_at": expires,
    })


@app.get("/health")
def health():
    return {
        "ok": True,
        "database": "postgresql" if USE_POSTGRES else "sqlite",
        "admin_configured": True,
        "admin_mode": "render_env" if ADMIN_SECRET else "hash_fallback",
    }


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
