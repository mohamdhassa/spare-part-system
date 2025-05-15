from flask import Flask, render_template, request, redirect, session, flash, send_from_directory
import psycopg2
import bcrypt
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime  # ✅ Added missing import

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-very-secret-key'

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

@app.route('/')
def login_page():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
        result = cur.fetchone()

        if result is None or not bcrypt.checkpw(password.encode(), result[0].encode()):
            flash("Invalid username or password")
            return redirect('/')

        session['username'] = username

        # Create user-specific parts table if not exists
        table_name = f"parts_{username}"
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                name TEXT,
                part_number TEXT,
                description TEXT,
                amount INTEGER,
                shelf TEXT,
                company TEXT,
                year_from INTEGER,
                year_to INTEGER,
                pay_price NUMERIC,
                sale_price NUMERIC,
                image TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()

        return redirect('/home')

    except Exception as e:
        flash(f"Internal error: {e}")
        return redirect('/')

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect('/')
    return render_template('home.html')

@app.route('/manage')
def manage():
    if 'username' not in session:
        return redirect('/')
    return render_template('manage_part.html')

@app.route('/alerts')
def alerts():
    if 'username' not in session:
        return redirect('/')
    return render_template('alerts.html')

@app.route('/part_detail')
def part_detail():
    if 'username' not in session:
        return redirect('/')
    return render_template('part_detail.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/style/<path:filename>')
def serve_style(filename):
    return send_from_directory('style', filename)

@app.route('/add_part', methods=['POST'])
def add_part():
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    table_name = f"parts_{username}"

    data = request.form
    name = data.get('name', '')
    part_number = data.get('part_number', '')
    description = data.get('description', '')
    amount = int(data.get('amount') or 0)
    shelf = data.get('shelf', '')
    company = data.get('company', '')
    year_from = int(data.get('year_from') or 0)
    year_to = int(data.get('year_to') or 0)
    pay_price = float(data.get('pay_price') or 0)
    sale_price = float(data.get('sale_price') or 0)
    image_url = data.get('image_url', '')
    created_at = datetime.now()

    filename = image_url.strip()

    # Save to DB
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"SELECT id, amount FROM {table_name} WHERE part_number = %s", (part_number,))
    existing = cur.fetchone()

    if existing:
        new_amount = existing[1] + amount
        cur.execute(f"""
            UPDATE {table_name}
            SET amount = %s
            WHERE id = %s
        """, (new_amount, existing[0]))
    else:
        cur.execute(f"""
            INSERT INTO {table_name}
            (name, part_number, description, amount, shelf, company, year_from, year_to, pay_price, sale_price, image, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            name, part_number, description, amount, shelf, company,
            year_from, year_to, pay_price, sale_price, filename, created_at
        ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect('/manage')


if __name__ == '__main__':
    app.run(debug=True)
