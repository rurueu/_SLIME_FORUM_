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

CREATOR_BOOTSTRAP_HASH = "bcd328efd1b0cf954cccf06c9314338cdf2bb37728ebd15f16a90056f2b97f90"
STAFF_BOOTSTRAP_HASH = ""
CODING_BOOTSTRAP_HASH = ""



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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS app_secrets (
                        name TEXT PRIMARY KEY,
                        password_hash TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    INSERT INTO app_secrets (name, password_hash, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                """, ("creator", CREATOR_BOOTSTRAP_HASH, iso(utcnow())))
                cur.execute("""
                    INSERT INTO app_secrets (name, password_hash, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                """, ("staff", STAFF_BOOTSTRAP_HASH, iso(utcnow())))
                cur.execute("""
                    INSERT INTO app_secrets (name, password_hash, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                """, ("coding", CODING_BOOTSTRAP_HASH, iso(utcnow())))
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_secrets (
            name TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    now_value = iso(utcnow())
    conn.execute(
        "INSERT OR IGNORE INTO app_secrets (name, password_hash, updated_at) VALUES (?, ?, ?)",
        ("creator", CREATOR_BOOTSTRAP_HASH, now_value)
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_secrets (name, password_hash, updated_at) VALUES (?, ?, ?)",
        ("staff", STAFF_BOOTSTRAP_HASH, now_value)
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_secrets (name, password_hash, updated_at) VALUES (?, ?, ?)",
        ("coding", CODING_BOOTSTRAP_HASH, now_value)
    )

    conn.commit()
    conn.close()


def client_id():
    return request.headers.get("X-Slime-Client", "").strip()


def get_secret_hash(name):
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password_hash FROM app_secrets WHERE name = %s", (name,))
                row = cur.fetchone()
                return row["password_hash"] if row else ""
    conn = sqlite_conn()
    row = conn.execute(
        "SELECT password_hash FROM app_secrets WHERE name = ?",
        (name,)
    ).fetchone()
    conn.close()
    return row["password_hash"] if row else ""


def set_secret_hash(name, password_hash):
    updated = iso(utcnow())
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO app_secrets (name, password_hash, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name)
                    DO UPDATE SET password_hash = EXCLUDED.password_hash,
                                  updated_at = EXCLUDED.updated_at
                """, (name, password_hash, updated))
            conn.commit()
        return

    conn = sqlite_conn()
    conn.execute("""
        INSERT INTO app_secrets (name, password_hash, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(name)
        DO UPDATE SET password_hash=excluded.password_hash,
                      updated_at=excluded.updated_at
    """, (name, password_hash, updated))
    conn.commit()
    conn.close()


def verify_secret(name, supplied):
    expected = get_secret_hash(name)
    if not expected or not supplied:
        return False
    supplied_hash = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
    return hmac.compare_digest(supplied_hash, expected)


def admin_role():
    role = request.headers.get("X-Slime-Admin-Role", "").strip().lower()
    if role not in {"creator", "staff", "admin"}:
        return None
    return role


def admin_authorized():
    supplied = request.headers.get("X-Slime-Admin-Secret", "")
    role = admin_role()
    if role == "creator":
        return verify_secret("creator", supplied)
    if role in {"staff", "admin"}:
        return verify_secret("staff", supplied)
    return False


def require_admin():
    if not admin_authorized():
        return jsonify({"error": "Accès personnel refusé."}), 403
    return None


def require_creator():
    denied = require_admin()
    if denied:
        return denied
    if admin_role() != "creator":
        return jsonify({"error": "Fonction réservée au Créateur."}), 403
    return None


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
    post = find_post(post_id, include_client=True)
    if post:
        try:
            db_execute(
                """INSERT INTO deleted_posts(id,pseudo,info,created_at,parent_id,client_id,deleted_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (post["id"],post["pseudo"],post["info"],post["created_at"],
                 post.get("parent_id"),post.get("client_id"),iso(utcnow()))
            )
        except Exception:
            pass

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



@app.get("/api/admin/passwords")
def admin_password_status():
    denied = require_creator()
    if denied:
        return denied

    return jsonify({
        "creator": bool(get_secret_hash("creator")),
        "staff": bool(get_secret_hash("staff")),
        "coding": bool(get_secret_hash("coding")),
    })


@app.post("/api/admin/passwords/<name>")
def admin_password_change(name):
    denied = require_creator()
    if denied:
        return denied

    if name not in {"creator", "staff", "coding"}:
        return jsonify({"error": "Type de mot de passe invalide."}), 400

    data = request.get_json(silent=True) or {}
    new_password = str(data.get("new_password", ""))

    if len(new_password) < 8:
        return jsonify({"error": "Le nouveau mot de passe doit contenir au moins 8 caractères."}), 400

    new_hash = hashlib.sha256(new_password.encode("utf-8")).hexdigest()
    set_secret_hash(name, new_hash)

    return jsonify({
        "message": f"Mot de passe {name} mis à jour.",
        "name": name
    })


@app.get("/health")
def health():
    return {
        "ok": True,
        "database": "postgresql" if USE_POSTGRES else "sqlite",
        "admin_configured": bool(get_secret_hash("creator")),
    }


init_db()


# ============================================================
# SLIME FORUM - EXTENSIONS COMMUNAUTAIRES
# ============================================================

def ensure_extra_tables():
    if USE_POSTGRES:
        statements = [
            """CREATE TABLE IF NOT EXISTS channels (
                id BIGSERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL,
                official_only BOOLEAN NOT NULL DEFAULT FALSE)""",
            """CREATE TABLE IF NOT EXISTS reactions (
                post_id BIGINT NOT NULL, client_id TEXT NOT NULL,
                reaction TEXT NOT NULL, PRIMARY KEY(post_id, client_id, reaction))""",
            """CREATE TABLE IF NOT EXISTS pinned_posts (
                post_id BIGINT PRIMARY KEY, pinned_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS moderation_log (
                id BIGSERIAL PRIMARY KEY, actor_role TEXT NOT NULL,
                action TEXT NOT NULL, target TEXT, created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS deleted_posts (
                id BIGINT PRIMARY KEY, pseudo TEXT, info TEXT, created_at TEXT,
                parent_id BIGINT, client_id TEXT, deleted_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS forum_settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS active_clients (
                client_id TEXT PRIMARY KEY, last_seen TEXT NOT NULL)""",
        ]
        with pg_conn() as conn:
            with conn.cursor() as cur:
                for q in statements:
                    cur.execute(q)
                cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS channel_id BIGINT")
                cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS edited_at TEXT")
                cur.execute("""INSERT INTO channels(name, official_only)
                               VALUES (%s,%s) ON CONFLICT(name) DO NOTHING""", ("Général", False))
                cur.execute("""INSERT INTO channels(name, official_only)
                               VALUES (%s,%s) ON CONFLICT(name) DO NOTHING""", ("Annonces officielles", True))
                defaults = {
                    "maintenance":"0", "refresh_seconds":"5",
                    "welcome_message":"Bienvenue sur SLIME FORUM",
                    "max_message_length":"1000"
                }
                for k,v in defaults.items():
                    cur.execute("""INSERT INTO forum_settings(key,value) VALUES (%s,%s)
                                   ON CONFLICT(key) DO NOTHING""", (k,v))
            conn.commit()
        return

    conn = sqlite_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
        official_only INTEGER NOT NULL DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS reactions (
        post_id INTEGER NOT NULL, client_id TEXT NOT NULL,
        reaction TEXT NOT NULL, PRIMARY KEY(post_id,client_id,reaction))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pinned_posts (
        post_id INTEGER PRIMARY KEY, pinned_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS moderation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, actor_role TEXT NOT NULL,
        action TEXT NOT NULL, target TEXT, created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS deleted_posts (
        id INTEGER PRIMARY KEY, pseudo TEXT, info TEXT, created_at TEXT,
        parent_id INTEGER, client_id TEXT, deleted_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS forum_settings (
        key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS active_clients (
        client_id TEXT PRIMARY KEY, last_seen TEXT NOT NULL)""")
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(posts)").fetchall()}
    if "channel_id" not in cols:
        conn.execute("ALTER TABLE posts ADD COLUMN channel_id INTEGER")
    if "edited_at" not in cols:
        conn.execute("ALTER TABLE posts ADD COLUMN edited_at TEXT")
    conn.execute("INSERT OR IGNORE INTO channels(name,official_only) VALUES (?,?)", ("Général",0))
    conn.execute("INSERT OR IGNORE INTO channels(name,official_only) VALUES (?,?)", ("Annonces officielles",1))
    defaults = {
        "maintenance":"0", "refresh_seconds":"5",
        "welcome_message":"Bienvenue sur SLIME FORUM",
        "max_message_length":"1000"
    }
    for k,v in defaults.items():
        conn.execute("INSERT OR IGNORE INTO forum_settings(key,value) VALUES (?,?)",(k,v))
    conn.commit()
    conn.close()


def db_rows(query_sqlite, params=(), query_pg=None):
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query_pg or query_sqlite.replace("?", "%s"), params)
                return cur.fetchall()
    conn = sqlite_conn()
    rows = [dict(r) for r in conn.execute(query_sqlite, params).fetchall()]
    conn.close()
    return rows


def db_execute(query_sqlite, params=(), query_pg=None):
    if USE_POSTGRES:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query_pg or query_sqlite.replace("?", "%s"), params)
            conn.commit()
        return
    conn = sqlite_conn()
    conn.execute(query_sqlite, params)
    conn.commit()
    conn.close()


def setting_get(key, default=""):
    rows = db_rows("SELECT value FROM forum_settings WHERE key=?", (key,))
    return rows[0]["value"] if rows else default


def log_mod(action, target=""):
    role = admin_role() or "system"
    db_execute(
        "INSERT INTO moderation_log(actor_role,action,target,created_at) VALUES (?,?,?,?)",
        (role, action, str(target), iso(utcnow()))
    )


@app.before_request
def slime_presence_and_maintenance():
    if not request.path.startswith("/api/"):
        return None
    cid = client_id()
    if cid:
        if USE_POSTGRES:
            db_execute(
                """INSERT INTO active_clients(client_id,last_seen) VALUES (?,?)
                   ON CONFLICT(client_id) DO UPDATE SET last_seen=EXCLUDED.last_seen""",
                (cid, iso(utcnow()))
            )
        else:
            db_execute(
                """INSERT INTO active_clients(client_id,last_seen) VALUES (?,?)
                   ON CONFLICT(client_id) DO UPDATE SET last_seen=excluded.last_seen""",
                (cid, iso(utcnow()))
            )
    if setting_get("maintenance","0") == "1" and not request.path.startswith("/api/admin/"):
        return jsonify({"error":"SLIME FORUM est actuellement en maintenance.","maintenance":True}), 503
    return None


@app.get("/api/channels")
def extra_channels():
    return jsonify(db_rows("SELECT id,name,official_only FROM channels ORDER BY id"))


@app.post("/api/admin/channels")
def extra_create_channel():
    denied = require_admin()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    name = str(data.get("name","")).strip()[:50]
    official = bool(data.get("official_only",False))
    if not name: return jsonify({"error":"Nom obligatoire."}),400
    try:
        db_execute("INSERT INTO channels(name,official_only) VALUES (?,?)",(name,1 if official else 0))
    except Exception:
        return jsonify({"error":"Ce salon existe déjà."}),409
    log_mod("création salon", name)
    return jsonify({"message":f"Salon {name} créé."}),201


@app.post("/api/posts/<int:post_id>/react")
def extra_react(post_id):
    data = request.get_json(silent=True) or {}
    reaction = str(data.get("reaction","")).strip()
    if reaction not in {"+1","❤️","😂","👍"}:
        return jsonify({"error":"Réaction invalide."}),400
    cid = client_id()
    if not cid: return jsonify({"error":"Client non identifié."}),400
    try:
        db_execute("INSERT INTO reactions(post_id,client_id,reaction) VALUES (?,?,?)",
                   (post_id,cid,reaction))
        return jsonify({"message":"Réaction ajoutée."}),201
    except Exception:
        db_execute("DELETE FROM reactions WHERE post_id=? AND client_id=? AND reaction=?",
                   (post_id,cid,reaction))
        return jsonify({"message":"Réaction retirée."})


@app.get("/api/posts/<int:post_id>/reactions")
def extra_reactions(post_id):
    return jsonify(db_rows(
        "SELECT reaction,COUNT(*) AS count FROM reactions WHERE post_id=? GROUP BY reaction",
        (post_id,)
    ))


@app.post("/api/admin/posts/<int:post_id>/pin")
def extra_pin(post_id):
    denied = require_admin()
    if denied: return denied
    try:
        if USE_POSTGRES:
            db_execute("""INSERT INTO pinned_posts(post_id,pinned_at) VALUES (?,?)
                          ON CONFLICT(post_id) DO NOTHING""",(post_id,iso(utcnow())))
        else:
            db_execute("INSERT OR IGNORE INTO pinned_posts(post_id,pinned_at) VALUES (?,?)",
                       (post_id,iso(utcnow())))
    except Exception:
        pass
    log_mod("message épinglé", post_id)
    return jsonify({"message":f"Message #{post_id} épinglé."})


@app.delete("/api/admin/posts/<int:post_id>/pin")
def extra_unpin(post_id):
    denied = require_admin()
    if denied: return denied
    db_execute("DELETE FROM pinned_posts WHERE post_id=?",(post_id,))
    log_mod("message désépinglé", post_id)
    return jsonify({"message":f"Message #{post_id} désépinglé."})


@app.get("/api/search")
def extra_search():
    q = request.args.get("q","").strip()
    if not q: return jsonify([])
    like = f"%{q}%"
    return jsonify(db_rows(
        """SELECT id,pseudo,info,created_at,parent_id
           FROM posts WHERE pseudo LIKE ? OR info LIKE ?
           ORDER BY id DESC LIMIT 100""",(like,like)
    ))


@app.get("/api/stats")
def extra_stats():
    total = db_rows("SELECT COUNT(*) AS n FROM posts")[0]["n"]
    replies = db_rows("SELECT COUNT(*) AS n FROM posts WHERE parent_id IS NOT NULL")[0]["n"]
    active = db_rows(
        "SELECT COUNT(*) AS n FROM active_clients WHERE last_seen >= ?",
        (iso(utcnow()-timedelta(minutes=5)),)
    )[0]["n"]
    today_prefix = utcnow().date().isoformat() + "%"
    today = db_rows("SELECT COUNT(*) AS n FROM posts WHERE created_at LIKE ?",(today_prefix,))[0]["n"]
    return jsonify({"messages":total,"reponses":replies,"actifs_5min":active,"aujourdhui":today})


@app.get("/api/admin/bans")
def extra_bans():
    denied = require_admin()
    if denied: return denied
    return jsonify(db_rows(
        "SELECT client_id,created_at,expires_at,reason FROM banned_clients ORDER BY created_at DESC"
    ))


@app.delete("/api/admin/bans/<client>")
def extra_unban(client):
    denied = require_admin()
    if denied: return denied
    unban(client)
    log_mod("débannissement", client[:12])
    return jsonify({"message":"Bannissement retiré."})


@app.get("/api/admin/log")
def extra_modlog():
    denied = require_admin()
    if denied: return denied
    return jsonify(db_rows(
        "SELECT id,actor_role,action,target,created_at FROM moderation_log ORDER BY id DESC LIMIT 200"
    ))


@app.get("/api/admin/trash")
def extra_trash():
    denied = require_admin()
    if denied: return denied
    return jsonify(db_rows(
        "SELECT id,pseudo,info,created_at,parent_id,deleted_at FROM deleted_posts ORDER BY deleted_at DESC LIMIT 200"
    ))


@app.post("/api/admin/trash/<int:post_id>/restore")
def extra_restore(post_id):
    denied = require_admin()
    if denied: return denied
    rows = db_rows("SELECT * FROM deleted_posts WHERE id=?",(post_id,))
    if not rows: return jsonify({"error":"Introuvable dans la corbeille."}),404
    r=rows[0]
    try:
        if USE_POSTGRES:
            db_execute("""INSERT INTO posts(id,pseudo,info,created_at,parent_id,client_id)
                          VALUES (?,?,?,?,?,?)""",
                       (r["id"],r["pseudo"],r["info"],r["created_at"],r["parent_id"],r.get("client_id")))
        else:
            db_execute("""INSERT INTO posts(id,pseudo,info,created_at,parent_id,client_id)
                          VALUES (?,?,?,?,?,?)""",
                       (r["id"],r["pseudo"],r["info"],r["created_at"],r["parent_id"],r.get("client_id")))
        db_execute("DELETE FROM deleted_posts WHERE id=?",(post_id,))
    except Exception as e:
        return jsonify({"error":"Restauration impossible."}),409
    log_mod("restauration message", post_id)
    return jsonify({"message":f"Message #{post_id} restauré."})


@app.post("/api/posts/<int:post_id>/edit")
def extra_edit(post_id):
    data=request.get_json(silent=True) or {}
    info=str(data.get("info","")).strip()
    if not info: return jsonify({"error":"Message vide."}),400
    # édition liée à la même installation
    rows=db_rows("SELECT client_id FROM posts WHERE id=?",(post_id,))
    if not rows: return jsonify({"error":"Message introuvable."}),404
    if rows[0].get("client_id") != client_id():
        return jsonify({"error":"Tu ne peux modifier que ton propre message."}),403
    db_execute("UPDATE posts SET info=?,edited_at=? WHERE id=?",(info,iso(utcnow()),post_id))
    return jsonify({"message":f"Message #{post_id} modifié."})


@app.get("/api/settings")
def extra_public_settings():
    rows=db_rows("SELECT key,value FROM forum_settings")
    data={r["key"]:r["value"] for r in rows}
    return jsonify(data)


@app.post("/api/admin/settings")
def extra_settings():
    denied=require_creator()
    if denied:return denied
    data=request.get_json(silent=True) or {}
    allowed={"maintenance","refresh_seconds","welcome_message","max_message_length"}
    for k,v in data.items():
        if k not in allowed: continue
        if USE_POSTGRES:
            db_execute("""INSERT INTO forum_settings(key,value) VALUES (?,?)
                          ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value""",(k,str(v)))
        else:
            db_execute("""INSERT INTO forum_settings(key,value) VALUES (?,?)
                          ON CONFLICT(key) DO UPDATE SET value=excluded.value""",(k,str(v)))
    log_mod("paramètres modifiés", ",".join(data.keys()))
    return jsonify({"message":"Paramètres enregistrés."})


ensure_extra_tables()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
