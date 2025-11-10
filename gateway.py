# gateway.py
import os, socket, threading, time, json, random

HOST = os.getenv("GATEWAY_HOST", "127.0.0.1")
PRICE_PORT = int(os.getenv("GATEWAY_PRICE_PORT", "5001"))
NEWS_PORT  = int(os.getenv("GATEWAY_NEWS_PORT",  "5002"))
MESSAGE_DELIMITER = os.getenv("MESSAGE_DELIMITER", "*").encode()
SYMS = os.getenv("SYMBOLS", "AAPL,MSFT,GOOG,AMZN").split(",")

def _listen(port, backlog=128):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # important on macOS
    try:
        s.bind((HOST, port))
    except OSError as e:
        # surface the port value for easier debugging
        raise RuntimeError(f"gateway bind failed on {HOST}:{port}: {e}") from e
    s.listen(backlog)
    return s

def _serve_prices():
    srv = _listen(PRICE_PORT)
    def handle(conn):
        with conn:
            prices = {sym: 100.0 for sym in SYMS}
            while True:
                sym = random.choice(SYMS)
                prices[sym] += random.uniform(-0.2, 0.2)
                msg = {"type":"price","sym":sym,"px":round(prices[sym],4),"ts":time.time()}
                conn.sendall(json.dumps(msg).encode() + MESSAGE_DELIMITER)
                time.sleep(0.01)
    while True:
        c, _ = srv.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()

def _serve_news():
    srv = _listen(NEWS_PORT)
    def handle(conn):
        with conn:
            while True:
                msg = {"type":"news","sentiment": random.randint(0,100), "ts": time.time()}
                conn.sendall(json.dumps(msg).encode() + MESSAGE_DELIMITER)
                time.sleep(0.2)
    while True:
        c, _ = srv.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()

def run_gateway():
    t1 = threading.Thread(target=_serve_prices, daemon=True)
    t2 = threading.Thread(target=_serve_news,   daemon=True)
    t1.start(); t2.start()
    t1.join(); t2.join()
