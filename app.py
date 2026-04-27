from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3
import hashlib
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'iktisab_secret_2024'
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH = os.path.join(os.path.dirname(__file__), 'iktisab.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS vocabulary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word_ar TEXT NOT NULL,
        word_en TEXT NOT NULL,
        theme TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS scores (
        score_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        date TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL
    )''')
    # Seed admin account
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  ('admin', hash_password('admin123'), 'admin'))
    # Seed vocabulary
    c.execute("SELECT COUNT(*) FROM vocabulary")
    if c.fetchone()[0] == 0:
        words = [
            ('الأسرة', 'Family', 'Identity'),
            ('المدرسة', 'School', 'Education'),
            ('البيئة', 'Environment', 'Environment'),
            ('الصحة', 'Health', 'Health'),
            ('التكنولوجيا', 'Technology', 'Technology'),
            ('العمل', 'Work', 'Work'),
            ('الثقافة', 'Culture', 'Culture'),
            ('المجتمع', 'Society', 'Society'),
            ('السفر', 'Travel', 'Leisure'),
            ('الطعام', 'Food', 'Leisure'),
            ('الرياضة', 'Sport', 'Leisure'),
            ('الفن', 'Art', 'Culture'),
            ('السياسة', 'Politics', 'Society'),
            ('الاقتصاد', 'Economy', 'Work'),
            ('التعليم', 'Education', 'Education'),
            ('الطبيعة', 'Nature', 'Environment'),
            ('الأدب', 'Literature', 'Culture'),
            ('الدين', 'Religion', 'Identity'),
            ('الوطن', 'Homeland', 'Identity'),
            ('المستقبل', 'Future', 'Education'),
        ]
        c.executemany("INSERT INTO vocabulary (word_ar, word_en, theme) VALUES (?, ?, ?)", words)
    conn.commit()
    conn.close()


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm  = request.form.get('confirm', '').strip()

        if not username or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')
        if len(username) < 3:
            flash('Username must be at least 3 characters.', 'danger')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        if c.fetchone():
            conn.close()
            flash('Username already exists.', 'danger')
            return render_template('register.html')
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'user')",
                  (username, hash_password(password)))
        conn.commit()
        conn.close()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?",
                  (username, hash_password(password)))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT s.score, s.date FROM scores s
                 WHERE s.user_id = ? ORDER BY s.date DESC LIMIT 5''', (session['user_id'],))
    scores = c.fetchall()
    c.execute("SELECT COUNT(*) FROM vocabulary")
    vocab_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM documents")
    doc_count = c.fetchone()[0]
    conn.close()
    return render_template('dashboard.html', scores=scores, vocab_count=vocab_count, doc_count=doc_count)


@app.route('/flashcards')
def flashcards():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    theme_filter = request.args.get('theme', 'All')
    if theme_filter == 'All':
        c.execute("SELECT * FROM vocabulary ORDER BY RANDOM() LIMIT 10")
    else:
        c.execute("SELECT * FROM vocabulary WHERE theme = ? ORDER BY RANDOM() LIMIT 10", (theme_filter,))
    cards = [dict(row) for row in c.fetchall()]
    c.execute("SELECT DISTINCT theme FROM vocabulary")
    themes = ['All'] + [row['theme'] for row in c.fetchall()]
    conn.close()
    return render_template('flashcards.html', cards=cards, themes=themes, selected_theme=theme_filter)


@app.route('/save_score', methods=['POST'])
def save_score():
    if 'user_id' not in session:
        return {'status': 'error', 'message': 'Not logged in'}, 401
    data = request.get_json()
    score = data.get('score', 0)
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO scores (user_id, score, date) VALUES (?, ?, ?)",
              (session['user_id'], score, datetime.now().strftime('%Y-%m-%d %H:%M')))
    conn.commit()
    conn.close()
    return {'status': 'success', 'score': score}


@app.route('/resources')
def resources():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM documents")
    docs = c.fetchall()
    conn.close()
    return render_template('resources.html', docs=docs)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Admin access required.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('No file selected.', 'danger')
            return render_template('upload.html')
        if not file.filename.lower().endswith('.pdf'):
            flash('Only PDF files are allowed.', 'danger')
            return render_template('upload.html')
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO documents (file_name, file_path) VALUES (?, ?)",
                  (filename, file_path))
        conn.commit()
        conn.close()
        flash(f'File "{filename}" uploaded successfully.', 'success')
        return redirect(url_for('resources'))
    return render_template('upload.html')


@app.route('/download/<int:doc_id>')
def download(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
    doc = c.fetchone()
    conn.close()
    if not doc:
        flash('File not found.', 'danger')
        return redirect(url_for('resources'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], doc['file_name'], as_attachment=True)


@app.route('/admin/vocabulary', methods=['GET', 'POST'])
def manage_vocab():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Admin access required.', 'danger')
        return redirect(url_for('dashboard'))
    conn = get_db()
    c = conn.cursor()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            word_ar = request.form.get('word_ar', '').strip()
            word_en = request.form.get('word_en', '').strip()
            theme   = request.form.get('theme', '').strip()
            if word_ar and word_en and theme:
                c.execute("INSERT INTO vocabulary (word_ar, word_en, theme) VALUES (?, ?, ?)",
                          (word_ar, word_en, theme))
                conn.commit()
                flash('Word added successfully.', 'success')
        elif action == 'delete':
            word_id = request.form.get('word_id')
            c.execute("DELETE FROM vocabulary WHERE id = ?", (word_id,))
            conn.commit()
            flash('Word deleted.', 'success')
    c.execute("SELECT * FROM vocabulary ORDER BY theme")
    words = c.fetchall()
    conn.close()
    return render_template('manage_vocab.html', words=words)


@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT u.username, MAX(s.score) as best_score
                 FROM scores s JOIN users u ON s.user_id = u.user_id
                 GROUP BY s.user_id ORDER BY best_score DESC LIMIT 10''')
    leaders = c.fetchall()
    conn.close()
    return render_template('leaderboard.html', leaders=leaders)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/themes')
def themes():
    return render_template('themes.html')


@app.route('/texttypes')
def texttypes():
    return render_template('texttypes.html')


@app.route('/rubrics')
def rubrics():
    return render_template('rubrics.html')


@app.route('/oral')
def oral():
    return render_template('oral.html')


@app.route('/mistakes')
def mistakes():
    return render_template('mistakes.html')


@app.route('/strategy')
def strategy():
    return render_template('strategy.html')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
