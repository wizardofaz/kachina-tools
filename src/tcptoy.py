import asyncio

HOST = '127.0.0.1'  # Replace with server address
PORT = 1100        # Replace with server port

async def handle_input(writer):
    loop = asyncio.get_event_loop()
    while True:
        message = await loop.run_in_executor(None, input, "You: ")
        if message.lower() in ('exit', 'quit'):
            print("Closing connection.")
            writer.close()
            await writer.wait_closed()
            break
        writer.write((message + '\r\n').encode())
        await writer.drain()

async def handle_receive(reader):
    try:
        while True:
            data = await reader.readline()
            if not data:
                print("Server closed the connection.")
                break
            print("Server:", data.decode().rstrip())
    except asyncio.CancelledError:
        pass  # Allow cancellation without error

async def main():
    print(f"Connecting to {HOST}:{PORT}...")
    reader, writer = await asyncio.open_connection(HOST, PORT)
    print(f"Connected to {HOST}:{PORT}")

    receive_task = asyncio.create_task(handle_receive(reader))
    input_task = asyncio.create_task(handle_input(writer))

    # Wait for either task to finish (typically input exits)
    done, pending = await asyncio.wait(
        [receive_task, input_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()

asyncio.run(main())

