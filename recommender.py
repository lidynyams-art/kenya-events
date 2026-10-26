"""Recommender: hybrid content-based + collaborative scoring (see design: 'Score and rank')."""
from db import event_rows

W = {"content": 0.40, "collab": 0.25, "location": 0.15, "rating": 0.10, "budget": 0.10}

def recommend(c, uid, n=8):
    u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    explicit = {r[0] for r in c.execute("SELECT category_id FROM user_interests WHERE user_id=?", (uid,))}
    hist = c.execute("SELECT a.event_id, e.category_id FROM attendance a JOIN events e ON e.id=a.event_id "
                     "WHERE a.user_id=?", (uid,)).fetchall()
    attended = {r[0] for r in hist}
    implicit = {r[1] for r in hist} - explicit          # categories learned from attendance
    # Collaborative: weight each peer by how many events they share with the user
    collab = {}
    if attended:
        q = ",".join("?" * len(attended))
        peers = c.execute(f"SELECT user_id, COUNT(*) w FROM attendance WHERE event_id IN ({q}) AND user_id!=? "
                          f"GROUP BY user_id", (*attended, uid)).fetchall()
        for p in peers:
            for r in c.execute("SELECT event_id FROM attendance WHERE user_id=?", (p["user_id"],)):
                collab[r[0]] = collab.get(r[0], 0) + p["w"]
    top = max(collab.values(), default=1)
    out = []
    for e in event_rows(c, "e.status='approved' AND e.event_date>=date('now')"):
        if e["id"] in attended:
            continue
        if u["budget_max"] is not None and e["price"] > u["budget_max"]:
            continue                                     # hard budget filter
        content = 1.0 if e["category_id"] in explicit else 0.5 if e["category_id"] in implicit else 0.0
        cf = collab.get(e["id"], 0) / top
        loc = 1.0 if u["location"] and e["county"] == u["location"] else 0.0
        rating = (e["rating"] or 3.0) / 5
        bud = 1 - e["price"] / u["budget_max"] if u["budget_max"] else 0.5
        score = (W["content"] * content + W["collab"] * cf + W["location"] * loc +
                 W["rating"] * rating + W["budget"] * bud)
        why = []
        if content == 1.0: why.append(f"Matches your interest in {e['category']}")
        elif content: why.append(f"You've enjoyed {e['category']} events before")
        if cf: why.append("Popular with attendees like you")
        if loc: why.append(f"In {e['county']}")
        e.update(score=round(score, 3), reason=" · ".join(why) or "Trending in Kenya")
        out.append(e)
    out.sort(key=lambda x: -x["score"])
    out = out[:n]
    c.execute("DELETE FROM recommendations WHERE user_id=?", (uid,))   # cache for accuracy checks later
    c.executemany("INSERT INTO recommendations(user_id,event_id,score) VALUES(?,?,?)",
                  [(uid, e["id"], e["score"]) for e in out])
    return out
