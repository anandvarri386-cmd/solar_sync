import sqlite3
import secrets
import string
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from database.db_manager import get_db_connection

def generate_device_id():
    """Generates a readable, unique pump device identifier e.g. PUMP-SOLAR-8942."""
    random_digits = ''.join(secrets.choice(string.digits) for _ in range(4))
    return f"PUMP-SOLAR-{random_digits}"

def generate_api_key():
    """Generates a secure, 32-character hexadecimal API key for ESP32 authorization."""
    return f"sync_sec_{secrets.token_hex(16)}"

def create_user(email, password, name, pump_device_id=None, pump_name="Smart Solar DC Pump"):
    """Creates a new customer account and binds it to a pump device."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    email = email.strip().lower()
    password_hash = generate_password_hash(password)
    
    if not pump_device_id or not pump_device_id.strip():
        pump_device_id = generate_device_id()
    else:
        pump_device_id = pump_device_id.strip().upper()
        
    api_key = generate_api_key()
    
    try:
        cursor.execute('''
            INSERT INTO users (email, password_hash, name, pump_device_id, api_key, pump_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            email, 
            password_hash, 
            name.strip(), 
            pump_device_id, 
            api_key, 
            pump_name.strip(), 
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
        user_id = cursor.lastrowid
        return {
            "id": user_id,
            "email": email,
            "name": name,
            "pump_device_id": pump_device_id,
            "api_key": api_key,
            "pump_name": pump_name
        }, None
    except sqlite3.IntegrityError as e:
        err_msg = str(e)
        if "users.email" in err_msg:
            return None, "An account with this email address already exists."
        elif "users.pump_device_id" in err_msg:
            return None, "This Pump Device ID is already assigned to another customer."
        else:
            return None, f"Database integrity error: {err_msg}"
    except Exception as e:
        return None, f"Unexpected error creating user: {str(e)}"
    finally:
        conn.close()

def get_user_by_email(email):
    """Retrieves a user record by email address."""
    if not email:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM users WHERE email = ?', (email.strip().lower(),))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"Error fetching user by email: {e}")
        return None
    finally:
        conn.close()

def get_user_by_id(user_id):
    """Retrieves a user record by database ID."""
    if not user_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"Error fetching user by ID: {e}")
        return None
    finally:
        conn.close()

def get_user_by_device_id(device_id, api_key=None):
    """Authenticates an ESP32 hardware node by its Device ID and optional API key."""
    if not device_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if api_key:
            cursor.execute('SELECT * FROM users WHERE pump_device_id = ? AND api_key = ?', (device_id.strip().upper(), api_key.strip()))
        else:
            cursor.execute('SELECT * FROM users WHERE pump_device_id = ?', (device_id.strip().upper(),))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"Error fetching user by device ID: {e}")
        return None
    finally:
        conn.close()

def verify_password(user, password):
    """Checks plain password against stored Werkzeug hash."""
    if not user or 'password_hash' not in user:
        return False
    return check_password_hash(user['password_hash'], password)

def update_user_pump_info(user_id, pump_name=None, pump_device_id=None):
    """Updates customer pump metadata."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if pump_name and pump_device_id:
            cursor.execute('UPDATE users SET pump_name = ?, pump_device_id = ? WHERE id = ?', 
                           (pump_name.strip(), pump_device_id.strip().upper(), user_id))
        elif pump_name:
            cursor.execute('UPDATE users SET pump_name = ? WHERE id = ?', (pump_name.strip(), user_id))
        elif pump_device_id:
            cursor.execute('UPDATE users SET pump_device_id = ? WHERE id = ?', (pump_device_id.strip().upper(), user_id))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, "This Pump Device ID is already in use by another account."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def regenerate_api_key(user_id):
    """Generates and stores a new API key for the user's ESP32."""
    new_key = generate_api_key()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET api_key = ? WHERE id = ?', (new_key, user_id))
        conn.commit()
        return new_key, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()
