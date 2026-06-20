import time

# sensor_id -> {"until": timestamp, "strength": float}  (ventilation active)
_active_mitigations = {}

# sensor_id -> True if currently in an unresolved spike, waiting for operator action
_unresolved_spike = {}

MITIGATION_DURATION = 20
MITIGATION_STRENGTH = 0.035

def activate(sensor_id: int):
    _active_mitigations[sensor_id] = {
        "until": time.time() + MITIGATION_DURATION,
        "strength": MITIGATION_STRENGTH,
    }
    _unresolved_spike[sensor_id] = False

def is_active(sensor_id: int) -> bool:
    m = _active_mitigations.get(sensor_id)
    if not m:
        return False
    if time.time() > m["until"]:
        del _active_mitigations[sensor_id]
        return False
    return True

def get_remaining(sensor_id: int) -> float:
    m = _active_mitigations.get(sensor_id)
    if not m:
        return 0
    remaining = m["until"] - time.time()
    return max(0, round(remaining, 1))

def mark_unresolved_spike(sensor_id: int):
    _unresolved_spike[sensor_id] = True

def is_unresolved_spike(sensor_id: int) -> bool:
    return _unresolved_spike.get(sensor_id, False)
