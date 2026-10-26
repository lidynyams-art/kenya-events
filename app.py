"""REST API (single entry point): login, role checks, validation, then delegates to services."""
import os, datetime as dt
from functools import wraps
from flask import Flask, request, jsonify, g, send_from_directory
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
import db, recommender, payments

def num(v, d=None):
    try: return int(v)
    except (TypeError, ValueError): return d

def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")
    ser = URLSafeTimedSerializer(os.environ.get("SECRET_KEY", "dev-secret-change-me"))
    db.init_db()
    err = lambda m, code=400: (jsonify(error=m), code)

    def public_user(c, uid):
        u = dict(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        u.pop("password_hash")
        u["interests"] = [r[0] for r in c.execute("SELECT category_id FROM user_interests WHERE user_id=?", (uid,))]
        return u

    def login_resp(c, uid, code=200):
        return jsonify(token=ser.dumps(uid), user=public_user(c, uid)), code

    def auth(*roles):
        def deco(f):
            @wraps(f)
            def wrapper(*a, **k):
                try: uid = ser.loads(request.headers.get("Authorization", "").replace("Bearer ", ""), max_age=86400)
                except (BadSignature, SignatureExpired): return err("Please log in", 401)
                with db.session() as c:
                    u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
                    if not u: return err("Please log in", 401)
                    if roles and u["role"] not in roles: return err("You don't have permission to do that", 403)
                    g.user, g.c = u, c
                    return f(*a, **k)
            return wrapper
        return deco

    @app.get("/")
    def index(): return send_from_directory(app.static_folder, "index.html")

    # ---- Accounts & profile (Profile Service)
    @app.post("/api/register")
    def register():
        d = request.get_json(silent=True) or {}
        name, email, pw, role = (d.get("name") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password") or "", d.get("role", "attendee")
        if not name or "@" not in email or len(pw) < 6 or role not in ("attendee", "organizer"):
            return err("Name, a valid email, a password (6+ characters) and a role are required")
        with db.session() as c:
            if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone(): return err("Email already registered", 409)
            cur = c.execute("INSERT INTO users(name,email,password_hash,role,location) VALUES(?,?,?,?,?)",
                            (name, email, generate_password_hash(pw), role, d.get("location")))
            return login_resp(c, cur.lastrowid, 201)

    @app.post("/api/login")
    def login():
        d = request.get_json(silent=True) or {}
        with db.session() as c:
            u = c.execute("SELECT * FROM users WHERE email=?", ((d.get("email") or "").strip().lower(),)).fetchone()
            if not u or not check_password_hash(u["password_hash"], d.get("password") or ""): return err("Wrong email or password", 401)
            return login_resp(c, u["id"])

    @app.get("/api/me")
    @auth()
    def me(): return jsonify(public_user(g.c, g.user["id"]))

    @app.put("/api/profile")
    @auth()
    def profile():
        d = request.get_json(silent=True) or {}
        bmin, bmax = num(d.get("budget_min"), 0), num(d.get("budget_max"))
        if bmax is not None and bmax < bmin: return err("Maximum budget must be at least the minimum")
        g.c.execute("UPDATE users SET location=?, budget_min=?, budget_max=? WHERE id=?", (d.get("location"), bmin, bmax, g.user["id"]))
        g.c.execute("DELETE FROM user_interests WHERE user_id=?", (g.user["id"],))
        g.c.executemany("INSERT OR IGNORE INTO user_interests VALUES(?,?)", [(g.user["id"], i) for i in (num(x) for x in d.get("interests", [])) if i])
        return jsonify(public_user(g.c, g.user["id"]))

    # ---- Events (Event Service)
    @app.get("/api/categories")
    def categories():
        with db.session() as c: return jsonify([dict(r) for r in c.execute("SELECT * FROM categories ORDER BY id")])

    @app.get("/api/events")
    def events():
        a, w, p = request.args, ["e.status='approved'"], []
        if a.get("past") != "1": w.append("e.event_date>=date('now')")
        if a.get("q"): w.append("(e.title LIKE ? OR e.venue LIKE ? OR e.description LIKE ?)"); p += [f"%{a['q']}%"] * 3
        if a.get("category"): w.append("e.category_id=?"); p.append(num(a["category"], 0))
        if a.get("county"): w.append("e.county=?"); p.append(a["county"])
        if a.get("free") == "1": w.append("e.price=0")
        if a.get("from"): w.append("e.event_date>=?"); p.append(a["from"])
        if a.get("to"): w.append("e.event_date<=?"); p.append(a["to"])
        where, per, page = " AND ".join(w), min(max(num(a.get("per"), 9), 1), 50), max(num(a.get("page"), 1), 1)
        with db.session() as c:
            total = c.execute(f"SELECT COUNT(*) FROM events e WHERE {where}", p).fetchone()[0]
            rows = db.event_rows(c, where, p, limit=per, offset=(page - 1) * per)
        return jsonify(events=rows, total=total, page=page, pages=max(1, -(-total // per)))

    @app.get("/api/featured")
    def featured():
        with db.session() as c:
            return jsonify(db.event_rows(c, "e.status='approved' AND e.event_date>=date('now')", order="going DESC, e.event_date", limit=3))

    @app.get("/api/events/<int:eid>")
    def event_detail(eid):
        with db.session() as c:
            rows = db.event_rows(c, "e.id=? AND e.status='approved'", (eid,))
            if not rows: return err("Event not found", 404)
            rows[0]["reviews"] = [dict(r) for r in c.execute(
                "SELECT u.name, r.score, r.comment FROM ratings r JOIN users u ON u.id=r.user_id WHERE r.event_id=? AND r.comment IS NOT NULL AND r.comment!=''", (eid,))]
            return jsonify(rows[0])

    @app.post("/api/events")
    @auth("organizer", "admin")
    def create_event():
        d = request.get_json(silent=True) or {}
        try: date = dt.date.fromisoformat(d.get("event_date"))
        except (ValueError, TypeError): return err("event_date must be YYYY-MM-DD")
        price, cat = num(d.get("price"), -1), num(d.get("category_id"))
        if not (d.get("title") and d.get("venue") and d.get("county") and cat and price >= 0):
            return err("Title, venue, county and category are required, and price must be 0 or more")
        if date < dt.date.today(): return err("Event date cannot be in the past")
        if not g.c.execute("SELECT 1 FROM categories WHERE id=?", (cat,)).fetchone(): return err("Unknown category")
        status = "approved" if g.user["role"] == "admin" else "pending"
        cur = g.c.execute("INSERT INTO events(organizer_id,category_id,title,description,venue,county,event_date,price,status) VALUES(?,?,?,?,?,?,?,?,?)",
                          (g.user["id"], cat, d["title"].strip(), d.get("description", ""), d["venue"].strip(), d["county"], date.isoformat(), price, status))
        return jsonify(id=cur.lastrowid, status=status), 201

    @app.get("/api/my/events")
    @auth("organizer")
    def my_events(): return jsonify(db.event_rows(g.c, "e.organizer_id=?", (g.user["id"],), order="e.event_date DESC"))

    # ---- Recommender
    @app.get("/api/recommend")
    @auth("attendee")
    def recommend(): return jsonify(recommender.recommend(g.c, g.user["id"], num(request.args.get("n"), 8)))

    # ---- Payments, tickets, ratings
    @app.post("/api/pay")
    @auth("attendee")
    def pay():
        d = request.get_json(silent=True) or {}
        body, code = payments.pay_for_event(g.c, g.user["id"], num(d.get("event_id"), 0), (d.get("phone") or "").strip())
        return jsonify(body), code

    @app.get("/api/me/tickets")
    @auth("attendee")
    def tickets():
        rows = g.c.execute("""SELECT e.id, e.title, e.county, e.venue, e.event_date, e.price,
            (SELECT receipt FROM payments p WHERE p.user_id=a.user_id AND p.event_id=e.id AND p.status='paid') AS receipt,
            (SELECT score FROM ratings r WHERE r.user_id=a.user_id AND r.event_id=e.id) AS my_score
            FROM attendance a JOIN events e ON e.id=a.event_id WHERE a.user_id=? ORDER BY e.event_date DESC""", (g.user["id"],)).fetchall()
        today = dt.date.today().isoformat()
        return jsonify([{**dict(r), "can_rate": r["event_date"] <= today and r["my_score"] is None} for r in rows])

    @app.post("/api/rate")
    @auth("attendee")
    def rate():
        d = request.get_json(silent=True) or {}
        eid, score = num(d.get("event_id"), 0), num(d.get("score"), 0)
        ev = g.c.execute("SELECT event_date FROM events WHERE id=?", (eid,)).fetchone()
        if not 1 <= score <= 5: return err("Score must be 1 to 5")
        if not g.c.execute("SELECT 1 FROM attendance WHERE user_id=? AND event_id=?", (g.user["id"], eid)).fetchone(): return err("You can only rate events you attended", 403)
        if ev["event_date"] > dt.date.today().isoformat(): return err("You can rate this event after it takes place")
        g.c.execute("INSERT OR REPLACE INTO ratings(user_id,event_id,score,comment) VALUES(?,?,?,?)", (g.user["id"], eid, score, (d.get("comment") or "")[:300]))
        return jsonify(ok=True)

    # ---- Admin: moderation and user management
    @app.get("/api/admin/events")
    @auth("admin")
    def admin_events(): return jsonify(db.event_rows(g.c, "e.status=?", (request.args.get("status", "pending"),), order="e.event_date"))

    @app.put("/api/admin/events/<int:eid>")
    @auth("admin")
    def moderate(eid):
        st = (request.get_json(silent=True) or {}).get("status")
        if st not in ("approved", "rejected"): return err("status must be approved or rejected")
        if not g.c.execute("UPDATE events SET status=? WHERE id=?", (st, eid)).rowcount: return err("Event not found", 404)
        return jsonify(ok=True)

    @app.get("/api/admin/users")
    @auth("admin")
    def users(): return jsonify([dict(r) for r in g.c.execute("SELECT id,name,email,role,location FROM users ORDER BY id")])

    @app.put("/api/admin/users/<int:uid>")
    @auth("admin")
    def set_role(uid):
        role = (request.get_json(silent=True) or {}).get("role")
        if role not in ("attendee", "organizer", "admin") or uid == g.user["id"]: return err("Invalid role change")
        g.c.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
        return jsonify(ok=True)

    return app

if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
