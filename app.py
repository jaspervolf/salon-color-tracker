"""
Gnuance - backend

This handles: storing data (SQLite), and routes (URLs) that the templates
use to read/write that data.

Routes:
  GET  /                                  -> list all clients
  GET  /clients/new   POST /clients/new   -> add a new client
  GET  /clients/<id>                      -> client profile + formula history
  GET  /clients/<id>/edit   POST .../edit -> edit client info
  GET  /clients/<id>/formulas/new  POST   -> add a new formula for a client
  GET  /formulas/<id>/edit   POST .../edit -> view/edit one formula entry
  GET  /schedule[/<date>]                 -> day view of appointments
  GET  /appointments/new   POST           -> add a new appointment
  GET  /appointments/<id>/edit   POST     -> edit an appointment
  POST /appointments/<id>/delete          -> delete an appointment

A single formula (one appointment) can contain multiple "formulation mixes"
(e.g. a root formula + a separate gloss). Those live in their own table,
formula_mixes, linked back to the formula by formula_id.

A formula can optionally link back to the appointment it was logged from
(appointment_id) - set when reached via the "Log visit" shortcut on the
schedule, null when logged the regular way from a client's profile page.
"""

from flask import Flask, render_template, request, redirect, url_for, g
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'salon.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')


def get_db():
    """Reuse one connection per request instead of opening a new one each time."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row  # lets us access columns by name, e.g. row['name']
    return db


@app.teardown_appcontext
def close_db(exception=None):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """Safe to call every time the app starts. CREATE TABLE IF NOT EXISTS
    handles brand new tables (and brand new databases) perfectly, but
    it's a no-op for tables that already exist - so when a column gets
    added to an existing table's schema (like dev_5..dev_40,
    color_house_series, and now appointment_id), it won't retroactively
    appear on a database that was created before that change existed.
    The block below patches in any columns missing from an older
    database, so this works correctly whether salon.db is brand new or
    has been around since early in development."""
    db = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r') as f:
        db.executescript(f.read())

    def ensure_column(table, column, column_type):
        existing = [row[1] for row in db.execute(f'PRAGMA table_info({table})').fetchall()]
        if column not in existing:
            db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {column_type}')

    ensure_column('formulas', 'appointment_id', 'INTEGER')
    ensure_column('formula_mixes', 'color_house_series', 'TEXT')
    for vol in (5, 10, 15, 20, 25, 30, 40):
        ensure_column('formula_mixes', f'dev_{vol}', 'INTEGER DEFAULT 0')

    db.commit()
    db.close()


def today():
    return datetime.now().strftime('%Y-%m-%d')


def save_mixes(db, formula_id, form):
    """Reads however many formulation mix boxes were submitted (could be
    1, could be 5 - the form tracks which ones via the mix_indices hidden
    field) and replaces whatever mixes existed for this formula with the
    submitted set. Simpler and more reliable than trying to figure out
    which individual boxes were added/edited/removed."""
    db.execute('DELETE FROM formula_mixes WHERE formula_id = ?', (formula_id,))

    indices_raw = form.get('mix_indices', '')
    indices = [i for i in indices_raw.split(',') if i != '']
    dev_volumes = [5, 10, 15, 20, 25, 30, 40]

    for sort_order, i in enumerate(indices):
        db.execute(
            '''INSERT INTO formula_mixes (
                formula_id, sort_order, is_lightener, is_permanent,
                is_demi_permanent, is_deposit_only, color_house_series,
                dev_5, dev_10, dev_15, dev_20, dev_25, dev_30, dev_40,
                mix_details, development_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                formula_id, sort_order,
                1 if form.get(f'mix_{i}_is_lightener') else 0,
                1 if form.get(f'mix_{i}_is_permanent') else 0,
                1 if form.get(f'mix_{i}_is_demi_permanent') else 0,
                1 if form.get(f'mix_{i}_is_deposit_only') else 0,
                form.get(f'mix_{i}_color_house_series', ''),
                *[1 if form.get(f'mix_{i}_dev_{vol}') else 0 for vol in dev_volumes],
                form.get(f'mix_{i}_mix_details', ''),
                form.get(f'mix_{i}_development_time', ''),
            )
        )


def time_to_minutes(time_str):
    """Converts 'HH:MM' into minutes since midnight, so two appointment
    times can be compared with simple integer math."""
    hours, minutes = time_str.split(':')
    return int(hours) * 60 + int(minutes)


def find_conflict(db, date, start_time, duration_minutes, exclude_id=None):
    """Returns the first existing appointment on the same day whose time
    range overlaps the given one, or None if the slot is clear. A missing
    or invalid duration defaults to 30 minutes for this check only - it
    doesn't change what's actually stored. exclude_id leaves one
    appointment out of the check, so editing an appointment without
    changing its time doesn't flag a conflict with itself."""
    try:
        duration = int(duration_minutes) if duration_minutes else 30
    except (TypeError, ValueError):
        duration = 30
    new_start = time_to_minutes(start_time)
    new_end = new_start + duration

    existing = db.execute(
        '''SELECT appointments.*, clients.name AS client_name
           FROM appointments JOIN clients ON appointments.client_id = clients.id
           WHERE appointments.date = ?''',
        (date,)
    ).fetchall()

    for appt in existing:
        if exclude_id is not None and appt['id'] == exclude_id:
            continue
        try:
            other_duration = int(appt['duration_minutes']) if appt['duration_minutes'] else 30
        except (TypeError, ValueError):
            other_duration = 30
        other_start = time_to_minutes(appt['start_time'])
        other_end = other_start + other_duration
        # Half-open interval overlap check: back-to-back appointments
        # (one ending exactly when the other starts) are NOT a conflict.
        if new_start < other_end and other_start < new_end:
            return appt
    return None


# ---------- Client routes ----------

@app.route('/')
def index():
    db = get_db()
    clients = db.execute('SELECT * FROM clients ORDER BY name').fetchall()
    return render_template('index.html', clients=clients)


@app.route('/clients/new', methods=['GET', 'POST'])
def client_new():
    if request.method == 'POST':
        db = get_db()
        db.execute(
            'INSERT INTO clients (name, address, email, phone, birthday, availability_notes, created_date) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (
                request.form['name'],
                request.form.get('address', ''),
                request.form.get('email', ''),
                request.form.get('phone', ''),
                request.form.get('birthday', ''),
                request.form.get('availability_notes', ''),
                today(),
            )
        )
        db.commit()
        return redirect(url_for('index'))
    return render_template('client_form.html', client=None)


@app.route('/clients/<int:client_id>')
def client_profile(client_id):
    db = get_db()
    client = db.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    formulas = db.execute(
        'SELECT * FROM formulas WHERE client_id = ? ORDER BY created_date DESC',
        (client_id,)
    ).fetchall()
    appointments = db.execute(
        'SELECT * FROM appointments WHERE client_id = ? AND date >= ? ORDER BY date, start_time',
        (client_id, today())
    ).fetchall()
    return render_template('client_profile.html', client=client, formulas=formulas, appointments=appointments)


@app.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
def client_edit(client_id):
    db = get_db()
    if request.method == 'POST':
        db.execute(
            'UPDATE clients SET name=?, address=?, email=?, phone=?, birthday=?, availability_notes=? WHERE id=?',
            (
                request.form['name'],
                request.form.get('address', ''),
                request.form.get('email', ''),
                request.form.get('phone', ''),
                request.form.get('birthday', ''),
                request.form.get('availability_notes', ''),
                client_id,
            )
        )
        db.commit()
        return redirect(url_for('client_profile', client_id=client_id))
    client = db.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    return render_template('client_form.html', client=client)


# ---------- Formula routes ----------

@app.route('/clients/<int:client_id>/formulas/new', methods=['GET', 'POST'])
def formula_new(client_id):
    db = get_db()
    if request.method == 'POST':
        now = today()
        cursor = db.execute(
            '''INSERT INTO formulas (
                client_id, appointment_id, created_date, last_edited_date,
                consultation_notes, results_notes
            ) VALUES (?, ?, ?, ?, ?, ?)''',
            (
                client_id,
                request.form.get('appointment_id') or None,
                now, now,
                request.form.get('consultation_notes', ''),
                request.form.get('results_notes', ''),
            )
        )
        formula_id = cursor.lastrowid
        save_mixes(db, formula_id, request.form)
        db.commit()
        return redirect(url_for('client_profile', client_id=client_id))
    # appointment_id arrives as a query string param when this page was
    # reached via the "Log visit" link on the schedule, so the new
    # formula gets linked back to that appointment on save.
    appointment_id = request.args.get('appointment_id')
    return render_template('formula_form.html', client_id=client_id, formula=None, mixes=[None], appointment_id=appointment_id)


@app.route('/formulas/<int:formula_id>/edit', methods=['GET', 'POST'])
def formula_edit(formula_id):
    db = get_db()
    formula = db.execute('SELECT * FROM formulas WHERE id = ?', (formula_id,)).fetchone()
    if request.method == 'POST':
        db.execute(
            '''UPDATE formulas SET
                last_edited_date=?, consultation_notes=?, results_notes=?
            WHERE id=?''',
            (
                today(),
                request.form.get('consultation_notes', ''),
                request.form.get('results_notes', ''),
                formula_id,
            )
        )
        save_mixes(db, formula_id, request.form)
        db.commit()
        return redirect(url_for('client_profile', client_id=formula['client_id']))

    mixes = db.execute(
        'SELECT * FROM formula_mixes WHERE formula_id = ? ORDER BY sort_order',
        (formula_id,)
    ).fetchall()
    if not mixes:
        # Defensive default: a formula should always show at least one box,
        # even if (e.g. from older data) it has none on record yet.
        mixes = [None]
    return render_template('formula_form.html', client_id=formula['client_id'], formula=formula, mixes=mixes, appointment_id=formula['appointment_id'])


# ---------- Appointment routes ----------

@app.route('/schedule')
@app.route('/schedule/<date_str>')
def schedule(date_str=None):
    db = get_db()
    if date_str is None:
        date_str = today()

    appointments = db.execute(
        '''SELECT appointments.*, clients.name AS client_name,
                  (SELECT id FROM formulas WHERE formulas.appointment_id = appointments.id) AS formula_id
           FROM appointments
           JOIN clients ON appointments.client_id = clients.id
           WHERE appointments.date = ?
           ORDER BY appointments.start_time''',
        (date_str,)
    ).fetchall()

    current = datetime.strptime(date_str, '%Y-%m-%d')
    prev_day = (current - timedelta(days=1)).strftime('%Y-%m-%d')
    next_day = (current + timedelta(days=1)).strftime('%Y-%m-%d')
    display_date = current.strftime('%A, %B %-d, %Y')

    return render_template(
        'schedule.html',
        appointments=appointments,
        date_str=date_str,
        display_date=display_date,
        prev_day=prev_day,
        next_day=next_day,
    )


@app.route('/appointments/new', methods=['GET', 'POST'])
def appointment_new():
    db = get_db()
    clients = db.execute('SELECT * FROM clients ORDER BY name').fetchall()

    if request.method == 'POST':
        conflict = find_conflict(db, request.form['date'], request.form['start_time'], request.form.get('duration_minutes'))
        if conflict:
            return render_template(
                'appointment_form.html', is_edit=False, clients=clients,
                prefill_date=request.form['date'],
                prefill_client_id=int(request.form['client_id']),
                prefill_start_time=request.form['start_time'],
                prefill_duration=request.form.get('duration_minutes', ''),
                prefill_notes=request.form.get('notes', ''),
                error=f"That overlaps {conflict['client_name']}'s {conflict['start_time']} appointment.",
            )
        db.execute(
            '''INSERT INTO appointments (client_id, date, start_time, duration_minutes, notes, created_date)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (
                request.form['client_id'],
                request.form['date'],
                request.form['start_time'],
                request.form.get('duration_minutes') or None,
                request.form.get('notes', ''),
                today(),
            )
        )
        db.commit()
        return redirect(url_for('schedule', date_str=request.form['date']))

    # Pre-fill the date (e.g. "+ New Appointment" from a specific day on
    # the schedule) and/or client (e.g. from a client's profile page),
    # whichever were passed in.
    return render_template(
        'appointment_form.html', is_edit=False, clients=clients,
        prefill_date=request.args.get('date', today()),
        prefill_client_id=request.args.get('client_id', type=int),
        prefill_start_time='', prefill_duration='', prefill_notes='',
        error=None,
    )


@app.route('/appointments/<int:appointment_id>/edit', methods=['GET', 'POST'])
def appointment_edit(appointment_id):
    db = get_db()
    appointment = db.execute('SELECT * FROM appointments WHERE id = ?', (appointment_id,)).fetchone()
    clients = db.execute('SELECT * FROM clients ORDER BY name').fetchall()

    if request.method == 'POST':
        conflict = find_conflict(
            db, request.form['date'], request.form['start_time'], request.form.get('duration_minutes'),
            exclude_id=appointment_id,
        )
        if conflict:
            return render_template(
                'appointment_form.html', is_edit=True, clients=clients,
                prefill_date=request.form['date'],
                prefill_client_id=int(request.form['client_id']),
                prefill_start_time=request.form['start_time'],
                prefill_duration=request.form.get('duration_minutes', ''),
                prefill_notes=request.form.get('notes', ''),
                error=f"That overlaps {conflict['client_name']}'s {conflict['start_time']} appointment.",
            )
        db.execute(
            '''UPDATE appointments SET client_id=?, date=?, start_time=?, duration_minutes=?, notes=?
               WHERE id=?''',
            (
                request.form['client_id'],
                request.form['date'],
                request.form['start_time'],
                request.form.get('duration_minutes') or None,
                request.form.get('notes', ''),
                appointment_id,
            )
        )
        db.commit()
        return redirect(url_for('schedule', date_str=request.form['date']))

    return render_template(
        'appointment_form.html', is_edit=True, clients=clients,
        prefill_date=appointment['date'],
        prefill_client_id=appointment['client_id'],
        prefill_start_time=appointment['start_time'],
        prefill_duration=appointment['duration_minutes'] or '',
        prefill_notes=appointment['notes'] or '',
        error=None,
    )


@app.route('/appointments/<int:appointment_id>/delete', methods=['POST'])
def appointment_delete(appointment_id):
    db = get_db()
    appointment = db.execute('SELECT * FROM appointments WHERE id = ?', (appointment_id,)).fetchone()
    date_str = appointment['date']
    db.execute('DELETE FROM appointments WHERE id = ?', (appointment_id,))
    db.commit()
    return redirect(url_for('schedule', date_str=date_str))


if __name__ == '__main__':
    init_db()
    # Debug mode is off by default - it's meant for active development
    # (auto-reload on code changes, the interactive debugger), not for
    # something running unattended on a network all day. Turn it on
    # explicitly when you're actively working on the code:
    #   GNUANCE_DEBUG=1 python3 app.py
    debug_mode = os.environ.get('GNUANCE_DEBUG') == '1'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
