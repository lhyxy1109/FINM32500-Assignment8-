# OrderManager.py
# ---------------------------------------------------
# Acts as a TCP server receiving Order objects from Strategy clients.
# Deserializes and logs orders, prints trade confirmations in real time.
# ---------------------------------------------------

import socket
import threading
import json
import time

HOST = "localhost"
ORDER_PORT = 7003
MESSAGE_DELIMITER = b"*"

class OrderManager:
    def __init__(self, host=HOST, port=ORDER_PORT):
        self.host = host
        self.port = port
        self.order_count = 0
        self._lock = threading.Lock()

    def handle_client(self, conn, addr):
        print(f"[OrderManager] Connected by {addr}")
        buffer = b""
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data
                parts = buffer.split(MESSAGE_DELIMITER)
                buffer = parts[-1]

                for part in parts[:-1]:
                    txt = part.decode(errors="ignore").strip()
                    if not txt:
                        continue
                    try:
                        order = json.loads(txt)
                        self.log_order(order)
                    except json.JSONDecodeError:
                        print("[OrderManager] Warning: malformed message ignored.")
                        continue
        except (ConnectionResetError, BrokenPipeError):
            print(f"[OrderManager] Client {addr} disconnected.")
        finally:
            conn.close()

    def log_order(self, order):
        """Log and print a trade confirmation."""
        with self._lock:
            self.order_count += 1
            oid = self.order_count

        side = order.get("side", "UNKNOWN")
        qty = order.get("qty", 0)
        sym = order.get("symbol", "???")
        px = order.get("price", float("nan"))
        t = time.strftime("%H:%M:%S", time.localtime(order.get("timestamp", time.time())))
        print(f"[OrderManager] Received Order {oid}: {side} {qty} {sym} @ {px:.2f} ({t})")

        # Optional: write to a simple log file
        with open("trades.log", "a") as f:
            f.write(json.dumps(order) + "\n")

    def run(self):
        """Start TCP server and listen for Strategy clients."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            print(f"[OrderManager] Listening on {self.host}:{self.port}")
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()


def main():
    manager = OrderManager()
    try:
        manager.run()
    except KeyboardInterrupt:
        print("\n[OrderManager] Shutting down.")

def run_ordermanager():
    main() 

if __name__ == "__main__":
    main()

