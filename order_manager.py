# order_manager.py
import os, socket, threading, json

HOST = os.getenv("ORDERMANAGER_HOST", "127.0.0.1")
PORT = int(os.getenv("ORDERMANAGER_PORT", "5003"))
MESSAGE_DELIMITER = os.getenv("MESSAGE_DELIMITER", "*").encode()

def _listen():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(128)
    return s

def _handle(conn, addr):
    buf = b""
    with conn:
        while True:
            data = conn.recv(4096)
            if not data: break
            buf += data
            parts = buf.split(MESSAGE_DELIMITER)
            for raw in parts[:-1]:
                if not raw: continue
                try:
                    o = json.loads(raw.decode())
                    print(f"Received Order {o.get('id','?')}: {o.get('side','?')} "
                          f"{o.get('qty','?')} {o.get('sym','?')} @ {o.get('px','?')}", flush=True)
                except Exception:
                    # ignore garbage frames in tests
                    pass
            buf = parts[-1]

def run_ordermanager():
    srv = _listen()
    while True:
        c, addr = srv.accept()
        threading.Thread(target=_handle, args=(c, addr), daemon=True).start()
