import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

# Absolute path to database.db in the workspace directory
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database tables with clean schema and handles auto-migrations."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            pump_device_id TEXT UNIQUE NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            pump_name TEXT DEFAULT 'Smart Solar DC Pump',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Create pump_data table for raw rolling telemetry
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pump_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pump_device_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            voltage REAL NOT NULL,
            current REAL NOT NULL,
            power REAL NOT NULL,
            pump_status INTEGER NOT NULL,
            runtime REAL NOT NULL,
            energy REAL NOT NULL
        )
    ''')
    
    # 3. Create pump_sessions table (Stores ON/OFF event history and daily runtime)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pump_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pump_device_id TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_seconds REAL DEFAULT 0.0,
            duration_minutes REAL DEFAULT 0.0,
            duration_str TEXT DEFAULT '0m 0s',
            avg_voltage REAL DEFAULT 0.0,
            avg_current REAL DEFAULT 0.0,
            avg_power REAL DEFAULT 0.0,
            energy_kwh REAL DEFAULT 0.0,
            status TEXT DEFAULT 'COMPLETED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Auto-migration safeguard for existing database files
    cursor.execute("PRAGMA table_info(pump_sessions)")
    sess_cols = [row[1] for row in cursor.fetchall()]
    if 'duration_seconds' not in sess_cols and len(sess_cols) > 0:
        print("Migrating pump_sessions: Adding duration_seconds column...")
        cursor.execute("ALTER TABLE pump_sessions ADD COLUMN duration_seconds REAL DEFAULT 0.0")
        
    conn.commit()
    
    # 4. Seed default demo customer if users table is empty
    cursor.execute('SELECT COUNT(*) FROM users')
    user_count = cursor.fetchone()[0]
    
    demo_device_id = "PUMP-SOLAR-1001"
    if user_count == 0:
        cursor.execute('''
            INSERT INTO users (email, password_hash, name, pump_device_id, api_key, pump_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            "demo@solarsync.com",
            generate_password_hash("Password123!"),
            "Demo Customer",
            demo_device_id,
            "sync_sec_demo1234567890abcdef12345678",
            "Farm DC Solar Pump",
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
        
    conn.close()

def clear_all_history():
    """Purges all history records from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM pump_sessions")
        cursor.execute("DELETE FROM pump_data")
        conn.commit()
        print("All history purged successfully.")
    except Exception as e:
        print(f"Error purging history: {e}")
    finally:
        conn.close()
