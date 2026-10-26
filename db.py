"""Database layer: schema (matches the ERD in the design), seed data, helpers."""
import os, sqlite3, datetime as dt
from contextlib import contextmanager
from werkzeug.security import generate_password_hash as h

DB = os.environ.get("KE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'attendee' CHECK(role IN('attendee','organizer','admin')),
  location TEXT, budget_min INTEGER DEFAULT 0, budget_max INTEGER);
CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS user_interests(user_id INTEGER REFERENCES users(id), category_id INTEGER REFERENCES categories(id),
  PRIMARY KEY(user_id, category_id));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, organizer_id INTEGER NOT NULL REFERENCES users(id),
  category_id INTEGER NOT NULL REFERENCES categories(id), title TEXT NOT NULL, description TEXT, venue TEXT NOT NULL,
  county TEXT NOT NULL, event_date TEXT NOT NULL, price INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN('pending','approved','rejected')));
CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  event_id INTEGER NOT NULL REFERENCES events(id), attended_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, event_id));
CREATE TABLE IF NOT EXISTS ratings(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  event_id INTEGER NOT NULL REFERENCES events(id), score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5), comment TEXT,
  UNIQUE(user_id, event_id));
CREATE TABLE IF NOT EXISTS recommendations(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  event_id INTEGER NOT NULL REFERENCES events(id), score REAL, generated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  event_id INTEGER NOT NULL REFERENCES events(id), amount INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN('pending','paid','failed')), phone TEXT, receipt TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

CATS = ["Music", "Food & Drink", "Culture", "Sports", "Nature & Safari", "Arts", "Business & Tech", "Nightlife"]

# (title, category, venue, county, days from today, price KSh, description) - illustrative sample data
EVENTS = [
 ("Koroga Festival", "Music", "Bomas of Kenya", "Nairobi", -40, 3500, "Food, music and good vibes in Nairobi's favourite picnic-style festival."),
 ("Nairobi Restaurant Week", "Food & Drink", "Various venues, Westlands", "Nairobi", -25, 0, "Set-menu tastings from the city's best kitchens."),
 ("Mombasa Carnival", "Culture", "Mama Ngina Waterfront", "Mombasa", -30, 0, "A colourful street parade celebrating coastal culture."),
 ("Rhino Charge", "Sports", "Kedong Valley", "Nakuru", -20, 1500, "Off-road 4x4 challenge raising funds for conservation."),
 ("Nairobi Art Week", "Arts", "Nairobi National Museum", "Nairobi", -15, 500, "Exhibitions and studio walks by East African artists."),
 ("Jazz Lounge Night", "Music", "Kasarani Gardens", "Nairobi", 6, 2500, "An evening of live jazz under the stars."),
 ("Lamu Cultural Festival", "Culture", "Lamu Old Town", "Lamu", 21, 1000, "Dhow races, donkey races, henna and Swahili poetry on the island."),
 ("Nairobi City Marathon", "Sports", "Uhuru Gardens", "Nairobi", 30, 2000, "5K, 10K, half and full marathon through the capital."),
 ("Maasai Mara Migration Weekend", "Nature & Safari", "Maasai Mara National Reserve", "Narok", 45, 18000, "Watch the great wildebeest crossing with guided game drives."),
 ("Kisumu Lake Festival", "Culture", "Dunga Beach", "Kisumu", 12, 0, "Fishing-village food, boat rides and Luo music on Lake Victoria."),
 ("Nairobi Tech Week", "Business & Tech", "KICC", "Nairobi", 18, 1500, "Talks, demos and networking for builders and founders."),
 ("Nyama Choma Festival", "Food & Drink", "Uhuru Gardens", "Nairobi", 9, 1000, "Kenya's favourite roast meat, live bands and family games."),
 ("Diani Sunset Beach Party", "Nightlife", "Diani Beach", "Kwale", 14, 1500, "DJs, bonfires and sunset sessions on the white sand."),
 ("Swahili Food Night", "Food & Drink", "Fort Jesus", "Mombasa", 16, 800, "Biryani, pilau and coconut sweets in a historic fort."),
 ("Mt Kenya Sunrise Hike", "Nature & Safari", "Sirimon Gate", "Nyeri", 11, 2500, "Guided day hike with sunrise views over the moorlands."),
 ("Lake Nakuru Flamingo Walk", "Nature & Safari", "Lake Nakuru National Park", "Nakuru", 8, 500, "Birdwatching with a ranger-led guide."),
 ("Gallery Night", "Arts", "GoDown Arts Centre", "Nairobi", 4, 0, "Open studios, live painting and a pop-up market."),
 ("Rooftop Afrobeats Night", "Nightlife", "Westlands Rooftop", "Nairobi", 2, 1000, "Afrobeats and amapiano with city views."),
 ("Magical Kenya Open", "Sports", "Muthaiga Golf Club", "Nairobi", 60, 3000, "Professional golf tournament with a fan village."),
]
ATTEND = [(3,1),(3,2),(4,1),(4,4),(5,3),(5,5),(5,2),(4,6),(4,8),(5,12),(5,7)]
RATINGS = [(3,1,5),(4,1,4),(4,4,5),(5,3,5),(5,5,4),(5,2,3)]

EVENT_SQL = """SELECT e.*, c.name AS category, u.name AS organizer,
 (SELECT ROUND(AVG(score),1) FROM ratings r WHERE r.event_id=e.id) AS rating,
 (SELECT COUNT(*) FROM attendance a WHERE a.event_id=e.id) AS going
 FROM events e JOIN categories c ON c.id=e.category_id JOIN users u ON u.id=e.organizer_id"""

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

@contextmanager
def session():
    c = conn()
    try:
        yield c
        c.commit()
    finally:
        c.close()

def event_rows(c, where="1=1", args=(), order="e.event_date, e.id", limit=None, offset=0):
    sql = f"{EVENT_SQL} WHERE {where} ORDER BY {order}"  # where/order are internal constants, values are bound
    if limit:
        sql += f" LIMIT {int(limit)} OFFSET {int(offset)}"
    return [dict(r) for r in c.execute(sql, args)]

def init_db():
    with session() as c:
        c.executescript(SCHEMA)
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        c.executemany("INSERT INTO categories(name) VALUES(?)", [(n,) for n in CATS])
        users = [("Admin", "admin@demo.ke", "admin123", "admin", "Nairobi", 0, None),
                 ("Safari Events Ltd", "organizer@demo.ke", "org123", "organizer", "Nairobi", 0, None),
                 ("Amina Wanjiru", "amina@demo.ke", "pass123", "attendee", "Nairobi", 0, 3000),
                 ("Brian Otieno", "brian@demo.ke", "pass123", "attendee", "Nairobi", 0, 5000),
                 ("Cynthia Mwangi", "cynthia@demo.ke", "pass123", "attendee", "Mombasa", 0, 2000)]
        c.executemany("INSERT INTO users(name,email,password_hash,role,location,budget_min,budget_max) VALUES(?,?,?,?,?,?,?)",
                      [(n, e, h(p), r, l, a, b) for n, e, p, r, l, a, b in users])
        c.executemany("INSERT INTO user_interests VALUES(?,?)", [(3,1),(3,2),(4,4),(4,5),(5,3),(5,6)])
        today = dt.date.today()
        for t, cat, v, co, off, pr, d in EVENTS:
            c.execute("INSERT INTO events(organizer_id,category_id,title,description,venue,county,event_date,price,status) "
                      "VALUES(2,?,?,?,?,?,?,?,'approved')",
                      (CATS.index(cat) + 1, t, d, v, co, (today + dt.timedelta(days=off)).isoformat(), pr))
        c.executemany("INSERT INTO attendance(user_id,event_id) VALUES(?,?)", ATTEND)
        c.executemany("INSERT INTO ratings(user_id,event_id,score) VALUES(?,?,?)", RATINGS)
