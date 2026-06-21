"""
Salon Color Tracker - backend

This handles: storing data (SQLite), and routes (URLs) that the templates
use to read/write that data. You shouldn't need to touch this file much
while building out the look and feel in templates/ - that's the next phase.

Routes:
  GET  /                                  -> list all clients
  GET  /clients/new   POST /clients/new   -> add a new client
  GET  /clients/<id>                      -> client profile + formula history
  GET  /clients/<id>/edit   POST .../edit -> edit client info
  GET  /clients/<id>/formulas/new  POST   -> add a new formula for a client
  GET  /formulas/<id>/edit   POST .../edit -> view/edit one formula entry
"""

from flask import Flask, render_template, request, redirect, url_for, g
import sqlite3
import os
from datetime import datetime

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
    db = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r') as f:
        db.executescript(f.read())
    db.close()


def today():
    return datetime.now().strftime('%Y-%m-%d')


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
    return render_template('client_profile.html', client=client, formulas=formulas)


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
        db.execute(
            '''INSERT INTO formulas (
                client_id, created_date, last_edited_date, consultation_notes,
                brand, line, is_lightener, is_permanent, is_demi_permanent, is_deposit_only,
                formula_details, developer, processing_time, results_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                client_id, now, now,
                request.form.get('consultation_notes', ''),
                request.form.get('brand', ''),
                request.form.get('line', ''),
                1 if request.form.get('is_lightener') else 0,
                1 if request.form.get('is_permanent') else 0,
                1 if request.form.get('is_demi_permanent') else 0,
                1 if request.form.get('is_deposit_only') else 0,
                request.form.get('formula_details', ''),
                request.form.get('developer', ''),
                request.form.get('processing_time', ''),
                request.form.get('results_notes', ''),
            )
        )
        db.commit()
        return redirect(url_for('client_profile', client_id=client_id))
    return render_template('formula_form.html', client_id=client_id, formula=None)


@app.route('/formulas/<int:formula_id>/edit', methods=['GET', 'POST'])
def formula_edit(formula_id):
    db = get_db()
    formula = db.execute('SELECT * FROM formulas WHERE id = ?', (formula_id,)).fetchone()
    if request.method == 'POST':
        db.execute(
            '''UPDATE formulas SET
                last_edited_date=?, consultation_notes=?, brand=?, line=?,
                is_lightener=?, is_permanent=?, is_demi_permanent=?, is_deposit_only=?,
                formula_details=?, developer=?, processing_time=?, results_notes=?
            WHERE id=?''',
            (
                today(),
                request.form.get('consultation_notes', ''),
                request.form.get('brand', ''),
                request.form.get('line', ''),
                1 if request.form.get('is_lightener') else 0,
                1 if request.form.get('is_permanent') else 0,
                1 if request.form.get('is_demi_permanent') else 0,
                1 if request.form.get('is_deposit_only') else 0,
                request.form.get('formula_details', ''),
                request.form.get('developer', ''),
                request.form.get('processing_time', ''),
                request.form.get('results_notes', ''),
                formula_id,
            )
        )
        db.commit()
        return redirect(url_for('client_profile', client_id=formula['client_id']))
    return render_template('formula_form.html', client_id=formula['client_id'], formula=formula)


if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()
        print('Database created at', DB_PATH)
    app.run(host='0.0.0.0', port=5000, debug=True)
