from flask import Flask, render_template, request, redirect, session, flash, send_from_directory
import psycopg2
import bcrypt
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid
from flask_session import Session
from flask import request
from flask import Flask, render_template, request, session, redirect
from datetime import datetime
from collections import defaultdict
from psycopg2.extras import RealDictCursor
import psycopg2
import json
from flask import jsonify  # ✅ Ensure this is imported



load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-very-secret-key'

# ✅ Fixed Flask-Session settings for Render
SESSION_DIR = os.path.join(os.getcwd(), '.flask_session')
os.makedirs(SESSION_DIR, exist_ok=True)

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = False  # Avoids byte-related cookie issue
app.config['SESSION_FILE_DIR'] = SESSION_DIR
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

Session(app)

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
    model = request.form.get('model', '').strip()

    query = f"SELECT id, name, part_number, shelf, amount, image FROM {table_name} WHERE 1=1"
    values = []

    if keyword:
        keyword_like = f"%{keyword}%"
        query += " AND (name ILIKE %s OR part_number ILIKE %s OR description ILIKE %s OR shelf ILIKE %s OR company ILIKE %s)"
        values += [keyword_like] * 5

    if company:
        query += " AND company = %s"
        values.append(company)

    if model:
      query += " AND model = %s"
      values.append(model)

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
from flask import Flask, render_template, request, redirect, session, flash, url_for
from uuid import uuid4

# 🛒 Initialize cart in session if not exists
def init_cart():
    if 'cart' not in session:
        session['cart'] = {}

# 🛒 Route: Sell Parts Page
@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    table_name = f"parts_{username}"

    keyword = request.form.get('keyword', '').strip()
    company = request.form.get('company', '').strip()
    year_from = request.form.get('year_from', '').strip()
    year_to = request.form.get('year_to', '').strip()
    model = request.form.get('model', '').strip()

    query = f"SELECT id, name, part_number, shelf, amount, image, sale_price FROM {table_name} WHERE 1=1"
    values = []

    if keyword:
        like = f"%{keyword}%"
        query += " AND (name ILIKE %s OR part_number ILIKE %s OR description ILIKE %s OR shelf ILIKE %s OR company ILIKE %s)"
        values += [like] * 5
    if company:
        query += " AND company = %s"
        values.append(company)
    if model:
        query += " AND model = %s"
        values.append(model)
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
        parts = [dict(id=row[0], name=row[1], part_number=row[2], shelf=row[3],
                      amount=row[4], image=row[5], sale_price=row[6]) for row in cur.fetchall()]
    except Exception as e:
        flash(f"Failed to load parts: {e}")
        parts = []
    finally:
        cur.close()
        conn.close()

    init_cart()
    cart = session['cart']
    total = sum(item['subtotal'] for item in cart.values())

    return render_template("sell.html", parts=parts, cart=cart, total=total, username=username)


# 🛒 Route: Add to Cart
from flask import jsonify  # ✅ Ensure this is imported

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    table_name = f"parts_{username}"
    part_id = int(request.form.get('part_id'))
    qty = int(request.form.get('quantity'))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT name, part_number, sale_price, pay_price, image
        FROM {table_name}
        WHERE id = %s
    """, (part_id,))
    part = cur.fetchone()
    cur.close()
    conn.close()

    if not part:
        return jsonify({'error': 'Part not found'}), 404

    init_cart()
    cart = session['cart']

    if str(part_id) in cart:
        cart[str(part_id)]['quantity'] += qty
    else:
        cart[str(part_id)] = {
            'part_id': part_id,
            'name': part[0],
            'part_number': part[1],
            'price': float(part[2]),
            'pay_price': float(part[3]),
            'image': part[4],
            'quantity': qty
                            }

    cart[str(part_id)]['subtotal'] = round(cart[str(part_id)]['price'] * cart[str(part_id)]['quantity'], 2)
    session.modified = True

    return jsonify(cart[str(part_id)])



# 🛒 Route: Update Cart Quantity
@app.route('/update_cart', methods=['POST'])
def update_cart():
    if 'username' not in session:
        return redirect('/')

    part_id = request.form.get('part_id')
    quantity = int(request.form.get('quantity'))

    if 'cart' in session and part_id in session['cart']:
        session['cart'][part_id]['quantity'] = quantity
        session['cart'][part_id]['subtotal'] = round(session['cart'][part_id]['price'] * quantity, 2)
        session.modified = True

    return redirect('/sell')


# 🛒 Route: Remove Item from Cart
@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    if 'username' not in session:
        return redirect('/')

    part_id = request.form.get('part_id')
    if 'cart' in session and part_id in session['cart']:
        session['cart'].pop(part_id)
        session.modified = True

    return redirect('/sell')

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    cart = session.get('cart', {})
    total = sum(item['subtotal'] for item in cart.values())
    total_after_discount = total

    if request.method == 'POST':
        buyer_name = request.form['buyer_name']
        buyer_phone = request.form['buyer_phone']
        car_number = request.form['car_number']
        discount = float(request.form.get('discount', 0))
        session["discount"] = discount
        discount_amount = round(total * discount / 100, 2)
        final_total = round(total - discount_amount, 2)

        order_id = str(uuid.uuid4())
        receipt_number = f"R-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        conn = get_connection()
        cur = conn.cursor()

        try:
            # Insert order
            cur.execute("""
                INSERT INTO orders (id, receipt_number, buyer_name, buyer_phone, car_number, users, total, discount, date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                order_id, receipt_number, buyer_name, buyer_phone, car_number, username,
                final_total, discount_amount, datetime.now()
            ))

            for item in cart.values():
                # Calculate profit per item
                profit = round((item['price'] - item['pay_price']) * item['quantity'], 2)

                # Insert each item into order_items with profit and pay_price_per_unit
                cur.execute("""
                    INSERT INTO order_items (
                        order_id, part_id, part_name, part_number,
                        unit_price, quantity, subtotal, image,
                        pay_price, profit
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    order_id, item['part_id'], item['name'], item['part_number'],
                    item['price'], item['quantity'], item['subtotal'], item['image'],
                    item['pay_price'], profit
                ))

                # Decrease stock
                table_name = f"parts_{username}"
                cur.execute(f"""
                    UPDATE {table_name}
                    SET amount = GREATEST(amount - %s, 0)
                    WHERE id = %s
                """, (item['quantity'], item['part_id']))

            conn.commit()
            session.pop('cart', None)
            return redirect(f'/receipt/{order_id}')

        except Exception as e:
            conn.rollback()
            flash(f"Checkout failed: {e}")
            return redirect('/checkout')
        finally:
            cur.close()
            conn.close()

    return render_template('checkout.html',
                           cart=cart,
                           total=total,
                           total_after_discount=total_after_discount,
                           username=username)


    return render_template('checkout.html',
                           cart=cart,
                           total=total,
                           total_after_discount=total_after_discount,
                           username=username)


@app.route('/receipt/<order_id>')
def receipt(order_id):
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT receipt_number, buyer_name, buyer_phone, car_number, users, total, discount, date
            FROM orders
            WHERE id = %s
        """, (order_id,))
        row = cur.fetchone()

        if not row:
            flash("Order not found.")
            return redirect('/sell')

        order = {
            'receipt_number': row[0],
            'buyer_name': row[1],
            'buyer_phone': row[2],
            'car_number': row[3],
            'users': row[4],
            'total': float(row[5]),
            'discount_amount': float(row[6]),
            'date': row[7]
        }

        cur.execute("""
            SELECT part_name, part_number, unit_price, quantity, subtotal, image
            FROM order_items
            WHERE order_id = %s
        """, (order_id,))
        items = [{
            'part_name': r[0],
            'part_number': r[1],
            'unit_price': float(r[2]),
            'quantity': r[3],
            'subtotal': float(r[4]),
            'image': r[5]
        } for r in cur.fetchall()]

        return render_template('receipt.html', order=order, items=items, username=username)

    except Exception as e:
        flash(f"Error loading receipt: {e}")
        return redirect('/sell')
    finally:
        cur.close()
        conn.close()



@app.route("/quote_preview", methods=["GET", "POST"])
def quote_preview():
    if "username" not in session:
        return redirect("/login")

    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.")
        return redirect("/sell")

    if request.method == "POST":
        buyer_name = request.form.get("buyer_name", "")
        buyer_phone = request.form.get("buyer_phone", "")
        car_number = request.form.get("car_number", "")
        try:
            discount = float(request.form.get("discount", 0))
        except ValueError:
            discount = 0
    else:
        buyer_name = request.args.get("buyer_name", "")
        buyer_phone = request.args.get("buyer_phone", "")
        car_number = request.args.get("car_number", "")
        discount = 0

    total = sum(item["price"] * item["quantity"] for item in cart.values())
    discount_amount = round(total * discount / 100, 2)
    grand_total = round(total - discount_amount, 2)

    return render_template(
        "receipt.html",
        is_quote=True,
        now=datetime.now(),
        buyer_name=buyer_name,
        buyer_phone=buyer_phone,
        car_number=car_number,
        cart=cart,
        total=total,
        discount=discount_amount,
        grand_total=grand_total
    )


@app.route('/sales_history', methods=['GET', 'POST'])
def sales_history():
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    car_number = request.form.get('car_number', '').strip()
    buyer_phone = request.form.get('buyer_phone', '').strip()
    date_from = request.form.get('date_from', '').strip()
    date_to = request.form.get('date_to', '').strip()

    query = """
        SELECT o.id, o.receipt_number, o.buyer_name, o.buyer_phone, o.car_number,
               SUM(oi.quantity) AS total_qty,
               SUM(oi.profit) AS total_profit,
               o.discount, o.date
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.users = %s
    """
    values = [username]

    if car_number:
        query += " AND o.car_number ILIKE %s"
        values.append(f"%{car_number}%")
    if buyer_phone:
        query += " AND o.buyer_phone ILIKE %s"
        values.append(f"%{buyer_phone}%")
    if date_from:
        query += " AND o.date >= %s"
        values.append(date_from)
    if date_to:
        query += " AND o.date <= %s"
        values.append(date_to)

    query += """
        GROUP BY o.id
        ORDER BY o.date DESC
    """

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, values)
    receipts = cur.fetchall()
    cur.close()
    conn.close()

    parsed_receipts = []
    for r in receipts:
     parsed_receipts.append({
        'id': r[0],
        'receipt_number': r[1],
        'buyer_name': r[2],
        'buyer_phone': r[3],
        'car_number': r[4],
        'qty': int(r[5] or 0),
        'profit': float(r[6] or 0),
        'discount': float(r[7] or 0),
        'date': r[8].strftime('%Y-%m-%d %H:%M')
    })


    return render_template('sales_history.html', receipts=parsed_receipts)




@app.route('/analysis', methods=['GET', 'POST'])
def analysis():
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    date_from = request.form.get('date_from') or '2000-01-01'
    date_to = request.form.get('date_to') or '2100-01-01'
    company = request.form.get('company')
    model = request.form.get('model')

    filters = ["o.users = %s", "o.date BETWEEN %s AND %s"]
    values = [username, date_from, date_to]

    if company:
        filters.append("p.company ILIKE %s")
        values.append(f"%{company}%")
    if model:
        filters.append("p.model ILIKE %s")
        values.append(f"%{model}%")

    where_clause = " AND ".join(filters)

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Summary Metrics
    cur.execute(f"""
        SELECT
            COALESCE(SUM(oi.subtotal), 0) AS revenue,
            COALESCE(SUM(oi.pay_price * oi.quantity), 0) AS cost,
            COALESCE(SUM(oi.profit), 0) AS profit,
            COALESCE(SUM(oi.quantity), 0) AS quantity,
            COUNT(DISTINCT o.id) AS orders
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        JOIN parts_{username} p ON p.id = CAST(oi.part_id AS INTEGER)
        WHERE {where_clause}
    """, values)
    metrics = cur.fetchone()

    # Sales Trend (by day)
    cur.execute(f"""
        SELECT TO_CHAR(o.date, 'YYYY-MM-DD') AS date, SUM(oi.subtotal) AS total
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        JOIN parts_{username} p ON p.id = CAST(oi.part_id AS INTEGER)
        WHERE {where_clause}
        GROUP BY 1 ORDER BY 1
    """, values)
    trend_data = cur.fetchall()
    sales_trend = {
        "labels": [r['date'] for r in trend_data],
        "datasets": [{"label": "Sales", "data": [r['total'] for r in trend_data]}]
    }

    # Top Selling
    cur.execute(f"""
        SELECT oi.part_name, SUM(oi.quantity) AS qty
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        JOIN parts_{username} p ON p.id = CAST(oi.part_id AS INTEGER)
        WHERE {where_clause}
        GROUP BY oi.part_name ORDER BY qty DESC LIMIT 5
    """, values)
    selling_data = cur.fetchall()
    top_selling = {
        "labels": [r['part_name'] for r in selling_data],
        "datasets": [{"label": "Qty Sold", "data": [r['qty'] for r in selling_data]}]
    }

    # Top Profit
    cur.execute(f"""
        SELECT oi.part_name, SUM(oi.profit) AS profit
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        JOIN parts_{username} p ON p.id = CAST(oi.part_id AS INTEGER)
        WHERE {where_clause}
        GROUP BY oi.part_name ORDER BY profit DESC LIMIT 5
    """, values)
    profit_data = cur.fetchall()
    top_profit = {
        "labels": [r['part_name'] for r in profit_data],
        "datasets": [{"label": "Profit", "data": [r['profit'] for r in profit_data]}]
    }

    # Sales by Company
    cur.execute(f"""
        SELECT p.company, SUM(oi.subtotal) AS total
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        JOIN parts_{username} p ON p.id = CAST(oi.part_id AS INTEGER)
        WHERE {where_clause}
        GROUP BY p.company ORDER BY total DESC LIMIT 5
    """, values)
    company_data = cur.fetchall()
    sales_by_company = {
        "labels": [r['company'] for r in company_data],
        "datasets": [{"label": "Sales", "data": [r['total'] for r in company_data]}]
    }

    cur.close()
    conn.close()

    return render_template(
        "analysis.html",
        username=username,
        revenue=round(metrics['revenue'], 2),
        cost=round(metrics['cost'], 2),
        profit=round(metrics['profit'], 2),
        quantity=metrics['quantity'],
        orders=metrics['orders'],
        sales_trend=sales_trend,
        top_selling=top_selling,
        top_profit=top_profit,
        sales_by_company=sales_by_company
    )

if __name__ == '__main__':
    app.run(debug=True)