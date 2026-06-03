from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
import sqlite3
import os

app = Flask(__name__, template_folder=os.path.join('birds', 'templates'))
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

DB_PATH = os.path.join('birds', 'ptaci.db')
AUTH_USERS = {
    'admin': 'admin123'
}

ALLOWED_SORT_COLUMNS = {
    "nazev", "vedecky_nazev", "rad", "celed",
    "delka_cm", "rozpeti_cm", "hmotnost_g",
    "status_ohrozeni", "typ_potravy", "migrace",
    "vyskyt_kontinent", "snuska_ks",
}
DEFAULT_SORT_COLUMN = "nazev"
DEFAULT_SORT_DIRECTION = "ASC"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bird_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            druh_ptaka TEXT NOT NULL,
            datum_pozorovani TEXT NOT NULL,
            lokalita TEXT NOT NULL,
            pocet_jedincu INTEGER,
            poznamka TEXT
        )
    ''')
    return conn

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped_view

@app.context_processor
def inject_auth_state():
    return {
        'logged_in': session.get('logged_in', False)
    }

def build_query(params):
    """
    Konstruuje WHERE klauzuli a seznam hodnot ze zadaných parametrů.
    Každou podmínku přidá jen pokud je parametr vyplněn.
    
    Args:
        params: dict s filtry (z request.args)
    
    Returns:
        tuple: (where_clause, values)
    """
    conditions = []
    values = []
    
    # Filtr podle řádu
    rad = params.get('rad', '').strip()
    if rad:
        conditions.append('rad = ?')
        values.append(rad)
    
    # Filtr podle typu potravy
    typ_potravy = params.get('typ_potravy', '').strip()
    if typ_potravy:
        conditions.append('typ_potravy = ?')
        values.append(typ_potravy)
    
    # Filtr podle kontinentu
    kontinent = params.get('vyskyt_kontinent', '').strip()
    if kontinent:
        conditions.append('vyskyt_kontinent = ?')
        values.append(kontinent)
    
    # Filtr podle migrace
    migrace = params.get('migrace', '').strip()
    if migrace in ['0', '1']:
        conditions.append('migrace = ?')
        values.append(int(migrace))
    
    # Filtr podle statusu ohrožení
    status = params.get('status_ohrozeni', '').strip()
    if status:
        conditions.append('status_ohrozeni = ?')
        values.append(status)
    
    # Filtr podle minimální hmotnosti
    hmotnost_min = params.get('hmotnost_min', '').strip()
    if hmotnost_min:
        try:
            conditions.append('hmotnost_g >= ?')
            values.append(int(hmotnost_min))
        except ValueError:
            pass
    
    # Filtr podle maximální hmotnosti
    hmotnost_max = params.get('hmotnost_max', '').strip()
    if hmotnost_max:
        try:
            conditions.append('hmotnost_g <= ?')
            values.append(int(hmotnost_max))
        except ValueError:
            pass
    
    # Spojit podmínky operátorem AND
    where_clause = ' AND '.join(conditions) if conditions else ''
    
    return where_clause, values

def get_filter_options(conn):
    """
    Načte unikátní hodnoty z databáze pro dropdowny.
    
    Args:
        conn: sqlite3 připojení
    
    Returns:
        dict: klíči jsou názvy filtrů, hodnoty jsou listy unikátních hodnot
    """
    cursor = conn.cursor()
    
    cursor.execute('SELECT DISTINCT rad FROM ptaci WHERE rad IS NOT NULL ORDER BY rad')
    rady = [row[0] for row in cursor.fetchall()]
    
    cursor.execute('SELECT DISTINCT typ_potravy FROM ptaci WHERE typ_potravy IS NOT NULL ORDER BY typ_potravy')
    typ_potravy_list = [row[0] for row in cursor.fetchall()]
    
    cursor.execute('SELECT DISTINCT vyskyt_kontinent FROM ptaci WHERE vyskyt_kontinent IS NOT NULL ORDER BY vyskyt_kontinent')
    kontinenty = [row[0] for row in cursor.fetchall()]
    
    cursor.execute('SELECT DISTINCT status_ohrozeni FROM ptaci WHERE status_ohrozeni IS NOT NULL ORDER BY status_ohrozeni')
    statusy = [row[0] for row in cursor.fetchall()]
    
    return {
        'rady': rady,
        'typ_potravy_list': typ_potravy_list,
        'kontinenty': kontinenty,
        'statusy': statusy
    }

def validate_record_form(form):
    errors = {}
    druh_ptaka = form.get('druh_ptaka', '').strip()
    datum_pozorovani = form.get('datum_pozorovani', '').strip()
    lokalita = form.get('lokalita', '').strip()
    pocet_jedincu = form.get('pocet_jedincu', '').strip()

    if not druh_ptaka:
        errors['druh_ptaka'] = 'Vyplňte druh ptáka.'
    if not datum_pozorovani:
        errors['datum_pozorovani'] = 'Vyplňte datum pozorování.'
    if not lokalita:
        errors['lokalita'] = 'Vyplňte lokalitu.'
    if pocet_jedincu:
        try:
            int(pocet_jedincu)
        except ValueError:
            errors['pocet_jedincu'] = 'Počet jedinců musí být celé číslo.'

    return errors

@app.route("/")
def dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    # Vytvořit WHERE klauzuli
    where_clause, params = build_query(request.args)

    # Získat statistiku
    stats_query = '''SELECT
        COUNT(*) as pocet,
        ROUND(AVG(delka_cm), 1) as prum_delka,
        MAX(hmotnost_g) as max_hmotnost,
        MIN(hmotnost_g) as min_hmotnost,
        ROUND(AVG(hmotnost_g), 1) as prum_hmotnost,
        ROUND(AVG(rozpeti_cm), 1) as prum_rozpeti
    FROM ptaci'''
    if where_clause:
        stats_query += ' WHERE ' + where_clause
    
    cursor.execute(stats_query, params)
    stats_row = cursor.fetchone()
    stats = dict(stats_row) if stats_row else {}

    # Bezpečné řazení podle povolených sloupců a směru
    sort_column = request.args.get('sort_by', '').strip()
    if sort_column not in ALLOWED_SORT_COLUMNS:
        sort_column = DEFAULT_SORT_COLUMN
    sort_order = request.args.get('sort_order', '').strip().upper()
    if sort_order not in ['ASC', 'DESC']:
        sort_order = DEFAULT_SORT_DIRECTION
    
    # Sestrojit SQL dotaz
    query = 'SELECT * FROM ptaci'
    if where_clause:
        query += ' WHERE ' + where_clause
    query += f' ORDER BY {sort_column} {sort_order}'
    
    # Spustit dotaz
    cursor.execute(query, params)
    ptaci = cursor.fetchall()
    
    # Načíst volby pro filtry
    filter_options = get_filter_options(conn)
    
    # Grafy - počet druhů podle řádu
    query_rad = 'SELECT rad, COUNT(*) as pocet FROM ptaci'
    if where_clause:
        query_rad += ' WHERE ' + where_clause
    query_rad += ' GROUP BY rad ORDER BY pocet DESC'
    cursor.execute(query_rad, params)
    druhy_rad = cursor.fetchall()
    graf_rad_labels = [r["rad"] for r in druhy_rad if r["rad"]]
    graf_rad_data = [r["pocet"] for r in druhy_rad if r["rad"]]
    
    # Grafy - průměrná hmotnost podle typu potravy
    query_potraba = 'SELECT typ_potravy, ROUND(AVG(hmotnost_g), 0) as prum FROM ptaci'
    if where_clause:
        query_potraba += ' WHERE ' + where_clause
    query_potraba += ' GROUP BY typ_potravy ORDER BY prum DESC'
    cursor.execute(query_potraba, params)
    potraba_data = cursor.fetchall()
    graf_potraba_labels = [r["typ_potravy"] for r in potraba_data if r["typ_potravy"]]
    graf_potraba_data = [r["prum"] for r in potraba_data if r["typ_potravy"]]
    
    # Grafy - tažní vs. netažní
    query_migrace = 'SELECT migrace, COUNT(*) as pocet FROM ptaci'
    if where_clause:
        query_migrace += ' WHERE ' + where_clause
    query_migrace += ' GROUP BY migrace'
    cursor.execute(query_migrace, params)
    migrace_data = cursor.fetchall()
    migrace_labels = []
    migrace_data_values = []
    for r in migrace_data:
        if r["migrace"] is not None:
            label = "Tažný" if r["migrace"] == 1 else "Netažný"
            migrace_labels.append(label)
            migrace_data_values.append(r["pocet"])
    
    # Grafy - počet druhů podle kontinentu
    query_kontinent = 'SELECT vyskyt_kontinent, COUNT(*) as pocet FROM ptaci'
    if where_clause:
        query_kontinent += ' WHERE ' + where_clause
    query_kontinent += ' GROUP BY vyskyt_kontinent ORDER BY pocet DESC'
    cursor.execute(query_kontinent, params)
    kontinent_data = cursor.fetchall()
    graf_kontinent_labels = [r["vyskyt_kontinent"] for r in kontinent_data if r["vyskyt_kontinent"]]
    graf_kontinent_data = [r["pocet"] for r in kontinent_data if r["vyskyt_kontinent"]]
    
    conn.close()
    
    return render_template('dashboard.html', 
                         ptaci=ptaci,
                         stats=stats,
                         rady=filter_options['rady'],
                         typ_potravy_list=filter_options['typ_potravy_list'],
                         kontinenty=filter_options['kontinenty'],
                         statusy=filter_options['statusy'],
                         filters=request.args,
                         graf_rad_labels=graf_rad_labels,
                         graf_rad_data=graf_rad_data,
                         graf_potraba_labels=graf_potraba_labels,
                         graf_potraba_data=graf_potraba_data,
                         migrace_labels=migrace_labels,
                         migrace_data=migrace_data_values,
                         graf_kontinent_labels=graf_kontinent_labels,
                         graf_kontinent_data=graf_kontinent_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if AUTH_USERS.get(username) == password:
            session['logged_in'] = True
            session['username'] = username
            flash('Přihlášení proběhlo úspěšně.', 'success')
            return redirect(request.args.get('next') or url_for('manage_records'))

        error = 'Neplatné přihlašovací údaje.'

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    flash('Byl(a) jste odhlášen(a).', 'success')
    return redirect(url_for('dashboard'))

@app.route('/manage')
@login_required
def manage_records():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bird_records ORDER BY id DESC')
    records = cursor.fetchall()
    conn.close()
    return render_template('manage.html', records=records)

@app.route('/manage/add', methods=['GET', 'POST'])
@login_required
def add_record():
    errors = {}
    if request.method == 'POST':
        errors = validate_record_form(request.form)
        if errors:
            return render_template('record_form.html', form_title='Přidat nový záznam', record=request.form, errors=errors)

        druh_ptaka = request.form.get('druh_ptaka', '').strip()
        datum_pozorovani = request.form.get('datum_pozorovani', '').strip()
        lokalita = request.form.get('lokalita', '').strip()
        pocet_jedincu = request.form.get('pocet_jedincu', '').strip()
        poznamka = request.form.get('poznamka', '').strip()

        pocet = int(pocet_jedincu) if pocet_jedincu else None

        conn = get_db()
        conn.execute(
            'INSERT INTO bird_records (druh_ptaka, datum_pozorovani, lokalita, pocet_jedincu, poznamka) VALUES (?, ?, ?, ?, ?)',
            (druh_ptaka, datum_pozorovani, lokalita, pocet, poznamka)
        )
        conn.commit()
        conn.close()
        flash('Záznam byl vytvořen.', 'success')
        return redirect(url_for('manage_records'))

    return render_template('record_form.html', form_title='Přidat nový záznam', record={}, errors=errors)

@app.route('/manage/edit/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit_record(record_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bird_records WHERE id = ?', (record_id,))
    record = cursor.fetchone()

    if record is None:
        conn.close()
        return abort(404)

    errors = {}
    if request.method == 'POST':
        errors = validate_record_form(request.form)
        if errors:
            conn.close()
            return render_template('record_form.html', form_title='Upravit záznam', record=request.form, errors=errors)

        druh_ptaka = request.form.get('druh_ptaka', '').strip()
        datum_pozorovani = request.form.get('datum_pozorovani', '').strip()
        lokalita = request.form.get('lokalita', '').strip()
        pocet_jedincu = request.form.get('pocet_jedincu', '').strip()
        poznamka = request.form.get('poznamka', '').strip()

        pocet = int(pocet_jedincu) if pocet_jedincu else None

        conn.execute(
            'UPDATE bird_records SET druh_ptaka = ?, datum_pozorovani = ?, lokalita = ?, pocet_jedincu = ?, poznamka = ? WHERE id = ?',
            (druh_ptaka, datum_pozorovani, lokalita, pocet, poznamka, record_id)
        )
        conn.commit()
        conn.close()
        flash('Záznam byl upraven.', 'success')
        return redirect(url_for('manage_records'))

    conn.close()
    return render_template('record_form.html', form_title='Upravit záznam', record=record, errors=errors)

@app.route('/manage/delete/<int:record_id>', methods=['POST'])
@login_required
def delete_record(record_id):
    conn = get_db()
    conn.execute('DELETE FROM bird_records WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()
    flash('Záznam byl odstraněn.', 'success')
    return redirect(url_for('manage_records'))

if __name__ == "__main__":
    app.run(debug=True)
