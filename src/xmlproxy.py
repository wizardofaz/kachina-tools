from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import xmlrpc.client
import signal
import sys

REAL_SERVER_URL = "http://localhost:8000"  # Change to your fldigi server
DEBUG = True

class ProxyHandler:
    def __init__(self):
        self.real_server = xmlrpc.client.ServerProxy(REAL_SERVER_URL, allow_none=True)

    def _dispatch(self, method, params):
        if DEBUG:
            print(f"[KCAT → Proxy] Method: {method}, Params: {params}")

        try:
            if method == "system.multicall":
                calls = params[0]  # list of dicts
                real_response = self.real_server.system.multicall(calls)
            else:
                real_method = getattr(self.real_server, method)
                real_response = real_method(*params)

            if DEBUG:
                print(f"[Proxy → KCAT] Response: {real_response}")
            return real_response

        except Exception as e:
            print(f"[ERROR] Proxy failed on method {method}: {e}")
            return f"[Proxy Error] {str(e)}"

def main():
    host = "localhost"
    port = 7362  # Where kcat connects

    server = SimpleXMLRPCServer(
        (host, port),
        requestHandler=SimpleXMLRPCRequestHandler,
        allow_none=True,
        logRequests=False
    )
    server.register_instance(ProxyHandler())

    print(f"XML-RPC proxy listening on {host}:{port} and forwarding to {REAL_SERVER_URL}")
    print("Ctrl+C to stop.")

    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))

    server.serve_forever()

if __name__ == "__main__":
    main()
