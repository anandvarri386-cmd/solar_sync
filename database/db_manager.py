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
    
    # 2. Create pump_data table with pump_device_id association
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
    
    # Check if pump_device_id column exists in pump_data (migration safeguard)
    cursor.execute("PRAGMA table_info(pump_data)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'pump_device_id' not in columns:
        print("Migrating pump_data table: Adding pump_device_id column...")
        cursor.execute("ALTER TABLE pump_data ADD COLUMN pump_device_id TEXT DEFAULT 'PUMP-SOLAR-1001'")
        
    conn.commit()
    
    # 3. Seed default demo customer if users table is empty
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
        
    # 4. Check if pump_data has records for the demo pump
    cursor.execute('SELECT COUNT(*) FROM pump_data WHERE pump_device_id = ?', (demo_device_id,))
    data_count = cursor.fetchone()[0]
    
    if data_count == 0:
        print("Seeding demo pump historical telemetry records...")
        seed_mock_data(conn, demo_device_id)
    else:
        print(f"Database contains telemetry data ({data_count} records).")
        
    conn.close()

def seed_mock_data(conn, device_id="PUMP-SOLAR-1001"):
    """Generates 7 days of realistic solar pump telemetry for the given pump device ID."""
    cursor = conn.cursor()
    now = datetime.now()
    
    total_runtime = 0.0
    total_energy = 0.0
    
    # Generate mock records day-by-day
    for day_offset in range(7, 0, -1):
        day_date = (now - timedelta(days=day_offset)).strftime('%Y-%m-%d')
        
        for hour in range(24):
            time_str = f"{hour:02d}:00:00"
            
            # Solar Voltage model
            if 6 <= hour <= 18:
                dist_from_noon = abs(hour - 12.5)
                voltage = max(0.0, 18.0 - (dist_from_noon * 1.5) + random.uniform(-0.4, 0.4))
            else:
                voltage = random.uniform(0.0, 0.2)
                
            # Pump state logic
            if 9 <= hour <= 16 and voltage > 10.0:
                pump_status = 1
                current = round(random.uniform(1.8, 2.6), 2)
                power = round(voltage * current, 2)
                total_runtime += 1.0
                total_energy += (power * 1.0) / 1000.0
            else:
                pump_status = 0
                current = 0.0
                power = 0.0
                
            cursor.execute('''
                INSERT INTO pump_data (pump_device_id, date, time, voltage, current, power, pump_status, runtime, energy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                day_date, 
                time_str, 
                round(voltage, 2), 
                current, 
                power, 
                pump_status, 
                round(total_runtime, 2), 
                round(total_energy, 4)
            ))
            
    conn.commit()
    print(f"Database successfully seeded with records for {device_id}.")
