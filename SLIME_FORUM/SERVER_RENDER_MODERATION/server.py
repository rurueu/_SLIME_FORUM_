from flask import Flask, request, jsonify
from datetime import datetime, timezone
import sqlite3, os

app = Flask(__name__)
DB = os.environ.get("SLIME_FORUM_DB", "forum.db")

def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    c=db()
    c.execute("""CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pseudo TEXT NOT NULL,
        info TEXT NOT NULL,
        created_at TEXT NOT NULL,
        parent_id INTEGER,
        client_id TEXT
    )""")
    cols={r["name"] for r in c.execute("PRAGMA table_info(posts)").fetchall()}
    if "parent_id" not in cols: c.execute("ALTER TABLE posts ADD COLUMN parent_id INTEGER")
    if "client_id" not in cols: c.execute("ALTER TABLE posts ADD COLUMN client_id TEXT")
    c.execute("CREATE TABLE IF NOT EXISTS banned_clients (client_id TEXT PRIMARY KEY, created_at TEXT NOT NULL)")
    c.commit(); c.close()

def client_id():
    return request.headers.get("X-Slime-Client","").strip()

def is_banned(cid):
    if not cid: return False
    c=db(); row=c.execute("SELECT 1 FROM banned_clients WHERE client_id=?",(cid,)).fetchone(); c.close()
    return row is not None

@app.before_request
def banned_check():
    if request.path.startswith("/api/") and not request.path.startswith("/api/admin/"):
        cid=client_id()
        if is_banned(cid):
            return jsonify({"error":"Cette installation est bannie du forum."}),403

@app.get("/api/posts")
def posts():
    c=db()
    rows=c.execute("SELECT id,pseudo,info,created_at,parent_id FROM posts ORDER BY id DESC LIMIT 300").fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@app.post("/api/posts")
def create():
    data=request.get_json(silent=True) or {}
    pseudo=str(data.get("pseudo","")).strip()
    info=str(data.get("info","")).strip()
    parent=data.get("parent_id")
    if not pseudo or not info: return jsonify({"error":"Pseudo et message obligatoires."}),400
    if parent not in ("",None):
        try: parent=int(parent)
        except: return jsonify({"error":"Publication parent invalide."}),400
    else: parent=None
    created=datetime.now(timezone.utc).isoformat(timespec="seconds")
    c=db()
    cur=c.execute("INSERT INTO posts(pseudo,info,created_at,parent_id,client_id) VALUES(?,?,?,?,?)",
                  (pseudo,info,created,parent,client_id()))
    c.commit(); pid=cur.lastrowid; c.close()
    return jsonify({"id":pid,"pseudo":pseudo,"info":info,"created_at":created,"parent_id":parent}),201

@app.delete("/api/admin/posts/<int:post_id>")
def delete_post(post_id):
    c=db()
    row=c.execute("SELECT id FROM posts WHERE id=?",(post_id,)).fetchone()
    if not row: c.close(); return jsonify({"error":"Message introuvable."}),404
    c.execute("DELETE FROM posts WHERE id=? OR parent_id=?",(post_id,post_id))
    c.commit(); c.close()
    return jsonify({"message":f"Message #{post_id} supprimé."})

@app.post("/api/admin/ban-by-post/<int:post_id>")
def ban_by_post(post_id):
    c=db()
    row=c.execute("SELECT client_id FROM posts WHERE id=?",(post_id,)).fetchone()
    if not row: c.close(); return jsonify({"error":"Message introuvable."}),404
    cid=row["client_id"]
    if not cid:
        c.close(); return jsonify({"error":"Ce message ancien ne possède pas d'identifiant d'installation."}),400
    created=datetime.now(timezone.utc).isoformat(timespec="seconds")
    c.execute("INSERT OR IGNORE INTO banned_clients(client_id,created_at) VALUES(?,?)",(cid,created))
    c.commit(); c.close()
    return jsonify({"message":f"Installation liée au message #{post_id} bannie."})

@app.get("/health")
def health(): return {"ok":True}

init_db()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
