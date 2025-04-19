# xmlrpc_proxy_logger.py
import argparse
import time
from xmlrpc.server import SimpleXMLRPCServer
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
args = parser.parse_args()

TARGET_HOST = args.target_host
TARGET_PORT = args.target_port
PROXY_PORT = args.proxy_port

start_time = time.time()
log_file = open(args.logfile, "a") if args.logfile else None

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

class ProxyHandler:
    def _dispatch(self, method, params):
        log_event("CALL", f"{method}({params})")

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

with SimpleXMLRPCServer(('', PROXY_PORT), allow_none=True) as server:
    server.register_instance(ProxyHandler())
    print(f"XML-RPC proxy running on port {PROXY_PORT}")

    if args.interactive:
        import code
        namespace = {'proxy': target, 'log': lambda m: log_event("SHELL", m)}
        log_event("SHELL", "Entering interactive mode (use 'proxy.method(...)')")
        code.interact(local=namespace)

    server.serve_forever()

if log_file:
    log_file.close()
