from flask import Flask, render_template, request, redirect, session
import psycopg2
import bcrypt
import os
from dotenv import load_dotenv
load_dotenv()



app = Flask(__name__)
app.secret_key = 'your-very-secret-key'  # Use a secure random key


try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    print("✅ Connected to Supabase successfully.")
    conn.close()
except Exception as e:
    print("❌ Connection failed:", e)


# Supabase DB connection
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
    return render_template('index.html')  # your login.html

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = get_connection()
    cur = conn.cursor()

    # Check for username and get hashed password
    cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
    result = cur.fetchone()

    if result is None or not bcrypt.checkpw(password.encode(), result[0].encode()):
        cur.close()
        conn.close()
        return "Invalid username or password", 401

    # Save login
    session['username'] = username

    # Create parts_<username> table if not exists
    user_table = f"parts_{username}"
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {user_table} (
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

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect('/')
    return render_template('home.html')  # your styled home.html

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
