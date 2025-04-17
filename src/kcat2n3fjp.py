from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import signal
import sys

from enum import IntEnum
import argparse

import time
program_start_time = time.time()

IGNORED_METHODS = {
    'rig.set_smeter',
    'main.set_wf_sideband',
    # Add more if needed
}

class DebugLevel(IntEnum):
    NONE = 0
    BUG = 1
    ERR = 2
    WARN = 3
    VERBOSE = 4
    TRACE = 5

DEBUG_LEVEL = DebugLevel.NONE

LOGGER = None

def debug_print(level, *args, **kwargs):
    if level <= DEBUG_LEVEL:
        elapsed_ms = int((time.time() - program_start_time) * 1000)
        timestamp = f"{elapsed_ms:08d}"  # 8-digit, zero-padded
        print(f"{timestamp} [{DEBUG_LEVEL.name}]:", *args, **kwargs)

method_log = {}
last_state = {
    "frequency": 7000.0,
    "mode": "CW",
    "bandwidth": "500"
}

BAND_TABLE = [
    (1800000, 2000000, "160m"),
    (3500000, 4000000, "80m"),
    (5330500, 5405500, "60m"),
    (7000000, 7300000, "40m"),
    (10100000, 10150000, "30m"),
    (14000000, 14350000, "20m"),
    (18068000, 18168000, "17m"),
    (21000000, 21450000, "15m"),
    (24890000, 24990000, "12m"),
    (28000000, 29700000, "10m"),
    (50000000, 54000000, "6m"),
    (144000000, 148000000, "2m"),
    (222000000, 225000000, "1.25m"),
    (420000000, 450000000, "70cm")
]

def freq_to_band(freq):
    try:
        freq = int(freq)
    except:
        return "Unknown"
    for low, high, name in BAND_TABLE:
        if low <= freq < high:
            return name
    return "Unknown"

class KCATHandler:
    def _dispatch(self, method, params):
        if (DEBUG_LEVEL >= DebugLevel.VERBOSE):
            if method not in method_log:
                method_log[method] = []
            method_log[method].append(params)

        debug_print(DebugLevel.VERBOSE, f"Method: {method}, Params: {params}", flush=True)

        if method == "system.multicall":
            results = []
            for call in params[0]:  # list of dicts
                inner_method = call.get("methodName")
                inner_params = call.get("params", [])
                result = self.handle_individual_call(inner_method, inner_params)
                debug_print(DebugLevel.TRACE, f"{inner_method} returned: {result}")
                results.append([result])  # Wrap in list per XML-RPC spec
            debug_print(DebugLevel.TRACE, f"{method} returned: {results}")
            return results
        else:
            result = self.handle_individual_call(method, params)
            debug_print(DebugLevel.TRACE, f"{method} returned: {result}")
            return result

    def handle_individual_call(self, method, params):
        debug_print(DebugLevel.VERBOSE, f"Handling: {method} {params}", flush=True)

        if method == 'rig.take_control':
            debug_print(DebugLevel.VERBOSE, f"{method} accepted", flush=True)
            return None

        if method == 'rig.release_control':
            debug_print(DebugLevel.VERBOSE, f"{method} accepted", flush=True)
            return None

        elif method == 'rig.set_name' and len(params) > 0:
            debug_print(DebugLevel.VERBOSE, f"{method} received, name is {params[0]}", flush=True)
            return None
        
        elif method == 'rig.set_modes' and len(params) > 0:
            debug_print(DebugLevel.VERBOSE, f"{method} received, modes are {params}", flush=True)
            return None

        elif method == 'rig.set_bandwidths' and len(params) > 0:
            debug_print(DebugLevel.VERBOSE, f"{method} received, bandwidths are {params}", flush=True)
            return None

        elif method == 'rig.set_frequency' and len(params) > 0:
            new_freq = params[0]
            old_freq = last_state["frequency"]
            debug_print(DebugLevel.VERBOSE, f"{method} received, new frequency is {params}, frequency was {old_freq}", flush=True)
            if new_freq != old_freq:
                last_state["frequency"] = new_freq
                debug_print(DebugLevel.WARN, f"FREQ CHANGE: {new_freq} Hz", flush=True)

            # send frequency change to N3FJP
            LOGGER.update_from_state(last_state["frequency"], last_state["mode"])

            return old_freq

        elif method == 'rig.set_mode' and len(params) > 0:
            new_mode = params[0]
            old_mode = last_state["mode"]
            debug_print(DebugLevel.VERBOSE, f"{method} received, new mode is {params}, mode was {old_mode}", flush=True)
            if new_mode != old_mode:
                last_state["mode"] = new_mode
                debug_print(DebugLevel.WARN, f"MODE CHANGE: from {old_mode} to {new_mode}", flush=True)

            # send mode change to N3FJP
            LOGGER.update_from_state(last_state["frequency"], last_state["mode"])

            return None

        elif method == 'rig.set_bandwidth' and len(params) > 0:
            new_bw = params[0]
            old_bw = last_state["bandwidth"]
            debug_print(DebugLevel.VERBOSE, f"{method} received, new mobandwidth is {params}, bandwidth was {old_bw}", flush=True)
            if new_bw != old_bw:
                last_state["bandwidth"] = new_bw
                debug_print(DebugLevel.WARN, f"BANDWIDTH CHANGE: from {old_bw} to {new_bw}", flush=True)
            return None

        elif method == 'rig.set_smeter' and len(params) > 0:
            # don't care about this one
            debug_print(DebugLevel.VERBOSE, f"{method} received, parms {params}, ignoring", flush=True)
            return None

        elif method == 'main.set_wf_sideband' and len(params) > 0:
            # don't care about this one
            debug_print(DebugLevel.VERBOSE, f"{method} received, parms {params}, ignoring", flush=True)
            return None

        elif method == 'main.get_trx_state':
            debug_print(DebugLevel.VERBOSE, f"{method} received, returning RX", flush=True)
            return "RX"

        elif method == 'main.get_frequency':
            old_freq = last_state["frequency"]
            debug_print(DebugLevel.VERBOSE, f"{method} received, returning {old_freq}", flush=True)
            return old_freq

        elif method == 'rig.get_mode':
            old_mode = last_state["mode"]
            debug_print(DebugLevel.VERBOSE, f"{method} received, returning {old_mode}", flush=True)
            return old_mode

        elif method == 'rig.get_bandwidth':
            old_bw = last_state["bandwidth"]
            debug_print(DebugLevel.VERBOSE, f"{method} received, returning {old_bw}", flush=True)
            return old_bw

        elif method in IGNORED_METHODS:
            debug_print(DebugLevel.VERBOSE, f"{method} received, params={params}, ignoring", flush=True)
            return None

        else:
            debug_print(DebugLevel.BUG, f"Unhandled method or parameter shape: {method}, params={params}")
            return None

import socket

class LoggerClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.last_band = None
        self.last_mode = None
        self.last_freq = None

    def connect(self):
        if self.sock:
            return
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=2)
            debug_print(DebugLevel.WARN, f"Connected to logger at {self.host}:{self.port}")
        except Exception as e:
            debug_print(DebugLevel.ERR, f"Logger connection failed: {e}")
            self.sock = None

    def send_and_expect_ack(self, message):
        if not self.sock:
            self.connect()
        if not self.sock:
            return  # still not connected

        try:
            self.sock.sendall((message + "\r\n").encode("utf-8"))
            debug_print(DebugLevel.TRACE, f"[LOGGER OUT] {message}")

            response = self.sock.recv(1024).decode("utf-8")
            if "<READBMFRESPONSE>" in response:
                debug_print(DebugLevel.TRACE, "[LOGGER IN] Received acknowledgment.")
            else:
                debug_print(DebugLevel.ERR, f"[LOGGER IN] Unexpected response: {response}")

        except Exception as e:
            debug_print(DebugLevel.ERR, f"Failed to send to logger: {e}")
            self.sock = None  # Drop connection to try again later

    def send_band_mode(self, band, mode):
        if band != self.last_band or mode != self.last_mode:
            message = f"<CMD><CHANGEBM><BAND>{band}</BAND><MODE>{mode}</MODE></CHANGEBM></CMD>"
            self.send_and_expect_ack(message)
            self.last_band = band
            self.last_mode = mode

    def send_frequency(self, freq_hz):
        freq_mhz = round(freq_hz / 1_000_000, 3)
        if freq_hz != self.last_freq:
            message = f"<CMD><UPDATE><CONTROL>TXTENTRYFREQUENCY</CONTROL><VALUE>{freq_mhz:.3f}</VALUE></UPDATE></CMD>"
            self.send_and_expect_ack(message)
            self.last_freq = freq_hz

    def update_from_state(self, freq, mode):
        band = freq_to_band(freq)
        self.send_band_mode(band=band.replace("m", ""), mode=mode)
        self.send_frequency(freq)

def print_summary():
    if (DEBUG_LEVEL >= DebugLevel.VERBOSE):
        print("\n--- XML-RPC Method Call Summary ---")
        for method, args_list in method_log.items():
            print(f"\nMethod: {method}")
            for i, args in enumerate(args_list, start=1):
                print(f"  [{i}] args: {args}")
    print("\nShutting down server.")
    sys.exit(0)

def main(kcat_host, kcat_port, logger_host, logger_port):
    server = SimpleXMLRPCServer(
        (kcat_host, kcat_port),
        requestHandler=SimpleXMLRPCRequestHandler,
        allow_none=True,
        logRequests=False
    )
    server.register_instance(KCATHandler())

    global LOGGER
    LOGGER = LoggerClient(logger_host, logger_port)

    print(f"KCAT XML-RPC Server listening on {kcat_host}:{kcat_port}")
    print(f"Logger target will be {logger_host}:{logger_port}")
    print(f"Debug level is {DEBUG_LEVEL.name} ({DEBUG_LEVEL})")
    print("Ctrl+C to stop and show summary.")

    signal.signal(signal.SIGINT, lambda sig, frame: print_summary())

    server.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KCAT to N3FJP: KCAT XMLRPC calls are forwarded to n3fjp client API")
    parser.add_argument("--debug", choices=[lvl.name for lvl in DebugLevel], default="NONE",
                        help="Set debug level (default: NONE)")
    parser.add_argument("--kcat_host", default="localhost",
                        help="Host interface to bind KCAT XML-RPC server (default: localhost)")
    parser.add_argument("--kcat_port", type=int, default=7362,
                        help="Port to bind KCAT XML-RPC server (default: 7362)")
    parser.add_argument("--logger_host", default="localhost",
                        help="Host for logger connection (default: localhost)")
    parser.add_argument("--logger_port", type=int, default=1100,
                        help="Port for logger connection (default: 1100)")

    args = parser.parse_args()
    DEBUG_LEVEL = DebugLevel[args.debug]

    # Pass args to main()
    main(
        kcat_host=args.kcat_host,
        kcat_port=args.kcat_port,
        logger_host=args.logger_host,
        logger_port=args.logger_port
    )
