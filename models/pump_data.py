import sqlite3
from datetime import datetime, timedelta
from database.db_manager import get_db_connection

def format_duration(total_seconds):
    """Formats seconds into human-readable hours, minutes, and seconds."""
    total_seconds = max(0, int(total_seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def record_telemetry_and_session(voltage, current, power, pump_status, runtime, energy, pump_device_id="PUMP-SOLAR-1001"):
    """
    Updates active motor run sessions and logs telemetry.
    Tracks exact Switched ON time, Switched OFF time, and Session Duration.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    
    try:
        # 1. Check for any active open session for this device
        cursor.execute('''
            SELECT id, start_time, duration_seconds, avg_voltage, avg_current, avg_power, energy_kwh
            FROM pump_sessions 
            WHERE pump_device_id = ? AND status = 'ACTIVE'
            ORDER BY id DESC LIMIT 1
        ''', (pump_device_id,))
        active_session = cursor.fetchone()
        
        # Determine if motor is running (pump_status == 1 or drawing current >= 1.0A)
        is_running = (pump_status == 1 or current >= 1.0)
        
        if is_running:
            if not active_session:
                # Motor just SWITCHED ON! Create a new run session entry
                cursor.execute('''
                    INSERT INTO pump_sessions (
                        pump_device_id, date, start_time, end_time, duration_seconds, 
                        duration_minutes, duration_str, avg_voltage, avg_current, 
                        avg_power, energy_kwh, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
                ''', (
                    pump_device_id,
                    date_str,
                    time_str,
                    time_str,
                    1.0,
                    round(1.0 / 60.0, 2),
                    "1s",
                    round(voltage, 1),
                    round(current, 2),
                    round(power, 1),
                    round((power * (1.0 / 3600.0)) / 1000.0, 5)
                ))
            else:
                # Motor is CONTINUING TO RUN! Update session duration & metrics
                sess_id = active_session['id']
                start_time_str = active_session['start_time']
                
                try:
                    # Compute total elapsed seconds from start time
                    start_dt = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H:%M:%S")
                    elapsed_seconds = max(1.0, (now - start_dt).total_seconds())
                except Exception:
                    elapsed_seconds = active_session['duration_seconds'] + 1.0
                    
                dur_mins = round(elapsed_seconds / 60.0, 2)
                dur_str = format_duration(elapsed_seconds)
                
                # Rolling averages
                new_v = round((active_session['avg_voltage'] * 0.8) + (voltage * 0.2), 1)
                new_i = round((active_session['avg_current'] * 0.8) + (current * 0.2), 2)
                new_p = round((active_session['avg_power'] * 0.8) + (power * 0.2), 1)
                new_e = round(active_session['energy_kwh'] + ((power * (1.0 / 3600.0)) / 1000.0), 5)
                
                cursor.execute('''
                    UPDATE pump_sessions
                    SET end_time = ?, duration_seconds = ?, duration_minutes = ?, 
                        duration_str = ?, avg_voltage = ?, avg_current = ?, 
                        avg_power = ?, energy_kwh = ?
                    WHERE id = ?
                ''', (time_str, elapsed_seconds, dur_mins, dur_str, new_v, new_i, new_p, new_e, sess_id))
                
        else:
            # Motor is OFF: If an active session was running, finalize it!
            if active_session:
                sess_id = active_session['id']
                cursor.execute('''
                    UPDATE pump_sessions
                    SET end_time = ?, status = 'COMPLETED'
                    WHERE id = ?
                ''', (time_str, sess_id))
                
        conn.commit()
    except Exception as e:
        print(f"Database Error updating pump session for {pump_device_id}: {e}")
    finally:
        conn.close()

def get_history(limit=15, offset=0, search_query="", sort_by="id", sort_order="DESC", pump_device_id="PUMP-SOLAR-1001"):
    """
    Fetches pump run sessions (Switched ON time, Switched OFF time, and Duration).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    valid_cols = ["id", "date", "start_time", "end_time", "duration_minutes", "avg_voltage", "avg_current", "avg_power", "energy_kwh", "status"]
    if sort_by not in valid_cols:
        sort_by = "id"
    if sort_order.upper() not in ["ASC", "DESC"]:
        sort_order = "DESC"
        
    query = "SELECT * FROM pump_sessions WHERE pump_device_id = ?"
    params = [pump_device_id]
    
    if search_query:
        query += " AND (date LIKE ? OR start_time LIKE ? OR end_time LIKE ? OR status LIKE ?)"
        search_pattern = f"%{search_query}%"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
        
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

def get_daily_summary(pump_device_id="PUMP-SOLAR-1001"):
    """
    Calculates daily total run duration and energy for every single day.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    daily_stats = []
    try:
        cursor.execute('''
            SELECT 
                date,
                COUNT(id) as total_runs,
                SUM(duration_minutes) as total_duration_mins,
                SUM(energy_kwh) as total_energy_kwh,
                AVG(avg_power) as avg_power_w
            FROM pump_sessions
            WHERE pump_device_id = ?
            GROUP BY date
            ORDER BY date DESC
            LIMIT 14
        ''', (pump_device_id,))
        rows = cursor.fetchall()
        for r in rows:
            tot_mins = r['total_duration_mins'] or 0.0
            daily_stats.append({
                "date": r['date'],
                "total_runs": r['total_runs'],
                "total_duration_hours": round(tot_mins / 60.0, 2),
                "total_duration_str": format_duration(tot_mins * 60.0),
                "total_energy_kwh": round(r['total_energy_kwh'] or 0.0, 4),
                "avg_power_w": round(r['avg_power_w'] or 0.0, 1)
            })
    except Exception as e:
        print(f"Database Error getting daily summary: {e}")
    finally:
        conn.close()
        
    return daily_stats

def delete_record(record_id, pump_device_id=None):
    """Deletes a specific session by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    success = False
    try:
        if pump_device_id:
            cursor.execute("DELETE FROM pump_sessions WHERE id = ? AND pump_device_id = ?", (record_id, pump_device_id))
        else:
            cursor.execute("DELETE FROM pump_sessions WHERE id = ?", (record_id,))
        conn.commit()
        success = cursor.rowcount > 0
    except Exception as e:
        print(f"Database Error deleting session {record_id}: {e}")
    finally:
        conn.close()
    return success

def get_analytics_summary(pump_device_id="PUMP-SOLAR-1001"):
    """Aggregates metrics for daily runtime, energy, and chart data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    summary = {
        "daily_runtime_hours": 0.0,
        "daily_energy_kwh": 0.0,
        "weekly_energy_kwh": 0.0,
        "daily_chart_labels": [],
        "daily_chart_energy": [],
        "daily_chart_runtime": []
    }
    
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        # Today's run stats
        cursor.execute('''
            SELECT SUM(duration_minutes) as tot_mins, SUM(energy_kwh) as tot_energy
            FROM pump_sessions
            WHERE pump_device_id = ? AND date = ?
        ''', (pump_device_id, today_str))
        row = cursor.fetchone()
        if row and row['tot_mins']:
            summary['daily_runtime_hours'] = round((row['tot_mins'] or 0.0) / 60.0, 2)
            summary['daily_energy_kwh'] = round(row['tot_energy'] or 0.0, 4)
            
        # Last 7 days chart data
        cursor.execute('''
            SELECT date, SUM(duration_minutes) as tot_mins, SUM(energy_kwh) as tot_energy
            FROM pump_sessions
            WHERE pump_device_id = ?
            GROUP BY date
            ORDER BY date DESC
            LIMIT 7
        ''', (pump_device_id,))
        rows = list(cursor.fetchall())
        rows.reverse()
        
        for r in rows:
            summary['daily_chart_labels'].append(r['date'])
            summary['daily_chart_energy'].append(round(r['tot_energy'] or 0.0, 4))
            summary['daily_chart_runtime'].append(round((r['tot_mins'] or 0.0) / 60.0, 2))
            
    except Exception as e:
        print(f"Database Error in analytics: {e}")
    finally:
        conn.close()
        
    return summary
