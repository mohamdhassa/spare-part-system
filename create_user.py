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
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            print("❌ User already exists.")
        else:
            cur.execute("""
                INSERT INTO users (username, password_hash, created_at)
                VALUES (%s, %s, NOW())
            """, (username, hashed_pw))
            conn.commit()
            print("✅ User created successfully.")
    except Exception as e:
        print(f"⚠️ Error: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    user = input("Enter new username: ")
    pw = input("Enter new password: ")
    create_user(user, pw)
