import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('whatsapp.db')
    c = conn.cursor()
    
    # Tabela para números validados
    c.execute('''CREATE TABLE IF NOT EXISTS validated_numbers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  number TEXT NOT NULL,
                  instance_name TEXT NOT NULL,
                  is_valid BOOLEAN NOT NULL,
                  validation_date TIMESTAMP NOT NULL,
                  UNIQUE(number, instance_name))''')
    
    # Tabela para histórico de mensagens
    c.execute('''CREATE TABLE IF NOT EXISTS message_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  instance_name TEXT NOT NULL,
                  number TEXT NOT NULL,
                  message TEXT NOT NULL,
                  status TEXT NOT NULL,
                  error TEXT,
                  delay INTEGER,
                  sent_date TIMESTAMP NOT NULL)''')
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect('whatsapp.db')
    conn.row_factory = sqlite3.Row
    return conn

def save_validated_number(number, instance_name, is_valid):
    conn = get_db()
    try:
        conn.execute('''INSERT OR REPLACE INTO validated_numbers 
                       (number, instance_name, is_valid, validation_date)
                       VALUES (?, ?, ?, ?)''',
                    (number, instance_name, is_valid, datetime.now()))
        conn.commit()
    finally:
        conn.close()

def get_validated_numbers(instance_name):
    conn = get_db()
    try:
        cursor = conn.execute('''SELECT * FROM validated_numbers 
                               WHERE instance_name = ? AND is_valid = 1
                               ORDER BY validation_date DESC''',
                            (instance_name,))
        return cursor.fetchall()
    finally:
        conn.close()

def save_message_history(instance_name, number, message, status, error=None, delay=None):
    conn = get_db()
    try:
        conn.execute('''INSERT INTO message_history 
                       (instance_name, number, message, status, error, delay, sent_date)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (instance_name, number, message, status, error, delay, datetime.now()))
        conn.commit()
    finally:
        conn.close()

def get_message_history():
    conn = get_db()
    try:
        cursor = conn.execute('''SELECT * FROM message_history 
                               ORDER BY sent_date DESC 
                               LIMIT 100''')
        return cursor.fetchall()
    finally:
        conn.close()
