import sqlite3

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