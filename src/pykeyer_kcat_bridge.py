# callback handler for use with xmlrpc_proxy_logger.py
# provides bridge between kcat and pyKeyer
# start this first like this:
# python xmlrpc_proxy_logger.py --proxy-port 7362 --handler pykeyer_kcat_bridge.py:handle
# kcat will issue xmlrpc calls to this code, pyKeyer will send simple commands via socket
# too much is hard coded at this time...

import socket
import threading
import atexit
import datetime
import time

# Shared rig state
state = {
    "frequency": 7000000.0,
    "mode": "CW",
    "bandwidth": "500",
    "trx": "RX",
    "listener_started": False,
    "listener_socket": None
}

now = int(round(time.time() * 1000))
print(f"[pykeyer_kcat_hook] module loaded at {now}")

def _start_listener():
    def handle_connection(conn, addr):
        with conn:
            print(f"[listener] Connection established from {addr}")
            while True:
                try:
                    data = conn.recv(1024)
                    if not data:
                        print(f"[listener] Connection from {addr} closed by peer.")
                        break  # client closed connection

                    command = data.decode("utf-8").strip()
                    print(f"[listener] Received from {addr}: {command}")

                    if command == "<CMD>get_frequency</CMD>":
                        value = state["frequency"]
                        response = f"<RESPONSE>{value}</RESPONSE>"
                    elif command == "<CMD>get_mode</CMD>":
                        value = state["mode"]
                        response = f"<RESPONSE>{value}</RESPONSE>"
                    elif command.startswith("<SET>set_freq=") and command.endswith("</SET>"):
                        try:
                            freq_val = float(command[len("<SET>set_freq="):-len("</SET>")])
                            state["frequency"] = freq_val
                            response = "<RESPONSE>OK</RESPONSE>"
                        except Exception as e:
                            response = f"<RESPONSE>Error parsing frequency: {e}</RESPONSE>"
                    elif command.startswith("<SET>set_mode=") and command.endswith("</SET>"):
                        try:
                            mode_val = command[len("<SET>set_mode="):-len("</SET>")]
                            state["mode"] = mode_val
                            response = "<RESPONSE>OK</RESPONSE>"
                        except Exception as e:
                            response = f"<RESPONSE>Error parsing mode: {e}</RESPONSE>"
                    else:
                        response = "<RESPONSE>Unknown command</RESPONSE>"

                    conn.sendall(response.encode("utf-8"))

                except Exception as e:
                    print(f"[listener] Error handling connection {addr}: {e}")
                    break

    def listener():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if state.get("listener_socket"):
                print("[listener] Already started or failed previously — skipping bind.")
                return

            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("localhost", 7365))
            s.listen()
            state["listener_socket"] = s
            print("[listener] TCP listener started on port 7365")

            while True:
                try:
                    conn, addr = s.accept()
                    thread = threading.Thread(target=handle_connection, args=(conn, addr), daemon=True)
                    thread.start()
                except Exception as e:
                    print(f"[listener] Accept error: {e}")

    thread = threading.Thread(target=listener, daemon=True)
    thread.start()
    state["listener_started"] = True

    def shutdown_listener():
        sock = state.get("listener_socket")
        if sock:
            print("[shutdown] Closing listener socket on port 7365")
            sock.close()
    atexit.register(shutdown_listener)

def handle(method, params):
    print(f"[handler] Received method call: {method} with params: {params}")

    retval = None

    elapsed = (int(round(time.time() * 1000)) - now)
    if not state["listener_started"]:
        _start_listener()

    #print(f"{elapsed:08d} received request {method}({params})")

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
