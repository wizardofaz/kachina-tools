# xmlrpc_proxy_logger.py

# Copyright 2025, Bill Bennett, N7DZ
#
# Originally built as a debugging tool to sit between kcat and 
# fldigi to examine rpcxml interactions between those two. 
# Hopefully useful more generally. 
# 
# This tool runs an xmlrpc server and client, and passes through
# all traffic from server to client. Ports of both are configurable,
# as well as the address of the target server. Traffic is logged to
# the terminal session or to a file. The purpose is to allow 
# examining traffic for reverse-engineering or debugging. 
#
# Specific method names can be renamed in passing, or blocked. 
# 
# The software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this code.  If not, see <http:#www.gnu.org/licenses/>.
#
# This code was developed with support from Jules, my ChatGPT-based 
# coding assistant. 
#
# Please report all bugs and problems to n7dz@arrl.net.


import argparse
import time
import threading
import sys
import importlib.util
from xmlrpc.server import SimpleXMLRPCRequestHandler
from xmlrpc.server import SimpleXMLRPCServer as BaseServer
from socketserver import ThreadingMixIn
import xmlrpc.client
import code
import queue
import uuid

# Parse command-line arguments
parser = argparse.ArgumentParser(description="XML-RPC Proxy Logger")
parser.add_argument("--target-host", default="localhost", help="Target host running the xml server (default: localhost)")
parser.add_argument("--target-port", type=int, default=7363, help="Target port (default: 7363)")
parser.add_argument("--proxy-port", type=int, default=7362, help="Port for this proxy to listen on (default: 7362)")
parser.add_argument("--list-methods", action="store_true", help="List available methods on the target before starting the proxy")
parser.add_argument("--verbose-methods", action="store_true", help="Include method signatures and help text when listing methods")
parser.add_argument("--quiet", action="store_true", help="Suppress routine log output from proxy activity")
parser.add_argument("--interactive", action="store_true", help="Open an interactive shell after starting the proxy")
parser.add_argument("--logfile", type=str, help="Optional file to append full log output to")
parser.add_argument("--method-map", action="append", help="Block or remap method calls: e.g. rig.take_control=BLOCK or rig.set_mode=main.set_rig_mode")
parser.add_argument("--on-request", help="Path to Python module containing `on_request(method, params)`")
parser.add_argument("--on-response", help="Path to Python module containing `on_response(method, params, result)`")
args = parser.parse_args()

TARGET_HOST = args.target_host
TARGET_PORT = args.target_port
PROXY_PORT = args.proxy_port

start_time = time.time()
log_file = open(args.logfile, "a") if args.logfile else None

method_map = {}
if args.method_map:
    for entry in args.method_map:
        if '=' in entry:
            orig, new = entry.split('=', 1)
            method_map[orig.strip()] = new.strip()

def log_event(label, message):
    elapsed_ms = int((time.time() - start_time) * 1000)
    timestamp = str(elapsed_ms).rjust(6, '0')
    line = f"[{timestamp}] {label} {message}"
    if not args.quiet or label == "SHELL":
        print(line)
    if log_file:
        print(line, file=log_file, flush=True)

# Load callbacks if specified
on_request = None
on_response = None

def load_callback(path, name):
    if not path:
        return None
    unique_name = f"callback_mod_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(unique_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name, None)

# Optimization: don't load the same module twice if paths match
if args.on_request and args.on_response and args.on_request == args.on_response:
    shared_module = load_callback(args.on_request, "shared")  # Just to load once
    on_request = getattr(shared_module, "on_request", None)
    on_response = getattr(shared_module, "on_response", None)
else:
    on_request = load_callback(args.on_request, "on_request")
    on_response = load_callback(args.on_response, "on_response")

# Shared task queue for XML-RPC calls
rpc_queue = queue.Queue()

url = f"http://{TARGET_HOST}:{TARGET_PORT}"
print(f"Starting XML-RPC proxy:")
print(f"  Listening on port {PROXY_PORT}")
print(f"  Forwarding to {url}")

class QuietRequestHandler(SimpleXMLRPCRequestHandler):
    def log_message(self, format, *args_inner):
        if not self.server.quiet_mode:
            super().log_message(format, *args_inner)

class ThreadingXMLRPCServer(ThreadingMixIn, BaseServer):
    pass

def enqueue_rpc_call(method, params, response_queue=None):
    rpc_queue.put((method, params, response_queue))

class ProxyHandler:
    def _dispatch(self, method, params):
        log_event("CALL", f"{method}({params})")

        if method in method_map:
            remap = method_map[method]
            if remap.upper() == "BLOCK":
                log_event("BLOCKED", f"{method} call blocked")
                return {'faultCode': 1, 'faultString': f"{method} is blocked by proxy"}
            else:
                log_event("REMAPPED", f"{method} -> {remap}")
                method = remap

        # Pre-dispatch callback
        if on_request:
            try:
                new_method, new_params = on_request(method, params)
                method = new_method or method
                params = new_params or params
                log_event("CALLBACK", f"on_request -> {method}({params})")
            except Exception as e:
                log_event("ERROR", f"on_request callback error: {e}")

        if method == "system.multicall":
            results = []
            for call in params[0]:
                try:
                    mname = call['methodName']
                    mparams = call.get('params', [])
                    log_event("MULTICALL", f"{mname}({mparams})")
                    response_q = queue.Queue()
                    enqueue_rpc_call(mname, mparams, response_q)
                    result = response_q.get()
                    if on_response:
                        try:
                            result = on_response(mname, mparams, result) or result
                            log_event("CALLBACK", f"on_response -> {mname} -> {result}")
                        except Exception as e:
                            log_event("ERROR", f"on_response callback error: {e}")
                    results.append([result])
                except Exception as e:
                    log_event("ERROR", f"{mname} failed: {e}")
                    results.append({'faultCode': 1, 'faultString': str(e)})
            return results

        try:
            response_q = queue.Queue()
            enqueue_rpc_call(method, params, response_q)
            result = response_q.get()
            if on_response:
                try:
                    result = on_response(method, params, result) or result
                    log_event("CALLBACK", f"on_response -> {method} -> {result}")
                except Exception as e:
                    log_event("ERROR", f"on_response callback error: {e}")
            log_event("RESULT", f"{method} -> {result}")
            return result
        except Exception as e:
            log_event("ERROR", f"{method} failed: {e}")
            return {'faultCode': 1, 'faultString': str(e)}

def rpc_dispatcher():
    target = xmlrpc.client.ServerProxy(url, allow_none=True)
    while True:
        method, params, response_q = rpc_queue.get()
        try:
            func = getattr(target, method)
            result = func(*params)
        except Exception as e:
            result = {'faultCode': 1, 'faultString': str(e)}
            log_event("ERROR", f"{method} failed: {e}")
        if response_q:
            response_q.put(result)

# Start the dispatcher thread
threading.Thread(target=rpc_dispatcher, daemon=True).start()

server = ThreadingXMLRPCServer(('', PROXY_PORT), requestHandler=QuietRequestHandler, allow_none=True)
server.quiet_mode = args.quiet
server.register_instance(ProxyHandler())
print(f"XML-RPC proxy running on port {PROXY_PORT}")

if args.interactive:
    def run_server():
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    interactive_url = f"http://localhost:{PROXY_PORT}"
    class NoKeepAliveTransport(xmlrpc.client.Transport):
        def request(self, host, handler, request_body, verbose=False):
            self._extra_headers = [("Connection", "close")]
            response = super().request(host, handler, request_body, verbose)
            if hasattr(self, "_connection") and isinstance(self._connection, dict):
                self._connection.pop(host, None)
            return response

    def call(method, *args):
        response_q = queue.Queue()
        enqueue_rpc_call(method, args, response_q)
        return response_q.get()

    namespace = {
        'call': call,
        'log': lambda m: log_event("SHELL", m),
        'quit': lambda: exit(),
        'exit': lambda: exit(),
    }
    log_event("SHELL", "Entering interactive mode (use 'call(\"method\", ...)')")
    try:
        code.interact(local=namespace)
    except KeyboardInterrupt:
        print("KeyboardInterrupt — exiting.")
        sys.exit()
else:
    server.serve_forever()

if log_file:
    log_file.close()
