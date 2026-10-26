"""Payment service + simulated M-Pesa gateway. Swap gateway_charge() for the Safaricom Daraja STK-push call in production."""
import re, secrets
from datetime import date

def gateway_charge(phone, amount):
    if not re.fullmatch(r"(?:\+?254|0)[17]\d{8}", phone or ""):
        return False, None, "Invalid M-Pesa number"
    if phone.endswith("000"):                      # demo: simulate a declined payment
        return False, None, "Payment declined: insufficient funds"
    return True, "MP" + secrets.token_hex(4).upper(), "OK"

def pay_for_event(c, user_id, event_id, phone):
    ev = c.execute("SELECT * FROM events WHERE id=? AND status='approved'", (event_id,)).fetchone()
    if not ev:
        return {"error": "Event not found"}, 404
    if ev["event_date"] < date.today().isoformat():
        return {"error": "This event has already happened"}, 400
    if c.execute("SELECT 1 FROM attendance WHERE user_id=? AND event_id=?", (user_id, event_id)).fetchone():
        return {"error": "You already have a ticket for this event"}, 409
    if ev["price"] == 0:
        c.execute("INSERT INTO attendance(user_id,event_id) VALUES(?,?)", (user_id, event_id))
        return {"status": "free", "message": "You're registered - this event is free."}, 201
    cur = c.execute("INSERT INTO payments(user_id,event_id,amount,status,phone) VALUES(?,?,?,'pending',?)",
                    (user_id, event_id, ev["price"], phone))
    ok, receipt, msg = gateway_charge(phone, ev["price"])
    c.execute("UPDATE payments SET status=?, receipt=? WHERE id=?", ("paid" if ok else "failed", receipt, cur.lastrowid))
    if not ok:
        return {"status": "failed", "error": msg}, 402
    c.execute("INSERT INTO attendance(user_id,event_id) VALUES(?,?)", (user_id, event_id))
    return {"status": "paid", "receipt": receipt, "message": f"Payment confirmed. Receipt {receipt}"}, 201
