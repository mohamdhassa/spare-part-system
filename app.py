from flask import Flask, render_template, request, redirect, session, flash, send_from_directory
import psycopg2
import bcrypt
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid

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
                model TEXT,
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

@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    table_name = f"parts_{username}"
    keyword = request.form.get('keyword', '').strip()
    company = request.form.get('company', '').strip()
    year_from = request.form.get('year_from', '').strip()
    year_to = request.form.get('year_to', '').strip()

    query = f"SELECT id, name, part_number, shelf, amount, image FROM {table_name} WHERE 1=1"
    values = []

    if keyword:
        keyword_like = f"%{keyword}%"
        query += " AND (name ILIKE %s OR part_number ILIKE %s OR description ILIKE %s OR shelf ILIKE %s OR company ILIKE %s)"
        values += [keyword_like] * 5

    if company:
        query += " AND company = %s"
        values.append(company)

    if year_from:
        query += " AND year_from >= %s"
        values.append(int(year_from))

    if year_to:
        query += " AND year_to <= %s"
        values.append(int(year_to))

    query += " ORDER BY created_at DESC"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, values)
        parts = cur.fetchall()
    except Exception as e:
        flash(f"Failed to search parts: {e}")
        parts = []

    cur.close()
    conn.close()

    return render_template('home.html', username=username, parts=parts)


@app.route('/use_part', methods=['POST'])
def use_part():
    if 'username' not in session:
        return redirect('/')

    part_id = request.form.get('part_id')
    username = session['username']
    table_name = f"parts_{username}"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        UPDATE {table_name}
        SET amount = GREATEST(amount - 1, 0)
        WHERE id = %s
    """, (part_id,))
    conn.commit()
    cur.close()
    conn.close()

    return redirect('/home')

@app.route('/manage')
def manage():
    if 'username' not in session:
        return redirect('/')
    return render_template('manage_part.html', username=session['username'])


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
    model = data.get('model', '')
    year_from = int(data.get('year_from') or 0)
    year_to = int(data.get('year_to') or 0)
    pay_price = float(data.get('pay_price') or 0)
    sale_price = float(data.get('sale_price') or 0)
    image_url = data.get('image_url', '')
    created_at = datetime.now()

    filename = image_url.strip()

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
    (name, part_number, description, amount, shelf, company, model, year_from, year_to, pay_price, sale_price, image, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""", (
    name, part_number, description, amount, shelf, company, model,
    year_from, year_to, pay_price, sale_price, filename, created_at
))


    conn.commit()
    cur.close()
    conn.close()

    return redirect('/manage')

@app.route('/alerts')
def alerts():
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    table_name = f"parts_{username}"

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(f"""
            SELECT id, name, part_number, shelf, amount, image
            FROM {table_name}
            WHERE amount <= 2
            ORDER BY amount ASC
        """)
        low_stock_parts = cur.fetchall()
    except Exception as e:
        flash(f"Error loading low stock parts: {e}")
        low_stock_parts = []

    cur.close()
    conn.close()

    return render_template('alerts.html', parts=low_stock_parts)


# ✅ FIXED: Renamed this function to avoid route conflict
@app.route('/part_detail')
def part_detail_page():
    if 'username' not in session:
        return redirect('/')
    return render_template('part_detail.html')

@app.route('/part_detail/<int:part_id>')
def part_detail(part_id):
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    table_name = f"parts_{username}"

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(f"""
            SELECT name, part_number, description, amount, shelf, company, model,
                   year_from, year_to, pay_price, sale_price, image
            FROM {table_name}
            WHERE id = %s
        """, (part_id,))
        part = cur.fetchone()

        if not part:
            flash("Part not found")
            return redirect('/home')

        part_data = {
    'id': part_id,
    'name': part[0],
    'part_number': part[1],
    'description': part[2],
    'amount': part[3],
    'shelf': part[4],
    'company': part[5],
    'model': part[6],
    'year_from': part[7],
    'year_to': part[8],
    'pay_price': part[9],
    'sale_price': part[10],
    'image': part[11]
}


    except Exception as e:
        flash(f"Error loading part: {e}")
        return redirect('/home')
    finally:
        cur.close()
        conn.close()

    return render_template('part_detail.html', part=part_data)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/style/<path:filename>')
def serve_style(filename):
    return send_from_directory('style', filename)


@app.route('/add_quantity/<int:part_id>', methods=['POST'])
def add_quantity(part_id):
    if 'username' not in session:
        return redirect('/')

    qty = int(request.form.get('add_qty', 0))
    username = session['username']
    table_name = f"parts_{username}"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        UPDATE {table_name}
        SET amount = amount + %s
        WHERE id = %s
    """, (qty, part_id))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(f'/part_detail/{part_id}')


@app.route('/remove_quantity/<int:part_id>', methods=['POST'])
def remove_quantity(part_id):
    if 'username' not in session:
        return redirect('/')

    qty = int(request.form.get('remove_qty', 0))
    username = session['username']
    table_name = f"parts_{username}"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        UPDATE {table_name}
        SET amount = GREATEST(amount - %s, 0)
        WHERE id = %s
    """, (qty, part_id))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(f'/part_detail/{part_id}')
@app.route('/update_shelf/<int:part_id>', methods=['POST'])
def update_shelf(part_id):
    if 'username' not in session:
        return redirect('/')

    new_shelf = request.form.get('shelf', '').strip()
    if not new_shelf:
        flash("Shelf name cannot be empty")
        return redirect(f'/part_detail/{part_id}')

    username = session['username']
    table_name = f"parts_{username}"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        UPDATE {table_name}
        SET shelf = %s
        WHERE id = %s
    """, (new_shelf, part_id))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(f'/part_detail/{part_id}')



if __name__ == '__main__':
    app.run(debug=True)
