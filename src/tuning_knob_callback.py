# tuning_knob_callback.py
# adds support for the Kachina 505DSP tuning knob, 505TK.
# callback for tuning knob input via serial mouse protocol
# use with xmlrpc_proxy_logger.py as a callback handler

import serial
import threading
import time
import atexit
from datetime import datetime

PORT = "/dev/ttyUSB3"
BAUD = 1200
BYTESIZE = serial.SEVENBITS
PARITY = serial.PARITY_NONE
STOPBITS = serial.STOPBITS_ONE

# Shared rig state
state = {
    "frequency": 7000000.0,
    "delta_f": 0.0,
    "mode": "CW",
    "bandwidth": "500",
    "trx": "RX",
    "knob_thread": None,
    "knob_active": False
}

now = int(round(time.time() * 1000))
print(f"[tuning_knob_hook] module loaded at {now}")

def decode_signed_x(b1, b2):
    b1 &= 0x03
    val = b2 + (b1 << 6)
    val &= 0x3F
    return val - 64 if val >= 32 else val

def parse_mouse_packet(packet):
    if len(packet) != 3:
        return None
    b1, b2, b3 = packet
    if b1 & 0x40 == 0:
        return None
    dx = decode_signed_x(b1, b2)
    return b1, b2, b3, dx

def scale_from_speed(delta_t):
    if delta_t > 0.3:
        return 1
    elif delta_t > 0.1:
        return 10
    elif delta_t > 0.03:
        return 100
    else:
        return 1000

def _knob_listener():
    last_movement_time = None
    buffer = bytearray()

    try:
        with serial.Serial(PORT, BAUD, bytesize=BYTESIZE,
                           parity=PARITY, stopbits=STOPBITS, timeout=1) as ser:
            print(f"[knob] Listening on {PORT} @ {BAUD} baud...")
            while state["knob_active"]:
                byte = ser.read(1)
                if not byte:
                    continue
                b = byte[0] & 0x7F  # Ignore D7
                if b & 0x40:
                    buffer = bytearray([b])
                else:
                    buffer.append(b)

                if len(buffer) == 3:
                    result = parse_mouse_packet(buffer)
                    buffer.clear()

                    if not result:
                        continue

                    b1, b2, b3, dx = result
                    now_time = time.time()
                    delta_t = 0

                    if dx != 0:
                        if last_movement_time is None:
                            last_update_time = now_time;
                            scale = 1
                        else:
                            delta_t = min(now_time - last_movement_time, 0.999)
                            scale = scale_from_speed(delta_t)

                        last_movement_time = now_time # last time the knob moved

                        state["delta_f"] += dx * scale
                        if now_time - last_update_time > 0.2: # don't expect the radio to update very often
                            state["frequency"] += state["delta_f"]
                            state["delta_f"] = 0.0
                            last_update_time = now_time # last time frequ was updated

                        #print(f"[knob] ΔX: {dx:>3}, Scaled Δ: {dx*scale:>4}, "
                        #      f"Freq: {old_freq:.1f} → {new_freq:.1f} (×{scale})")

    except Exception as e:
        print(f"[knob] Error: {e}")

def _start_knob_listener():
    if state["knob_thread"]:
        return
    state["knob_active"] = True
    t = threading.Thread(target=_knob_listener, daemon=True)
    t.start()
    state["knob_thread"] = t

    def shutdown():
        print("[shutdown] Stopping knob thread.")
        state["knob_active"] = False
    atexit.register(shutdown)

def handle(method, params):
    if not state["knob_thread"]:
        _start_knob_listener()

    retval = None

    if method == "system.multicall" and len(params) == 1 and isinstance(params[0], list):
        results = []
        for call in params[0]:
            try:
                sub_method = call['methodName']
                sub_params = call.get('params', [])
                sub_result = handle(sub_method, sub_params)
                results.append([sub_result])
            except Exception as e:
                results.append({'faultCode': 1, 'faultString': str(e)})
        return results


    if method == "rig.set_frequency" and len(params) == 1:
        retval = state["frequency"]
        state["frequency"] = params[0]
    elif method == "rig.get_frequency" and len(params) == 1:
        retval = state["frequency"]
    elif method == "rig.set_mode" and len(params) == 1:
        state["mode"] = params[0]
    elif method == "rig.get_mode" and len(params) == 1:
        retval = state["mode"]
    elif method == "rig.set_bandwidth" and len(params) == 1:
        state["bandwidth"] = params[0]
    elif method == "rig.get_bandwidth" and len(params) == 1:
        retval = state["bandwidth"]
    elif method == "main.get_trx_state" and len(params) == 1:
        retval = state["trx"]

    return retval
