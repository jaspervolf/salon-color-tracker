# Salon Color Tracker

A simple, local-first client + color formula tracker. Runs entirely on your
Pi 500, no internet or cloud account needed.

## What's here

- `schema.sql` — the database structure (clients table, formulas table)
- `app.py` — the Flask backend (routes, database queries)
- `templates/` — the HTML pages (this is what you'll be customizing)
- `static/style.css` — placeholder styling, yours to redesign
- `salon.db` — created automatically the first time you run the app (not included)

## Setup on the Pi 500

```bash
cd salon_tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open a browser to `http://localhost:5000`.

The first run will create `salon.db` automatically and print a confirmation.

## What each route does

| URL | Purpose |
|---|---|
| `/` | List of all clients |
| `/clients/new` | Add a new client |
| `/clients/<id>` | View one client + their formula history |
| `/clients/<id>/edit` | Edit client info |
| `/clients/<id>/formulas/new` | Add a new formula entry for that client |
| `/formulas/<id>/edit` | View/edit one formula entry |

## Where to go from here (Phase 3 — yours)

The HTML in `templates/` works but is intentionally undressed. This is where
the dyslexia-friendly, low-clutter design you described actually happens:

- Pick a typeface (OpenDyslexic is worth a look, but test a few — readable
  sans-serifs with generous letter spacing matter more than any single
  "dyslexia font")
- Generous line-height and spacing (already started in style.css, push it further)
- Consider whether checkboxes/buttons need to be bigger/easier to hit
- Decide on a color scheme with strong contrast but not harsh white-on-black

Everything you need to know is in `static/style.css` and the `templates/*.html`
files — the backend won't need to change for any of this.

## Later phases

- Phase 4: client photos, search, autostart on boot (so the Pi just boots
  straight into this in a browser kiosk)
- Phase 5: scheduling module — separate from this once the formula tracker
  is solid and in daily use
