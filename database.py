import sqlite3
from datetime import datetime

DB_NAME = "sport_musobaqa.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Adminlar jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        telegram_id INTEGER PRIMARY KEY
    )""")
    
    # Sport turlari jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        max_limit INTEGER DEFAULT 100,
        min_age INTEGER DEFAULT 0,
        max_age INTEGER DEFAULT 100,
        is_active INTEGER DEFAULT 1
    )""")
    
    # Ishtirokchilar jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        fullname TEXT,
        mahalla TEXT,
        birth_year INTEGER,
        phone TEXT,
        sport_name TEXT,
        reg_date TEXT
    )""")
    
    # Yangi to'g'ri Admin ID raqamingizni bazaga yozish
    cursor.execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (7145265381,)) 
    
    conn.commit()
    conn.close()

def db_execute(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def db_fetchall(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = cursor.fetchall()
    conn.close()
    return res

def db_fetchone(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = cursor.fetchone()
    conn.close()
    return res