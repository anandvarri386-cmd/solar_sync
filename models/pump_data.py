import sqlite3
from datetime import datetime, timedelta
from database.db_manager import get_db_connection

def insert_reading(voltage, current, power, status, runtime, energy, pump_device_id="PUMP-SOLAR-1001"):
    """Inserts a new telemetry entry into the SQLite database scoped to a specific pump device."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    
    try:
        cursor.execute('''
            INSERT INTO pump_data (pump_device_id, date, time, voltage, current, power, pump_status, runtime, energy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            pump_device_id,
            date_str, 
            time_str, 
            round(voltage, 2), 
            round(current, 2), 
            round(power, 2), 
            int(status), 
            round(runtime, 4), 
            round(energy, 4)
        ))
        conn.commit()
        last_id = cursor.lastrowid
        return last_id
    except Exception as e:
        print(f"Database Error inserting reading for {pump_device_id}: {e}")
        return None
    finally:
        conn.close()

def get_latest_reading(pump_device_id="PUMP-SOLAR-1001"):
    """Fetches the latest reading for a specific customer's pump device."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM pump_data WHERE pump_device_id = ? ORDER BY id DESC LIMIT 1', (pump_device_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"Database Error getting latest reading for {pump_device_id}: {e}")
        return None
    finally:
        conn.close()

def get_history(limit=10, offset=0, search_query="", sort_by="id", sort_order="DESC", pump_device_id="PUMP-SOLAR-1001"):
    """Fetches a list of records for a specific pump device with sorting, searching, and pagination."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    valid_cols = ["id", "date", "time", "voltage", "current", "power", "pump_status", "runtime", "energy"]
    if sort_by not in valid_cols:
        sort_by = "id"
    if sort_order.upper() not in ["ASC", "DESC"]:
        sort_order = "DESC"
        
    query = "SELECT * FROM pump_data WHERE pump_device_id = ?"
    params = [pump_device_id]
    
    if search_query:
        query += " AND (date LIKE ? OR time LIKE ? OR pump_status LIKE ?)"
        search_pattern = f"%{search_query}%"
        params.extend([search_pattern, search_pattern, search_pattern])
        
    # Get total count before pagination
    count_query = f"SELECT COUNT(*) FROM ({query})"
    try:
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
    except Exception as e:
        print(f"Database Error getting count: {e}")
        total_records = 0
        
    # Append sorting and pagination
    query += f" ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    records = []
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        for r in rows:
            records.append(dict(r))
    except Exception as e:
        print(f"Database Error getting records: {e}")
        
    conn.close()
    return records, total_records

def delete_record(record_id, pump_device_id=None):
    """Deletes a specific reading by ID (ensuring ownership check if pump_device_id is provided)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    success = False
    try:
        if pump_device_id:
            cursor.execute("DELETE FROM pump_data WHERE id = ? AND pump_device_id = ?", (record_id, pump_device_id))
        else:
            cursor.execute("DELETE FROM pump_data WHERE id = ?", (record_id,))
        conn.commit()
        success = cursor.rowcount > 0
    except Exception as e:
        print(f"Database Error deleting record {record_id}: {e}")
    finally:
        conn.close()
    return success

def get_analytics_summary(pump_device_id="PUMP-SOLAR-1001"):
    """Aggregates metrics for daily energy, daily runtime, efficiency, and chart data for a specific pump."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    summary = {
        "energy_used_today": 0.0,
        "runtime_today": 0.0,
        "efficiency_score": 94.2,
        "daily_usage_chart": [],
        "weekly_usage_chart": []
    }
    
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    
    try:
        # 1. Energy Used Today
        cursor.execute("SELECT MIN(energy), MAX(energy) FROM pump_data WHERE pump_device_id = ? AND date = ?", (pump_device_id, today_str))
        row = cursor.fetchone()
        if row and row[0] is not None and row[1] is not None:
            summary["energy_used_today"] = round(row[1] - row[0], 4)
        else:
            summary["energy_used_today"] = 0.0
            
        # 2. Runtime Today
        cursor.execute("SELECT MIN(runtime), MAX(runtime) FROM pump_data WHERE pump_device_id = ? AND date = ?", (pump_device_id, today_str))
        row = cursor.fetchone()
        if row and row[0] is not None and row[1] is not None:
            summary["runtime_today"] = round(row[1] - row[0], 2)
        else:
            summary["runtime_today"] = 0.0
            
        # 3. Daily Energy consumption (last 7 days)
        cursor.execute("""
            SELECT date, (MAX(energy) - MIN(energy)) as daily_energy
            FROM pump_data
            WHERE pump_device_id = ?
            GROUP BY date
            ORDER BY date DESC
            LIMIT 7
        """, (pump_device_id,))
        rows = cursor.fetchall()
        daily_chart = []
        for r in reversed(rows):
            daily_chart.append({
                "date": r["date"],
                "energy": round(r["daily_energy"] if r["daily_energy"] is not None else 0.0, 3)
            })
        summary["daily_usage_chart"] = daily_chart
        
        # 4. Weekly Energy consumption (last 4 weeks)
        cursor.execute("""
            SELECT strftime('%W', date) as week, SUM(daily_energy) as weekly_energy
            FROM (
                SELECT date, (MAX(energy) - MIN(energy)) as daily_energy
                FROM pump_data
                WHERE pump_device_id = ?
                GROUP BY date
            )
            GROUP BY week
            ORDER BY week DESC
            LIMIT 4
        """, (pump_device_id,))
        rows = cursor.fetchall()
        weekly_chart = []
        for r in reversed(rows):
            weekly_chart.append({
                "week": f"Week {r['week']}",
                "energy": round(r["weekly_energy"] if r["weekly_energy"] is not None else 0.0, 3)
            })
        summary["weekly_usage_chart"] = weekly_chart
        
        # 5. Dynamic Efficiency Score
        cursor.execute("""
            SELECT voltage, current, power 
            FROM pump_data 
            WHERE pump_device_id = ? AND pump_status = 1 
            ORDER BY id DESC 
            LIMIT 10
        """, (pump_device_id,))
        rows = cursor.fetchall()
        if rows:
            efficiencies = []
            for r in rows:
                v, i, p = r["voltage"], r["current"], r["power"]
                if v > 10.0 and i < 0.8:
                    efficiencies.append(40.0)
                else:
                    efficiencies.append(94.2)
            summary["efficiency_score"] = round(sum(efficiencies) / len(efficiencies), 1)
        else:
            summary["efficiency_score"] = 94.2
            
    except Exception as e:
        print(f"Database Error in analytics calculations for {pump_device_id}: {e}")
    finally:
        conn.close()
        
    return summary
