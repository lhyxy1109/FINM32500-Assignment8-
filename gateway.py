# gateway.py
# --------------------------------------------
# Gateway: acts as server broadcasting prices (GBM) and news sentiment.
# Two TCP servers:
#   - 7001: price stream
#   - 7002: sentiment stream
# --------------------------------------------

import socket
import threading
import time
import random
import math

HOST = "localhost"
PRICE_PORT = 7001
NEWS_PORT = 7002
MESSAGE_DELIMITER = b"*"
PRICE_UPDATE_INTERVAL = 0.1

SYMBOLS = ["AAPL", "MSFT", "AMZN"]

# GBM parameters
MU = 0.0001
SIGMA = 0.01
DT = PRICE_UPDATE_INTERVAL

def handle_price_client(conn, addr, prices):
    """Send GBM-based prices continuously."""
    print(f"[PRICE] Client connected from {addr}")
    try:
        while True:
            for sym in SYMBOLS:
                z = random.gauss(0, 1)
                drift = (MU - 0.5 * SIGMA**2) * DT
                diffusion = SIGMA * (DT**0.5) * z
                prices[sym] *= math.exp(drift + diffusion)

            msg = b"".join(
                f"{sym},{prices[sym]:.2f}".encode() + MESSAGE_DELIMITER
                for sym in SYMBOLS
            )
            conn.sendall(msg)
            time.sleep(PRICE_UPDATE_INTERVAL)
    except (BrokenPipeError, ConnectionResetError):
        print(f"[PRICE] Client {addr} disconnected.")
    finally:
        conn.close()

def price_server():
    prices = {sym: random.uniform(100, 300) for sym in SYMBOLS}
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PRICE_PORT))
        s.listen()
        print(f"[PRICE] Server started on port {PRICE_PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_price_client, args=(conn, addr, prices), daemon=True).start()

def handle_news_client(conn, addr):
    print(f"[NEWS] Client connected from {addr}")
    try:
        while True:
            sentiment = random.randint(0, 100)
            msg = f"NEWS,{sentiment}".encode() + MESSAGE_DELIMITER
            conn.sendall(msg)
            time.sleep(0.5)
    except (BrokenPipeError, ConnectionResetError):
        print(f"[NEWS] Client {addr} disconnected.")
    finally:
        conn.close()

def news_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, NEWS_PORT))
        s.listen()
        print(f"[NEWS] Server started on port {NEWS_PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_news_client, args=(conn, addr), daemon=True).start()

def main():
    """Run both price and news servers concurrently."""
    threading.Thread(target=price_server, daemon=True).start()
    threading.Thread(target=news_server, daemon=True).start()
    print("[Gateway] Running both servers.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Gateway] Shutting down.")
        
def run_gateway():
    main()

if __name__ == "__main__":
    main()
