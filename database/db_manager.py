import sqlite3
import os
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash

# Absolute path to database.db in the workspace directory
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database tables and seeds demo customer and historical telemetry."""
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
    
    conn.commit()
    
    # 4. Seed default demo customer if users table is empty
    cursor.execute('SELECT COUNT(*) FROM users')
    user_count = cursor.fetchone()[0]
    
    demo_device_id = "PUMP-SOLAR-1001"
    if user_count == 0:
        print("Creating default demo customer account...")
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
        
    # 5. Check if pump_sessions has records for the demo pump
    cursor.execute('SELECT COUNT(*) FROM pump_sessions WHERE pump_device_id = ?', (demo_device_id,))
    session_count = cursor.fetchone()[0]
    
    if session_count == 0:
        print("Seeding demo pump run session history records...")
        seed_mock_sessions(conn, demo_device_id)
    else:
        print(f"Database contains run session data ({session_count} sessions).")
        
    conn.close()

def seed_mock_sessions(conn, device_id="PUMP-SOLAR-1001"):
    """Generates 7 days of realistic pump run sessions (motor ON/OFF events and run duration)."""
    cursor = conn.cursor()
    now = datetime.now()
    
    # Generate 2 realistic pump run sessions per day for the last 7 days
    for day_offset in range(7, 0, -1):
        day_date = (now - timedelta(days=day_offset)).strftime('%Y-%m-%d')
        
        # Session 1: Morning Irrigation Run (e.g. 09:15 to 11:45)
        m_start = "09:15:00"
        m_end = "11:45:00"
        m_duration_mins = 150.0 # 2.5 hrs
        m_duration_str = "2 hrs 30 mins"
        m_voltage = round(random.uniform(17.2, 19.5), 1)
        m_current = round(random.uniform(2.1, 2.5), 2)
        m_power = round(m_voltage * m_current, 1)
        m_energy = round((m_power * 2.5) / 1000.0, 4)
        
        cursor.execute('''
            INSERT INTO pump_sessions (pump_device_id, date, start_time, end_time, duration_minutes, duration_str, avg_voltage, avg_current, avg_power, energy_kwh, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED')
        ''', (device_id, day_date, m_start, m_end, m_duration_mins, m_duration_str, m_voltage, m_current, m_power, m_energy))
        
        # Session 2: Afternoon Irrigation Run (e.g. 13:30 to 15:45)
        a_start = "13:30:00"
        a_end = "15:45:00"
        a_duration_mins = 135.0 # 2.25 hrs
        a_duration_str = "2 hrs 15 mins"
        a_voltage = round(random.uniform(16.8, 18.9), 1)
        a_current = round(random.uniform(2.0, 2.4), 2)
        a_power = round(a_voltage * a_current, 1)
        a_energy = round((a_power * 2.25) / 1000.0, 4)
        
        cursor.execute('''
            INSERT INTO pump_sessions (pump_device_id, date, start_time, end_time, duration_minutes, duration_str, avg_voltage, avg_current, avg_power, energy_kwh, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED')
        ''', (device_id, day_date, a_start, a_end, a_duration_mins, a_duration_str, a_voltage, a_current, a_power, a_energy))
        
    conn.commit()
    print(f"Database successfully seeded with realistic pump run history for {device_id}.")
