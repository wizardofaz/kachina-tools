# xmlrpc_proxy_logger.py

# Copyright 2025, Bill Bennett, N7DZ
#
# Originally built as a debugging tool to sit between kcat and 
# fldigi to examine rpcxml interactions between those two. 
# Hopefully useful more generally. 
# 
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# The software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with fldigi.  If not, see <http:#www.gnu.org/licenses/>.
#
# This code was developed with support from Jules, my ChatGPT-based coding assistant. 
#
# Please report all bugs and problems to n7dz@arrl.net.

import argparse
import time
import threading
import sys
from xmlrpc.server import SimpleXMLRPCRequestHandler
from xmlrpc.server import SimpleXMLRPCServer as BaseServer
from socketserver import ThreadingMixIn
import xmlrpc.client

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

url = f"http://{TARGET_HOST}:{TARGET_PORT}"
print(f"Starting XML-RPC proxy:")
print(f"  Listening on port {PROXY_PORT}")
print(f"  Forwarding to {url}")

target = xmlrpc.client.ServerProxy(url, allow_none=True)

if args.list_methods:
    try:
        methods = target.system.listMethods()
        print("\nAvailable XML-RPC methods from target:")
        for m in methods:
            print(f"  {m}")
            if args.verbose_methods:
                try:
                    sig = target.system.methodSignature(m)
                    print(f"    Signature: {sig}")
                except Exception as e:
                    print(f"    Signature: unavailable ({e})")
                try:
                    help_text = target.system.methodHelp(m)
                    print(f"    Help: {help_text.strip() or 'No help available.'}")
                except Exception as e:
                    print(f"    Help: unavailable ({e})")
        print("\n--- End of method list ---\n")
    except Exception as e:
        print(f"Failed to retrieve method list: {e}")

class QuietRequestHandler(SimpleXMLRPCRequestHandler):
    def log_message(self, format, *args_inner):
        if not self.server.quiet_mode:
            super().log_message(format, *args_inner)

class ThreadingXMLRPCServer(ThreadingMixIn, BaseServer):
    pass

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

        if method == "system.multicall":
            results = []
            for call in params[0]:
                try:
                    mname = call['methodName']
                    mparams = call.get('params', [])
                    log_event("MULTICALL", f"{mname}({mparams})")
                    func = getattr(target, mname)
                    result = func(*mparams)
                    log_event("RESULT", f"{mname} -> {result}")
                    results.append([result])
                except Exception as e:
                    log_event("ERROR", f"{mname} failed: {e}")
                    results.append({'faultCode': 1, 'faultString': str(e)})
            return results

        try:
            func = getattr(target, method)
            result = func(*params)
            log_event("RESULT", f"{method} -> {result}")
            return result
        except Exception as e:
            log_event("ERROR", f"{method} failed: {e}")
            return {'faultCode': 1, 'faultString': str(e)}

server = ThreadingXMLRPCServer(('', PROXY_PORT), requestHandler=QuietRequestHandler, allow_none=True)
server.quiet_mode = args.quiet
server.register_instance(ProxyHandler())
print(f"XML-RPC proxy running on port {PROXY_PORT}")

if args.interactive:
    def run_server():
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    import code
    interactive_url = f"http://localhost:{PROXY_PORT}"
    class NoKeepAliveTransport(xmlrpc.client.Transport):
        def request(self, host, handler, request_body, verbose=False):
            self._extra_headers = [("Connection", "close")]
            response = super().request(host, handler, request_body, verbose)
            if hasattr(self, "_connection") and isinstance(self._connection, dict):
                self._connection.pop(host, None)
            return response

    def call(method, *args):
        transport = NoKeepAliveTransport()
        with xmlrpc.client.ServerProxy(interactive_url, allow_none=True, transport=transport) as proxy:
            for part in method.split('.'):
                proxy = getattr(proxy, part)
            result = proxy(*args)
            # if isinstance(result, dict) and result.get('faultString') == 'Request-sent':
#     log_event("RETRY", f"Retrying {method} due to fault response: {result}")
#     with xmlrpc.client.ServerProxy(interactive_url, allow_none=True, transport=transport) as retry_proxy:
#         for part in method.split('.'):
#             retry_proxy = getattr(retry_proxy, part)
#         return retry_proxy(*args)
            return result

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
