import socket
import threading
import atexit
import datetime
import time

# Shared rig state
state = {
    "frequency": None,
    "mode": None,
    "listener_started": False,
    "listener_socket": None
}

now = int(round(time.time() * 1000))
print(f"[pykeyer_kcat_hook] module loaded at {now}")

def _start_listener():
    def listener():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if state.get("listener_socket"):
                print("[listener] Already started or failed previously — skipping bind.")
                return

            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("localhost", 7367))
            s.listen()
            state["listener_socket"] = s
            while True:
                try:
                    conn, addr = s.accept()
                    with conn:
                        data = conn.recv(1024).decode("utf-8").strip()
                        if data == "<CMD>get_frequency</CMD>":
                            freq = state["frequency"]
                            response = f"<RESPONSE>{freq}</RESPONSE>" if freq is not None else "<RESPONSE>None</RESPONSE>"
                        elif data == "<CMD>get_mode</CMD>":
                            mode = state["mode"]
                            response = f"<RESPONSE>{mode}</RESPONSE>" if mode is not None else "<RESPONSE>None</RESPONSE>"
                        else:
                            response = "<RESPONSE>Unknown command</RESPONSE>"
                        conn.sendall(response.encode("utf-8"))
                except Exception as e:
                    print(f"[listener error] {e}")

    thread = threading.Thread(target=listener, daemon=True)
    thread.start()
    state["listener_started"] = True

    def shutdown_listener():
        sock = state.get("listener_socket")
        if sock:
            print("[shutdown] Closing listener socket on port 7367")
            sock.close()
    atexit.register(shutdown_listener)

def on_request(method, params):
    elapsed = (int(round(time.time() * 1000)) - now)
    if not state["listener_started"]:
        _start_listener()

    print(f"{elapsed:08d} received request {method}({params})")
    if method == "rig.set_frequency" and len(params) == 1:
        state["frequency"] = params[0]
    elif method == "rig.set_mode" and len(params) == 1:
        state["mode"] = params[0]
    #elif method == "rig.set_smeter" and len(params) == 1:
    #    print(f"{elapsed:08d} received smeter update: {params}")

    return method, params

def on_response(method, params, result):
    if not state["listener_started"]:
        _start_listener()
    return result
