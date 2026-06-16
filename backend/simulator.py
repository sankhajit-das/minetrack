import time
import random
import requests

# We will continuously alternate destinations until we get a 200/201 success code
ENDPOINTS = [
    "http://backend:8000/telemetry",
    "http://backend:8000/api/telemetry",
    "http://backend:8000/readings",
    "http://backend:8000/api/v1/telemetry"
]

sensors = [
    {"sensor_code": "CH4-01", "type": "Methane", "unit": "%", "base": 1.1, "warn": 1.5, "crit": 2.5},
    {"sensor_code": "CO-02", "type": "Carbon Monoxide", "unit": "ppm", "base": 28.0, "warn": 35.0, "crit": 50.0},
    {"sensor_code": "TEMP-03", "type": "Sub-surface Temp", "unit": "°C", "base": 36.5, "warn": 38.0, "crit": 45.0}
]

print("Initializing robust simulator tracking mesh...", flush=True)
time.sleep(5)

active_endpoint = ENDPOINTS[0]

while True:
    for s in sensors:
        variance = random.uniform(-0.1, 0.1) if s["type"] != "Carbon Monoxide" else random.uniform(-1.5, 1.5)
        current_value = max(0, s["base"] + variance)
        
        status = "normal"
        if current_value >= s["crit"]: status = "critical"
        elif current_value >= s["warn"]: status = "warning"
            
        payload = {
            "sensor_code": s["sensor_code"],
            "type": s["type"],
            "unit": s["unit"],
            "value": float(current_value),
            "status": status,
            "warn_threshold": s["warn"],
            "crit_threshold": s["crit"]
        }
        
        # Attempt to cycle across routing blocks to bypass 404 gates
        for url in ENDPOINTS:
            try:
                res = requests.post(url, json=payload, timeout=1)
                if res.status_code in [200, 201]:
                    active_endpoint = url
                    break
            except Exception:
                continue
                
    time.sleep(1)
