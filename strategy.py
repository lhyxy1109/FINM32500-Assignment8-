# strategy.py
# ---------------------------------------------------
# Reads latest prices from shared memory.
# Connects to Gateway's news stream to receive sentiment.
# Generates trading signals (MA crossover + news thresholds).
# Currently: only prints order objects (no socket send yet).
# ---------------------------------------------------

import argparse
import json
import math
import socket
import threading
import time
from collections import deque

import numpy as np
from multiprocessing import shared_memory

# --- Config ---
NEWS_HOST = "localhost"
NEWS_PORT = 7002
ORDER_MANAGER_HOST = "localhost"
ORDER_MANAGER_PORT = 7003
MESSAGE_DELIMITER = b"*"

SHORT_WINDOW = 5
LONG_WINDOW = 20
PRICE_POLL_INTERVAL = 0.2

BULLISH_THRESHOLD = 60
BEARISH_THRESHOLD = 40
ORDER_QTY = 10


def parse_args():
    p = argparse.ArgumentParser(description="Strategy: signal generator (no order send)")
    p.add_argument("--shm-name", required=True, help="SharedMemory name printed by OrderBook")
    p.add_argument("--symbols", nargs="+", default=["AAPL", "MSFT", "AMZN"], help="Symbols order in shared memory")
    return p.parse_args()


class NewsReceiver(threading.Thread):
    """Background thread to receive sentiment from Gateway (7002)."""

    def __init__(self, host, port):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self._lock = threading.Lock()
        self._latest_sentiment = 50
        self._buffer = b""
        self._stop = False

    def get_sentiment(self):
        with self._lock:
            return self._latest_sentiment

    def stop(self):
        self._stop = True

    def _set_sentiment(self, val: int):
        with self._lock:
            self._latest_sentiment = val

    def run(self):
        while not self._stop:
            try:
                sock = socket.create_connection((self.host, self.port), timeout=5)
                sock.settimeout(5)
                print(f"[Strategy] Connected to news stream at {self.host}:{self.port}")
                self._buffer = b""
                while not self._stop:
                    chunk = sock.recv(1024)
                    if not chunk:
                        raise ConnectionResetError
                    self._buffer += chunk
                    parts = self._buffer.split(MESSAGE_DELIMITER)
                    self._buffer = parts[-1]
                    for part in parts[:-1]:
                        txt = part.decode(errors="ignore").strip()
                        if not txt:
                            continue
                        try:
                            left, right = txt.split(",", 1)
                            score = int(right)
                            score = max(0, min(100, score))
                            self._set_sentiment(score)
                        except Exception:
                            continue
            except (ConnectionRefusedError, TimeoutError, OSError, ConnectionResetError):
                print("[Strategy] News stream unavailable. Reconnecting in 2s...")
                time.sleep(2)
            except Exception as e:
                print("[Strategy] News recv error:", e)
                time.sleep(1)


def compute_ma_signal(history: deque):
    """Return 'BUY' if short MA > long MA, else 'SELL'. Equal ignored."""
    if len(history) < LONG_WINDOW:
        return None
    arr = np.fromiter(history, dtype=float)
    s_ma = arr[-SHORT_WINDOW:].mean()
    l_ma = arr[-LONG_WINDOW:].mean()
    return "BUY" if s_ma > l_ma else "SELL"


def news_signal_from(score: int):
    """Map sentiment integer to signal."""
    if score > BULLISH_THRESHOLD:
        return "BUY"
    if score < BEARISH_THRESHOLD:
        return "SELL"
    return "HOLD"

def connect_order_manager():
    """Try to connect to OrderManager, retry on failure."""
    while True:
        try:
            sock = socket.create_connection((ORDER_MANAGER_HOST, ORDER_MANAGER_PORT))
            print(f"[Strategy] Connected to OrderManager at {ORDER_MANAGER_HOST}:{ORDER_MANAGER_PORT}")
            sock.settimeout(5)
            return sock
        except (ConnectionRefusedError, OSError):
            print("[Strategy] OrderManager unavailable, retrying in 3s...")
            time.sleep(3)


def send_order(sock, ord_obj):
    """Send serialized order over TCP with delimiter."""
    msg = json.dumps(ord_obj).encode() + MESSAGE_DELIMITER
    sock.sendall(msg)


def main():
    args = parse_args()
    symbols = args.symbols

    dtype = np.dtype([("symbol", "U8"), ("price", "f8")])
    shm = shared_memory.SharedMemory(name=args.shm_name)
    shared_array = np.ndarray((len(symbols),), dtype=dtype, buffer=shm.buf)

    history = {sym: deque(maxlen=LONG_WINDOW) for sym in symbols}
    position = {sym: None for sym in symbols}

    news = NewsReceiver(NEWS_HOST, NEWS_PORT)
    news.start()

    # 🟡 Temporarily disable order sending: not connecting to OrderManager, just printing results
    order_sock = connect_order_manager()

    try:
        last_print = 0.0
        while True:
            # double snapshot
            snap1 = np.copy(shared_array)
            time.sleep(0.001)
            snap2 = np.copy(shared_array)
            snap = snap1 if np.array_equal(snap1, snap2) else np.copy(shared_array)

            sym_to_price = {}
            for rec in snap:
                sym = str(rec["symbol"])
                px = float(rec["price"])
                history[sym].append(px)
                sym_to_price[sym] = px

            sentiment = news.get_sentiment()
            nsig = news_signal_from(sentiment)

            for sym in symbols:
                psig = compute_ma_signal(history[sym])
                if psig is None:
                    continue

                action = None
                if nsig == "BUY" and psig == "BUY":
                    action = "BUY"
                elif nsig == "SELL" and psig == "SELL":
                    action = "SELL"

                if action == "BUY" and position[sym] != "LONG":
                    ord_obj = {
                        "type": "order",
                        "symbol": sym,
                        "side": "BUY",
                        "qty": ORDER_QTY,
                        "price": float(sym_to_price.get(sym, math.nan)),
                        "sentiment": sentiment,
                        "timestamp": time.time(),
                    }
                    # 🟢 Temporarily print order object only (not sent)
                    
                    try:
                        send_order(order_sock, ord_obj)
                        print(f"[Strategy] Sent BUY order: {ord_obj}")
                        position[sym] = "LONG"
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        print("[Strategy] Lost connection to OrderManager. Reconnecting...")
                        order_sock.close()
                        order_sock = connect_order_manager()
                    

                elif action == "SELL" and position[sym] != "SHORT":
                    ord_obj = {
                        "type": "order",
                        "symbol": sym,
                        "side": "SELL",
                        "qty": ORDER_QTY,
                        "price": float(sym_to_price.get(sym, math.nan)),
                        "sentiment": sentiment,
                        "timestamp": time.time(),
                    }
                    # 🟢 Temporarily print order object only (not sent)
                    try:
                        send_order(order_sock, ord_obj)
                        print(f"[Strategy] Sent SELL order: {ord_obj}")
                        position[sym] = "SHORT"
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        print("[Strategy] Lost connection to OrderManager. Reconnecting...")
                        order_sock.close()
                        order_sock = connect_order_manager()

            now = time.time()
            if now - last_print > 2.0:
                last_print = now
                desc = ", ".join(f"{s}={sym_to_price.get(s, float('nan')):.2f}" for s in symbols)
                print(f"[Strategy] sentiment={sentiment} | {desc}")

            time.sleep(PRICE_POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n[Strategy] Shutting down.")
    finally:
        news.stop()
        shm.close()
        try:
            order_sock.close()
        except Exception:
            pass

def run_strategy():
    main()

if __name__ == "__main__":
    main()
