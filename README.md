# Gnuance

*Free as in Formulation*

A free, open-source, local-first client and color formula tracker for
independent hairstylists. Runs entirely on your own hardware — a
Raspberry Pi 500 in this build — with no internet connection, cloud
account, or subscription required. The name and tagline are a nod to the
GNU Project: free as in freedom, not free as in beer.

## What's here

- `app.py` — Flask backend (routes, database queries)
- `schema.sql` — database structure (clients, formulas, formula mixes)
- `templates/` — HTML pages
- `static/style.css` — styling
- `static/app.js` — font toggle, phone formatting, client search,
  add/remove formulation boxes
- `static/fonts/` — self-hosted fonts (Atkinson Hyperlegible,
  OpenDyslexic, GNU FreeFont) — no CDN dependency, so the app never
  breaks just because the salon's wifi hiccups
- `requirements.txt` — Python dependencies (just Flask)
- `gnuance.service` — systemd service so Flask starts automatically on boot
- `labwc-autostart` — kiosk-mode browser launch script
- `salon.db` — created automatically on first run, not included in the
  repo (this is where real client data lives, so it's gitignored)

## Setup

```bash
cd gnuance
sudo apt install python3-flask
python3 app.py
```

Then open a browser to `http://localhost:5000`. The first run creates
`salon.db` automatically.

If you'd rather keep dependencies isolated in a virtual environment
instead of installing system-wide, `requirements.txt` is included for
that instead:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

By default the app runs with Flask's debug mode off, which is what you
want for normal day-to-day use. If you're actively working on the code
and want auto-reload-on-save and the interactive debugger, turn it on
explicitly:

```bash
GNUANCE_DEBUG=1 python3 app.py
```

## Routes

| URL | Purpose |
|---|---|
| `/` | List of all clients, with search |
| `/clients/new` | Add a new client |
| `/clients/<id>` | View one client + their formulation history |
| `/clients/<id>/edit` | Edit client info |
| `/clients/<id>/formulas/new` | Add a new formulation entry for that client |
| `/formulas/<id>/edit` | View/edit one formulation entry |

## Running automatically on boot (kiosk mode)

Gnuance can start itself on boot and open full-screen, so the Pi just
turns on straight into the app with no manual steps.

**1. Flask starts on boot**, independent of any desktop login, via the
included systemd service:

```bash
sudo tee /etc/systemd/system/gnuance.service > /dev/null < gnuance.service
sudo systemctl daemon-reload
sudo systemctl enable --now gnuance.service
```

**2. The browser opens automatically, full-screen.** This part needs
Chromium specifically — its kiosk mode is far more reliably supported on
Raspberry Pi OS than other browsers' equivalents.

```bash
sudo apt install -y curl
sudo apt install -y chromium-browser || sudo apt install -y chromium

mkdir -p ~/.config/labwc
cp labwc-autostart ~/.config/labwc/autostart
chmod +x ~/.config/labwc/autostart
```

Reboot to test. See the comments inside `labwc-autostart` for what each
part of the script does and why.

**Chromium isn't required to use Gnuance** — it's only needed for the
automatic full-screen kiosk experience. Without it, Flask still starts on
boot the same as always; you'd just open whatever browser you already
have and go to `http://localhost:5000` yourself, rather than the app
appearing automatically.

Troubleshooting, if the kiosk doesn't appear after reboot:

```bash
systemctl status gnuance     # is Flask actually running?
journalctl -u gnuance -e     # recent Flask errors, if any
curl http://localhost:5000   # does Flask answer at all?
```

## Design notes

Dark, tactile, vintage-inspired interface. Two body fonts are available
via a toggle in the header (Atkinson Hyperlegible and OpenDyslexic), so
each stylist can pick whichever is easier for them to read — the choice
is remembered per-browser. The wordmark itself always renders in GNU
FreeFont regardless of that toggle, since a logo should look like the
logo.

Formulations don't keep version history — editing one overwrites the
previous version in place. This was a deliberate choice to keep the
interface simple rather than an oversight: `created_date` and
`last_edited_date` are tracked on every formula, so you can always see
*that* something changed and *when*, even though the prior version isn't
kept around.

## What's next

- A simple one-page site at gnuance.com introducing the project
- A scheduling module, kept separate from the formula tracker once this
  is solid in daily use — SQLite works well for a single station, but a
  shared schedule across multiple stations would need a different
  approach
