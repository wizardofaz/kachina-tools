from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
from collections import defaultdict
import signal
import sys

# Store method calls and their arguments
method_log = defaultdict(list)

class GenericHandler:
    def _dispatch(self, method, params):
        print(f"Received XML-RPC call: method='{method}', params={params}")
        if params not in method_log[method]:
            method_log[method].append(params)
        return f"Received method '{method}' with params {params}"

def print_summary():
    print("\n--- XML-RPC Method Call Summary ---")
    for method, args_list in method_log.items():
        print(f"\nMethod: {method}")
        for i, args in enumerate(args_list, start=1):
            print(f"  [{i}] args: {args}")
    print("\nShutting down server.")
    sys.exit(0)

def main():
    host = "localhost"
    port = 7362

    server = SimpleXMLRPCServer(
        (host, port),
        requestHandler=SimpleXMLRPCRequestHandler,
        allow_none=True,
        logRequests=True
    )
    server.register_instance(GenericHandler())

    print(f"Generic XML-RPC server listening on {host}:{port}")
    print("Press Ctrl+C to stop and see a summary of method calls.")

    # Gracefully handle Ctrl+C
    def signal_handler(sig, frame):
        print_summary()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print_summary()

if __name__ == "__main__":
    main()
