import os, sys, tempfile, datetime as dt
os.environ["KE_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from app import create_app

@pytest.fixture(scope="module")
def client(): return create_app().test_client()

def hdr(client, email, pw):
    return {"Authorization": "Bearer " + client.post("/api/login", json={"email": email, "password": pw}).get_json()["token"]}

def test_browse_and_filters(client):
    d = client.get("/api/events").get_json()
    assert d["total"] > 5 and all(e["status"] == "approved" for e in d["events"])
    assert all(e["price"] == 0 for e in client.get("/api/events?free=1").get_json()["events"])
    assert all(e["county"] == "Mombasa" for e in client.get("/api/events?county=Mombasa").get_json()["events"])
    assert client.get("/api/events?q=marathon").get_json()["total"] == 1

def test_auth_rules(client):
    assert client.post("/api/login", json={"email": "amina@demo.ke", "password": "bad"}).status_code == 401
    assert client.post("/api/register", json={"name": "X", "email": "amina@demo.ke", "password": "secret1"}).status_code == 409
    assert client.post("/api/register", json={"name": "X", "email": "x@x.ke", "password": "1"}).status_code == 400
    assert client.get("/api/recommend").status_code == 401
    assert client.post("/api/events", json={}, headers=hdr(client, "amina@demo.ke", "pass123")).status_code == 403

def test_recommendations_respect_budget_and_history(client):
    recs = client.get("/api/recommend", headers=hdr(client, "amina@demo.ke", "pass123")).get_json()
    assert recs and all(r["price"] <= 3000 for r in recs)
    assert [r["score"] for r in recs] == sorted((r["score"] for r in recs), reverse=True)
    assert not {1, 2} & {r["id"] for r in recs}          # already attended
    assert recs[0]["category"] in ("Music", "Food & Drink")  # matches her interests

def test_payment_flow(client):
    h = hdr(client, "amina@demo.ke", "pass123")
    assert client.post("/api/pay", json={"event_id": 8, "phone": "abc"}, headers=h).status_code == 402
    assert client.post("/api/pay", json={"event_id": 8, "phone": "0700000000"}, headers=h).status_code == 402
    ok = client.post("/api/pay", json={"event_id": 8, "phone": "0712345678"}, headers=h)
    assert ok.status_code == 201 and ok.get_json()["receipt"].startswith("MP")
    assert client.post("/api/pay", json={"event_id": 8, "phone": "0712345678"}, headers=h).status_code == 409
    assert client.post("/api/pay", json={"event_id": 10, "phone": ""}, headers=h).get_json()["status"] == "free"

def test_rating_rules(client):
    h = hdr(client, "amina@demo.ke", "pass123")
    assert client.post("/api/rate", json={"event_id": 2, "score": 4}, headers=h).status_code == 200
    assert client.post("/api/rate", json={"event_id": 8, "score": 4}, headers=h).status_code == 400   # not yet happened
    assert client.post("/api/rate", json={"event_id": 3, "score": 4}, headers=h).status_code == 403   # not attended

def test_moderation_workflow(client):
    org, adm = hdr(client, "organizer@demo.ke", "org123"), hdr(client, "admin@demo.ke", "admin123")
    day = (dt.date.today() + dt.timedelta(days=20)).isoformat()
    r = client.post("/api/events", headers=org, json={"title": "Naivasha Boat Party", "category_id": 8, "venue": "Lake Naivasha", "county": "Nakuru", "event_date": day, "price": 700})
    eid = r.get_json()["id"]
    assert r.status_code == 201 and r.get_json()["status"] == "pending"
    assert client.get(f"/api/events/{eid}").status_code == 404
    assert any(e["id"] == eid for e in client.get("/api/admin/events", headers=adm).get_json())
    assert client.put(f"/api/admin/events/{eid}", json={"status": "approved"}, headers=adm).status_code == 200
    assert client.get(f"/api/events/{eid}").status_code == 200
