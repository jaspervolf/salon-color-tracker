"""
Gnuance - backend

This handles: storing data (SQLite), and routes (URLs) that the templates
use to read/write that data.

Routes:
  GET  /                                  -> list all clients
  GET  /clients/new   POST /clients/new   -> add a new client
  GET  /clients/<id>                      -> client profile (info + appointments)
  GET  /clients/<id>/edit   POST .../edit -> edit client info
  GET  /clients/<id>/formulas/new  POST   -> add a new formula for a client
  GET  /formulas/<id>/edit   POST .../edit -> view/edit one formula entry
  GET  /formulations                      -> all formulas across all clients
  GET  /clients/<id>/formulas              -> per-client formula view (latest + history)
  GET  /schedule[/<date>]                 -> day view of appointments
  GET  /appointments/new   POST           -> add a new appointment
  GET  /appointments/<id>/edit   POST     -> edit an appointment
  POST /appointments/<id>/delete          -> delete an appointment
  GET  /dispensary                        -> product shopping list
  POST /dispensary/add                    -> add an item to the list
  POST /dispensary/<id>/purchased         -> mark item purchased (removes it)
  POST /dispensary/<id>/delete            -> permanently delete an item

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

    # Dispensary table - salon product shopping list
    db.execute('''
        CREATE TABLE IF NOT EXISTS dispensary_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity TEXT,
            unit TEXT,
            notes TEXT,
            added_at TEXT NOT NULL,
            purchased INTEGER NOT NULL DEFAULT 0
        )
    ''')

    db.commit()


def today():
    return datetime.now().strftime('%Y-%m-%d')


def time_to_minutes(t):
    """Convert 'HH:MM' to total minutes since midnight."""
    h, m = map(int, t.split(':'))
    return h * 60 + m


def find_conflict(db, date, start_time, duration_minutes, exclude_id=None):
    """Return the first appointment on `date` that overlaps the proposed
    [start_time, start_time + duration) window, or None if clear.

    Uses a half-open interval check: two appointments overlap when
    A.start < B.end AND B.start < A.end.  An appointment with no
    duration is treated as a single point in time, so two back-to-back
    slots never conflict with each other."""
    start_min = time_to_minutes(start_time)
    dur = int(duration_minutes) if duration_minutes else 0
    end_min = start_min + dur

    query = '''
        SELECT a.*, c.name AS client_name
        FROM appointments a
        JOIN clients c ON c.id = a.client_id
        WHERE a.date = ?
    '''
    params = [date]
    if exclude_id is not None:
        query += ' AND a.id != ?'
        params.append(exclude_id)

    for row in db.execute(query, params).fetchall():
        row_start = time_to_minutes(row['start_time'])
        row_dur   = row['duration_minutes'] or 0
        row_end   = row_start + row_dur
        if start_min < row_end and row_start < end_min:
            return row
    return None


# -----------------------------------------------------------------------
# CLIENTS
# -----------------------------------------------------------------------

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
            'INSERT INTO clients (name, address, email, phone, birthday, availability_notes, created_date) VALUES (?, ?, ?, ?, ?, ?, ?)',
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
    return render_template('client_form.html', is_edit=False, client=None)


@app.route('/clients/<int:client_id>')
def client_profile(client_id):
    db = get_db()
    client = db.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    formula_count = db.execute(
        'SELECT COUNT(*) FROM formulas WHERE client_id = ?', (client_id,)
    ).fetchone()[0]
    return render_template('client_profile.html', client=client,
                           formula_count=formula_count)


@app.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
def client_edit(client_id):
    db = get_db()
    client = db.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
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
    return render_template('client_form.html', is_edit=True, client=client)


# -----------------------------------------------------------------------
# FORMULATIONS
# -----------------------------------------------------------------------

@app.route('/formulations')
def formulations():
    """All formulas across all clients, newest first."""
    db = get_db()
    formulas = db.execute(
        '''SELECT f.*, c.name AS client_name
           FROM formulas f
           JOIN clients c ON c.id = f.client_id
           ORDER BY f.created_date DESC, f.id DESC'''
    ).fetchall()
    return render_template('formulations.html', formulas=formulas)


@app.route('/clients/<int:client_id>/formulas')
def client_formulas(client_id):
    """Per-client formulas page: shows the most recent formula in full,
    with a compact list of older ones below and a + New Formulation link."""
    db = get_db()
    client = db.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    formulas = db.execute(
        'SELECT * FROM formulas WHERE client_id = ? ORDER BY created_date DESC, id DESC',
        (client_id,)
    ).fetchall()
    latest = formulas[0] if formulas else None
    older  = formulas[1:] if len(formulas) > 1 else []
    latest_mixes = []
    if latest:
        latest_mixes = db.execute(
            'SELECT * FROM formula_mixes WHERE formula_id = ? ORDER BY sort_order',
            (latest['id'],)
        ).fetchall()
    return render_template('client_formulas.html', client=client,
                           latest=latest, latest_mixes=latest_mixes, older=older)


@app.route('/clients/<int:client_id>/formulas/new', methods=['GET', 'POST'])
def formula_new(client_id):
    db = get_db()
    client = db.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()

    if request.method == 'POST':
        appointment_id = request.form.get('appointment_id') or None
        formula_id = db.execute(
            'INSERT INTO formulas (client_id, appointment_id, created_date, last_edited_date, consultation_notes, results_notes) VALUES (?, ?, ?, ?, ?, ?)',
            (client_id, appointment_id, today(), today(),
             request.form.get('consultation_notes', ''),
             request.form.get('results_notes', ''))
        ).lastrowid

        mix_indices = [int(x) for x in request.form.get('mix_indices', '0').split(',') if x.strip()]
        for i in mix_indices:
            db.execute(
                '''INSERT INTO formula_mixes
                   (formula_id, sort_order,
                    is_lightener, is_permanent, is_demi_permanent, is_deposit_only,
                    color_house_series,
                    dev_5, dev_10, dev_15, dev_20, dev_25, dev_30, dev_40,
                    mix_details, development_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    formula_id, i,
                    1 if f'mix_{i}_is_lightener'      in request.form else 0,
                    1 if f'mix_{i}_is_permanent'      in request.form else 0,
                    1 if f'mix_{i}_is_demi_permanent' in request.form else 0,
                    1 if f'mix_{i}_is_deposit_only'   in request.form else 0,
                    request.form.get(f'mix_{i}_color_house_series', ''),
                    1 if f'mix_{i}_dev_5'  in request.form else 0,
                    1 if f'mix_{i}_dev_10' in request.form else 0,
                    1 if f'mix_{i}_dev_15' in request.form else 0,
                    1 if f'mix_{i}_dev_20' in request.form else 0,
                    1 if f'mix_{i}_dev_25' in request.form else 0,
                    1 if f'mix_{i}_dev_30' in request.form else 0,
                    1 if f'mix_{i}_dev_40' in request.form else 0,
                    request.form.get(f'mix_{i}_mix_details', ''),
                    request.form.get(f'mix_{i}_development_time', ''),
                )
            )
        db.commit()

        if appointment_id:
            appt = db.execute('SELECT * FROM appointments WHERE id = ?', (appointment_id,)).fetchone()
            return redirect(url_for('schedule', date_str=appt['date']))
        return redirect(url_for('formulations'))

    appointment_id = request.args.get('appointment_id', type=int)
    back = request.args.get('back', url_for('formulations'))
    return render_template('formula_form.html', client=client, formula=None,
                           mixes=[], is_edit=False, appointment_id=appointment_id,
                           back=back)


@app.route('/formulas/<int:formula_id>/edit', methods=['GET', 'POST'])
def formula_edit(formula_id):
    db = get_db()
    formula = db.execute('SELECT * FROM formulas WHERE id = ?', (formula_id,)).fetchone()
    client  = db.execute('SELECT * FROM clients WHERE id = ?', (formula['client_id'],)).fetchone()
    mixes   = db.execute(
        'SELECT * FROM formula_mixes WHERE formula_id = ? ORDER BY sort_order',
        (formula_id,)
    ).fetchall()

    if request.method == 'POST':
        db.execute(
            'UPDATE formulas SET last_edited_date=?, consultation_notes=?, results_notes=? WHERE id=?',
            (today(),
             request.form.get('consultation_notes', ''),
             request.form.get('results_notes', ''),
             formula_id)
        )

        db.execute('DELETE FROM formula_mixes WHERE formula_id = ?', (formula_id,))

        mix_indices = [int(x) for x in request.form.get('mix_indices', '0').split(',') if x.strip()]
        for i in mix_indices:
            db.execute(
                '''INSERT INTO formula_mixes
                   (formula_id, sort_order,
                    is_lightener, is_permanent, is_demi_permanent, is_deposit_only,
                    color_house_series,
                    dev_5, dev_10, dev_15, dev_20, dev_25, dev_30, dev_40,
                    mix_details, development_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    formula_id, i,
                    1 if f'mix_{i}_is_lightener'      in request.form else 0,
                    1 if f'mix_{i}_is_permanent'      in request.form else 0,
                    1 if f'mix_{i}_is_demi_permanent' in request.form else 0,
                    1 if f'mix_{i}_is_deposit_only'   in request.form else 0,
                    request.form.get(f'mix_{i}_color_house_series', ''),
                    1 if f'mix_{i}_dev_5'  in request.form else 0,
                    1 if f'mix_{i}_dev_10' in request.form else 0,
                    1 if f'mix_{i}_dev_15' in request.form else 0,
                    1 if f'mix_{i}_dev_20' in request.form else 0,
                    1 if f'mix_{i}_dev_25' in request.form else 0,
                    1 if f'mix_{i}_dev_30' in request.form else 0,
                    1 if f'mix_{i}_dev_40' in request.form else 0,
                    request.form.get(f'mix_{i}_mix_details', ''),
                    request.form.get(f'mix_{i}_development_time', ''),
                )
            )
        db.commit()

        back = request.form.get('back', url_for('formulations'))
        return redirect(back)

    back = request.args.get('back', url_for('formulations'))
    return render_template('formula_form.html', client=client, formula=formula,
                           mixes=mixes, is_edit=True, appointment_id=None,
                           back=back)


# -----------------------------------------------------------------------
# SCHEDULE
# -----------------------------------------------------------------------

@app.route('/schedule', defaults={'date_str': None})
@app.route('/schedule/<date_str>')
def schedule(date_str):
    if date_str is None:
        date_str = today()
    try:
        current_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        current_date = datetime.now()
        date_str = today()

    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')

    db = get_db()
    appointments = db.execute(
        '''SELECT a.*, c.name AS client_name
           FROM appointments a
           JOIN clients c ON c.id = a.client_id
           WHERE a.date = ?
           ORDER BY a.start_time ASC''',
        (date_str,)
    ).fetchall()

    logged_formula_ids = {}
    for appt in appointments:
        formula = db.execute(
            'SELECT id FROM formulas WHERE appointment_id = ?', (appt['id'],)
        ).fetchone()
        if formula:
            logged_formula_ids[appt['id']] = formula['id']

    clients = db.execute('SELECT * FROM clients ORDER BY name').fetchall()

    return render_template(
        'schedule.html',
        appointments=appointments,
        logged_formula_ids=logged_formula_ids,
        date_str=date_str,
        display_date=current_date.strftime('%A, %B %-d, %Y'),
        prev_date=prev_date,
        next_date=next_date,
        clients=clients,
    )


@app.route('/appointments/new', methods=['GET', 'POST'])
def appointment_new():
    db = get_db()
    clients = db.execute('SELECT * FROM clients ORDER BY name').fetchall()

    if request.method == 'POST':
        conflict = find_conflict(
            db, request.form['date'], request.form['start_time'], request.form.get('duration_minutes'),
        )
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
            'INSERT INTO appointments (client_id, date, start_time, duration_minutes, notes, created_date) VALUES (?, ?, ?, ?, ?, ?)',
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


# -----------------------------------------------------------------------
# DISPENSARY - salon product shopping list
# -----------------------------------------------------------------------

@app.route('/dispensary')
def dispensary():
    db = get_db()
    items = db.execute(
        'SELECT * FROM dispensary_items WHERE purchased = 0 ORDER BY added_at DESC'
    ).fetchall()
    return render_template('dispensary.html', items=items)


@app.route('/dispensary/add', methods=['POST'])
def dispensary_add():
    name = request.form.get('name', '').strip()
    if not name:
        return redirect(url_for('dispensary'))
    db = get_db()
    db.execute(
        'INSERT INTO dispensary_items (name, quantity, unit, notes, added_at, purchased) VALUES (?, ?, ?, ?, ?, 0)',
        (
            name,
            request.form.get('quantity', '').strip() or None,
            request.form.get('unit', '').strip() or None,
            request.form.get('notes', '').strip() or None,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )
    )
    db.commit()
    return redirect(url_for('dispensary'))


@app.route('/dispensary/<int:item_id>/purchased', methods=['POST'])
def dispensary_purchased(item_id):
    db = get_db()
    db.execute('UPDATE dispensary_items SET purchased = 1 WHERE id = ?', (item_id,))
    db.commit()
    return redirect(url_for('dispensary'))


@app.route('/dispensary/<int:item_id>/delete', methods=['POST'])
def dispensary_delete(item_id):
    db = get_db()
    db.execute('DELETE FROM dispensary_items WHERE id = ?', (item_id,))
    db.commit()
    return redirect(url_for('dispensary'))


if __name__ == '__main__':
    init_db()
    # Debug mode is off by default - it's meant for active development
    # (auto-reload on code changes, the interactive debugger), not for
    # something running unattended on a network all day. Turn it on
    # explicitly when you're actively working on the code:
    #   GNUANCE_DEBUG=1 python3 app.py
    debug_mode = os.environ.get('GNUANCE_DEBUG') == '1'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
