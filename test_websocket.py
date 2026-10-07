import asyncio
import websockets

async def test():
    uri = "ws://127.0.0.1:8000/ws/kds"
    async with websockets.connect(uri) as ws:
        # Wait for the initial data from the server
        initial_message = await ws.recv()
        print("Initial message:", initial_message)

        print("Waiting for refresh messages...")
        while True:
            msg = await ws.recv()
            print("Received:", msg)

asyncio.run(test())