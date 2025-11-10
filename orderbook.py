# orderbook.py
# --------------------------------------------
# OrderBook: connects to Gateway (7001) and updates shared memory.
# Stores latest prices in shared memory for Strategy to read.
# Uses Lock for atomic writes and auto-reconnect on failure.
# --------------------------------------------

import socket
import time
import numpy as np
from multiprocessing import shared_memory, Lock
import traceback

GATEWAY_HOST = "localhost"
GATEWAY_PORT = 7001
SYMBOLS = ["AAPL", "MSFT", "AMZN"]
MESSAGE_DELIMITER = b"*"

def connect_to_gateway():
    """Try to connect to Gateway and return socket."""
    while True:
        try:
            sock = socket.create_connection((GATEWAY_HOST, GATEWAY_PORT))
            print(f"[OrderBook] Connected to Gateway at {GATEWAY_HOST}:{GATEWAY_PORT}")
            sock.settimeout(5)
            return sock
        except (ConnectionRefusedError, OSError):
            print("[OrderBook] Gateway unavailable, retrying in 3s...")
            time.sleep(3)

def update_prices(buffer: bytes, shared_array, lock):
    text = buffer.decode(errors="ignore")
    for chunk in text.split(MESSAGE_DELIMITER.decode()):
        if not chunk.strip():
            continue
        try:
            sym, val = chunk.split(",")
            val = float(val)
            idx = np.where(shared_array["symbol"] == sym)[0]
            if len(idx) == 1:
                with lock:
                    shared_array[idx[0]]["price"] = val
        except Exception:
            continue

def main():
    dtype = np.dtype([("symbol", "U8"), ("price", "f8")])
    data = np.zeros(len(SYMBOLS), dtype=dtype)
    data["symbol"] = SYMBOLS

    shm = shared_memory.SharedMemory(create=True, size=data.nbytes)
    shared_array = np.ndarray(data.shape, dtype=data.dtype, buffer=shm.buf)
    shared_array[:] = data[:]
    lock = Lock()

    print(f"[OrderBook] Shared memory created: name={shm.name}")
    print(f"[OrderBook] Initial data:\n{shared_array}\n")

    sock = connect_to_gateway()
    buffer = b""
    try:
        while True:
            try:
                chunk = sock.recv(1024)
                if not chunk:
                    raise ConnectionResetError
                buffer += chunk
                parts = buffer.split(MESSAGE_DELIMITER)
                buffer = parts[-1]
                for part in parts[:-1]:
                    update_prices(part + MESSAGE_DELIMITER, shared_array, lock)
                with lock:
                    snapshot = shared_array.copy()
                print("[OrderBook]", ", ".join(f"{r['symbol']}={r['price']:.2f}" for r in snapshot))
            except (ConnectionResetError, BrokenPipeError, TimeoutError):
                print("[OrderBook] Connection lost. Reconnecting...")
                sock.close()
                time.sleep(3)
                sock = connect_to_gateway()
    except KeyboardInterrupt:
        print("\n[OrderBook] Shutting down.")
    finally:
        shm.close()
        shm.unlink()

def run_orderbook():
    main()

    
if __name__ == "__main__":
    main()
