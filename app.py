from flask import Flask, render_template, request, redirect, session, flash
import psycopg2
import bcrypt
import os
from dotenv import load_dotenv

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
                image TEXT
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/part_detail')
def part_detail():
    if 'username' not in session:
        return redirect('/')
    return render_template('part_detail.html')

@app.route('/style/<path:filename>')
def serve_style(filename):
    from flask import send_from_directory
    return send_from_directory('style', filename)

if __name__ == '__main__':
    app.run(debug=True)
