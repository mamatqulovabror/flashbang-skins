import sqlite3
import time

def create_db():
    conn = sqlite3.connect("skins.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS skins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            weapon TEXT,
            name TEXT,
            wear TEXT,
            float TEXT,
            price REAL,
            photo TEXT,
            sold INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_seen INTEGER,
            last_seen INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def add_skin(seller_id, weapon, name, wear, float_val, price, photo):
    conn = sqlite3.connect("skins.db")
    c = conn.cursor()
    c.execute('''
            INSERT INTO skins (seller_id, weapon, name, wear, float, price, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (seller_id, weapon, name, wear, float_val, price, photo))
    conn.commit()
    conn.close()

def get_all_skins():
    conn = sqlite3.connect("skins.db")
    c = conn.cursor()
    c.execute('SELECT * FROM skins WHERE sold = 0')
    rows = c.fetchall()
    conn.close()
    return rows

def mark_sold(skin_id):
    conn = sqlite3.connect("skins.db")
    c = conn.cursor()
    c.execute('UPDATE skins SET sold = 1 WHERE id = ?', (skin_id,))
    conn.commit()
    conn.close()

def save_user(user_id, username):
    conn = sqlite3.connect("skins.db")
    c = conn.cursor()
    now = int(time.time())
    c.execute('''
        INSERT INTO users (user_id, username, first_seen, last_seen)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET last_seen=?, username=?
    ''', (user_id, username, now, now, now, username))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("skins.db")
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total = c.fetchone()[0]
    online_threshold = int(time.time()) - 300
    c.execute('SELECT COUNT(*) FROM users WHERE last_seen > ?', (online_threshold,))
    online = c.fetchone()[0]
    conn.close()
    return total, online
