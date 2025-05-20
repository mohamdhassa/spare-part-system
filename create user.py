import psycopg2
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()  # Load DB credentials from .env

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def create_user(username, password):
    # Hash password
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Connect to DB
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Check if user already exists
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            print("❌ User already exists.")
            return

        # Insert new user
        cur.execute("""
            INSERT INTO users (username, password_hash, created_at)
            VALUES (%s, %s, NOW())
        """, (username, hashed_pw))
        conn.commit()

        # Create user-specific parts table
        table_name = f"parts_{username}".lower()
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
                created_at TIMESTAMP DEFAULT NOW(),
                model TEXT
            )
        """)
        conn.commit()

        print(f"✅ User '{username}' created and table '{table_name}' initialized.")

    except Exception as e:
        print(f"⚠️ Error: {e}")

    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    user = input("Enter new username: ")
    pw = input("Enter new password: ")
    create_user(user, pw)


