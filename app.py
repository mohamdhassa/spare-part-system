from flask import Flask, render_template, request, redirect, session
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
def index():
    return render_template('index.html')  # your login page

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
    result = cur.fetchone()
    cur.close()
    conn.close()

    if result and bcrypt.checkpw(password.encode('utf-8'), result[0].encode('utf-8')):
        session['username'] = username
        return redirect('/home')
    return "Invalid login", 401

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect('/')
    return render_template('home.html')
