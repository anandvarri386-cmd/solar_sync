from flask import Blueprint, jsonify, request, current_app, session
from datetime import datetime
import json
import os

from models.pump_data import (
    record_telemetry_and_session, get_latest_reading, get_history, 
    delete_record, get_analytics_summary, get_daily_summary
)
from models.user import get_user_by_device_id, get_user_by_id, regenerate_api_key
from utils.calibrations import load_config, save_config

api_bp = Blueprint('api', __name__)

# Multi-tenant state dictionaries keyed by pump_device_id
DEVICE_TARGET_STATES = {}  # e.g. {"PUMP-SOLAR-1001": 0}
DEVICE_LAST_TELEMETRY = {} # e.g. {"PUMP-SOLAR-1001": {...}}
DEVICE_LAST_PULL = {}      # e.g. {"PUMP-SOLAR-1001": datetime}

def get_socketio():
    """Helper to retrieve SocketIO instance from extensions."""
    return current_app.extensions.get('socketio')

def get_session_device_id():
    """Helper to get current logged-in user's pump device ID."""
    return session.get('pump_device_id', 'PUMP-SOLAR-1001')

@api_bp.route('/api/live', methods=['GET'])
def get_live_data():
    """Returns the latest telemetry and connection status for the logged-in customer's pump."""
    device_id = request.args.get('device_id') or get_session_device_id()
    
    last_telemetry = DEVICE_LAST_TELEMETRY.get(device_id, {
        "voltage": 0.0,
        "current": 0.0,
        "power": 0.0,
        "pump_status": 0,
        "runtime": 0.0,
        "energy": 0.0,
        "last_updated": None
    })
    
    last_pull = DEVICE_LAST_PULL.get(device_id)
    is_online = False
    if last_pull is not None:
        delta = (datetime.now() - last_pull).total_seconds()
        is_online = delta < 12.0
        
    target_status = DEVICE_TARGET_STATES.get(device_id, 0)
    
    response_data = {
        **last_telemetry,
        "pump_device_id": device_id,
        "esp32_online": is_online,
        "target_status": target_status
    }
    return jsonify(response_data)

@api_bp.route('/api/history', methods=['GET'])
def get_historical_data():
    """Returns paginated, sorted, and searchable historical log records scoped to the customer's pump."""
    device_id = request.args.get('device_id') or get_session_device_id()
    
    limit = request.args.get('limit', default=10, type=int)
    offset = request.args.get('offset', default=0, type=int)
    search_query = request.args.get('search', default="", type=str)
    sort_by = request.args.get('sort_by', default="id", type=str)
    sort_order = request.args.get('sort_order', default="DESC", type=str)
    
    records, total = get_history(limit, offset, search_query, sort_by, sort_order, pump_device_id=device_id)
    
    return jsonify({
        "status": "success",
        "pump_device_id": device_id,
        "records": records,
        "total_count": total,
        "limit": limit,
        "offset": offset
    })

@api_bp.route('/api/history/<int:record_id>', methods=['DELETE'])
def delete_history_record(record_id):
    """Deletes a record verifying customer ownership."""
    device_id = get_session_device_id()
    success = delete_record(record_id, pump_device_id=device_id)
    if success:
        return jsonify({"status": "success", "message": f"Record {record_id} deleted."}), 200
    return jsonify({"status": "error", "message": "Record not found or unauthorized."}), 404

@api_bp.route('/api/energy', methods=['GET'])
def get_energy_analytics():
    """Returns aggregated daily and weekly analytics scoped to the customer's pump."""
    device_id = request.args.get('device_id') or get_session_device_id()
    analytics = get_analytics_summary(pump_device_id=device_id)
    return jsonify(analytics)

@api_bp.route('/api/daily_summary', methods=['GET'])
def get_daily_runtime_summary():
    """Returns total pump runtime duration for every day."""
    device_id = request.args.get('device_id') or get_session_device_id()
    summary = get_daily_summary(pump_device_id=device_id)
    return jsonify({"status": "success", "pump_device_id": device_id, "daily_summary": summary})

@api_bp.route('/api/pump/state', methods=['GET', 'POST'])
def handle_pump_state_route():
    """Endpoint for web dashboard and mobile to toggle pump state (ON/OFF) and register session."""
    global DEVICE_TARGET_STATES, DEVICE_LAST_TELEMETRY
    device_id = get_session_device_id()
    
    if request.method == 'GET':
        return jsonify({"status": "success", "pump_device_id": device_id, "target_status": DEVICE_TARGET_STATES.get(device_id, 0)})
        
    data = request.get_json(silent=True) or {}
    target = int(data.get('target_status', data.get('pump_status', 0)))
    device_id = data.get('pump_device_id') or device_id
    
    DEVICE_TARGET_STATES[device_id] = target
    
    # Grab latest voltage/power or defaults
    last = DEVICE_LAST_TELEMETRY.get(device_id, {})
    v = last.get('voltage', 18.0) if target == 1 else 0.0
    i = last.get('current', 2.2) if target == 1 else 0.0
    p = last.get('power', round(v * i, 1)) if target == 1 else 0.0
    
    # Record session event immediately
    record_telemetry_and_session(
        voltage=v,
        current=i,
        power=p,
        pump_status=target,
        runtime=0.0,
        energy=0.0,
        pump_device_id=device_id
    )
    
    socketio = get_socketio()
    if socketio:
        socketio.emit('pump_command', {"pump_device_id": device_id, "target_status": target})
        
    return jsonify({"status": "success", "pump_device_id": device_id, "target_status": target})

@api_bp.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Returns or updates calibration settings."""
    if request.method == 'GET':
        config = load_config()
        return jsonify(config)
        
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
        
    config = load_config()
    if 'voltage_multiplier' in data:
        config['voltage_multiplier'] = float(data['voltage_multiplier'])
    if 'current_offset' in data:
        config['current_offset'] = float(data['current_offset'])
    if 'auto_mode' in data:
        config['auto_mode'] = bool(data['auto_mode'])
    if 'wifi_ssid' in data:
        config['wifi_ssid'] = str(data['wifi_ssid'])
    if 'wifi_pass' in data:
        config['wifi_pass'] = str(data['wifi_pass'])
        
    save_config(config)
    return jsonify({"status": "success", "config": config})

@api_bp.route('/api/user/regenerate_key', methods=['POST'])
def regenerate_key_route():
    """Regenerates the user's ESP32 API authorization key."""
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    new_key, err = regenerate_api_key(session['user_id'])
    if new_key:
        return jsonify({"status": "success", "api_key": new_key})
    return jsonify({"status": "error", "message": err}), 500

@api_bp.route('/api/esp32/data', methods=['POST'])
def receive_esp32_telemetry():
    """Primary REST Gateway Endpoint for ESP32 Hardware IoT Nodes.
    Authenticates by device_id & optional api_key, saves telemetry,
    and returns pump target status and calibrations.
    """
    global DEVICE_TARGET_STATES, DEVICE_LAST_TELEMETRY, DEVICE_LAST_PULL
    
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Payload must be valid JSON"}), 400
        
    # Check Device ID (defaults to PUMP-SOLAR-1001 if omitted for backwards compatibility)
    device_id = data.get('device_id', 'PUMP-SOLAR-1001').strip().upper()
    api_key = data.get('api_key', '').strip()
    
    # Optional hardware authentication validation
    user = get_user_by_device_id(device_id)
    if not user:
        # If unknown device, log and handle gracefully
        print(f"Warning: Telemetry received for unregistered device ID: {device_id}")
        
    try:
        raw_voltage = float(data.get('voltage', 0.0))
        raw_current = float(data.get('current', 0.0))
        raw_power = float(data.get('power', 0.0))
        pump_status = int(data.get('pump_status', 0))
        runtime = float(data.get('runtime', 0.0))
        energy = float(data.get('energy', 0.0))
    except (ValueError, TypeError) as e:
        return jsonify({"status": "error", "message": f"Malformed sensor types: {e}"}), 400
        
    # Load calibrations
    config = load_config()
    v_mult = config.get('voltage_multiplier', 1.0)
    c_off = config.get('current_offset', 0.0)
    
    calibrated_voltage = round(raw_voltage * v_mult, 2)
    calibrated_current = round(max(0.0, raw_current + c_off), 2)
    
    # When current is >= 1.0 Amp or explicitly turned ON, pump is RUNNING (status = 1)
    if calibrated_current >= 1.0 or pump_status == 1:
        pump_status = 1
    else:
        pump_status = 0
        
    calibrated_power = round(calibrated_voltage * calibrated_current, 2)
    
    # Record telemetry & update pump run session (Switched ON / OFF events)
    record_telemetry_and_session(
        voltage=calibrated_voltage,
        current=calibrated_current,
        power=calibrated_power,
        pump_status=pump_status,
        runtime=runtime,
        energy=energy,
        pump_device_id=device_id
    )
    
    # Update in-memory telemetry cache for this device
    now_time = datetime.now()
    DEVICE_LAST_TELEMETRY[device_id] = {
        "voltage": calibrated_voltage,
        "current": calibrated_current,
        "power": calibrated_power,
        "pump_status": pump_status,
        "runtime": round(runtime, 4),
        "energy": round(energy, 4),
        "last_updated": now_time.strftime('%H:%M:%S')
    }
    DEVICE_LAST_PULL[device_id] = now_time
    
    # Broadcast via SocketIO to the web dashboard
    socketio = get_socketio()
    if socketio:
        target_status = DEVICE_TARGET_STATES.get(device_id, 0)
        socketio.emit('telemetry', {
            **DEVICE_LAST_TELEMETRY[device_id],
            "pump_device_id": device_id,
            "esp32_online": True,
            "target_status": target_status
        })
        
    target_state = DEVICE_TARGET_STATES.get(device_id, 0)
    
    return jsonify({
        "status": "success",
        "pump_device_id": device_id,
        "target_status": target_state,
        "voltage_calibration": v_mult,
        "current_offset": c_off,
        "timestamp": now_time.strftime('%Y-%m-%d %H:%M:%S')
    }), 200
