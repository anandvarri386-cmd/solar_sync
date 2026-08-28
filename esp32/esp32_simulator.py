import time
import requests
import random
from datetime import datetime

# Server details
SERVER_URL = "http://localhost:5000/api/esp32/data"

# Local simulator variables
sim_pump_status = 0
sim_runtime = 0.0
sim_energy = 0.0

# Print utility coloring
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

print(f"{CYAN}===================================================={RESET}")
print(f"{CYAN}       SOLARSYNC AI - ESP32 TELEMETRY SIMULATOR     {RESET}")
print(f"{CYAN}===================================================={RESET}")
print(f"Targeting server endpoint: {SERVER_URL}")
print(f"Initializing loop... Press Ctrl+C to terminate.")
print("")

try:
    while True:
        # 1. Simulate voltage depending on simulated solar hour
        # Varies based on time of day (peaks at noon)
        now_hour = datetime.now().hour
        base_volt = 0.1
        if 6 <= now_hour <= 18:
            dist_from_noon = abs(now_hour - 12.5)
            base_volt = max(8.0, 18.0 - (dist_from_noon * 1.5))
        
        # Add random fluctuations (e.g. cloud passage)
        voltage = base_volt + random.uniform(-0.15, 0.15)
        
        # 2. Simulate current and power draw based on pump state
        if sim_pump_status == 1 and voltage > 10.0:
            # Draw current (1.8A to 2.7A)
            current = round(random.uniform(2.10, 2.55), 2)
            power = voltage * current
            # 1 second increment in hours
            sim_runtime += 1.0 / 3600.0
            # 1 second increment in energy (kWh)
            sim_energy += (power * (1.0 / 3600.0)) / 1000.0
        else:
            current = 0.0
            power = 0.0
            
        # 3. Build payload
        payload = {
            "voltage": round(voltage, 2),
            "current": round(current, 2),
            "power": round(power, 2),
            "pump_status": sim_pump_status,
            "runtime": round(sim_runtime, 5),
            "energy": round(sim_energy, 6)
        }
        
        # 4. Post data to Flask REST API
        try:
            res = requests.post(SERVER_URL, json=payload, timeout=2)
            if res.status_code == 200:
                data = res.json()
                server_target = int(data.get("target_status", 0))
                
                # Check for state change
                if server_target != sim_pump_status:
                    status_text = f"{GREEN}ON{RESET}" if server_target == 1 else f"{RED}OFF{RESET}"
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {YELLOW}Command Received:{RESET} Switch Relay {status_text}")
                    sim_pump_status = server_target
                    
                status_color = GREEN if sim_pump_status == 1 else YELLOW
                status_label = "ACTIVE" if sim_pump_status == 1 else "STANDBY"
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {CYAN}Tx:{RESET} "
                      f"V={voltage:.1f}V | I={current:.2f}A | P={power:.1f}W | "
                      f"Status={status_color}{status_label}{RESET} | "
                      f"E={sim_energy:.5f}kWh")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {RED}Error:{RESET} Server returned HTTP {res.status_code}")
                
        except requests.exceptions.RequestException as req_err:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {RED}Connection failed:{RESET} Is Flask server app.py running on port 5000? ({req_err})")
            
        time.sleep(1.0)
        
except KeyboardInterrupt:
    print("")
    print(f"{YELLOW}Simulation interrupted by operator. Offline.{RESET}")
