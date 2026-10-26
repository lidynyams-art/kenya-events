# KenyaEvents - Event Recommendation System (APT3065A Part III prototype)

Web app for discovering events across Kenya, modelled on the Japan Travel events page. Implements the Part II design:
REST API -> Profile / Event / Recommender / Payment services -> SQLite database, plus a simulated M-Pesa gateway.

## Run it
```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                                         # open http://127.0.0.1:5000
python -m pytest -q                                   # run the automated tests
```
The database (`events.db`) is created and seeded on first run. Delete it to reset. Event data is illustrative sample data.

## Demo accounts
| Role | Email | Password |
|---|---|---|
| Attendee | amina@demo.ke | pass123 |
| Organizer | organizer@demo.ke | org123 |
| Admin | admin@demo.ke | admin123 |

M-Pesa demo: any valid Kenyan number (e.g. 0712345678) succeeds; numbers ending in `000` are declined.

## Structure
| File | Role in the design |
|---|---|
| `app.py` | REST API: login, role checks, validation (18 endpoints) |
| `db.py` | Schema (the 8 ERD tables), seed data, query helpers |
| `recommender.py` | Hybrid scoring: content 40%, collaborative 25%, location 15%, rating 10%, budget 10% |
| `payments.py` | Payment service + simulated M-Pesa gateway |
| `static/` | Attendee app, organizer portal, admin dashboard (one role-aware web app) |
| `tests/test_api.py` | Auth, filters, recommender, payments, ratings, moderation |

## Suggested Git history (commit as you go, every member commits)
```bash
git init && git add requirements.txt db.py && git commit -m "Add database schema and seed data"
git add app.py && git commit -m "Add REST API with auth and event endpoints"
git add recommender.py && git commit -m "Add hybrid recommender service"
git add payments.py && git commit -m "Add payment service with simulated M-Pesa"
git add static/index.html static/style.css && git commit -m "Add Kenya-themed UI layout"
git add static/app.js && git commit -m "Add attendee, organizer and admin screens"
git add tests README.md && git commit -m "Add tests and documentation"
git remote add origin <your-repo-url> && git push -u origin main
```
