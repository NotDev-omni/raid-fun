"""
Pre-bind socket launcher for uvicorn.

uvicorn.run() runs lifespan BEFORE binding the port, creating a race condition
where something else grabs port 8000 in the ~7ms window.

Fix: bind the socket ourselves first, then hand it to uvicorn.Server.serve()
which accepts a pre-bound sockets list and skips the bind step entirely.
"""
import asyncio
import socket
import uvicorn

if __name__ == "__main__":
    HOST, PORT = "127.0.0.1", 8000

    # Grab the port NOW before lifespan runs
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    print(f"[run.py] Socket bound to {HOST}:{PORT} — starting server")

    config = uvicorn.Config(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve(sockets=[sock]))
