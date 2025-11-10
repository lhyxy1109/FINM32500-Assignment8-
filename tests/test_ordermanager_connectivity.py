# tests/test_ordermanager_connectivity.py
import os
import json
import socket
import time

import pytest

DELIM = os.environ.get("MESSAGE_DELIMITER", "*").encode()


@pytest.mark.timeout(10)
def test_ordermanager_accepts_orders(ordermanager_proc, ports):
    """OrderManager should accept a TCP connection and read framed orders without closing."""
    with socket.create_connection((ports["HOST"], ports["ORDER_PORT"]), timeout=2) as s:
        order1 = {"type": "order", "id": 1, "side": "BUY", "sym": "AAPL", "qty": 10, "px": 173.2}
        order2 = {"type": "order", "id": 2, "side": "SELL", "sym": "MSFT", "qty": 5, "px": 325.4}
        payload = json.dumps(order1).encode() + DELIM + json.dumps(order2).encode() + DELIM
        s.sendall(payload)
        # Give the server a moment to process. We expect the connection to stay open at least briefly.
        time.sleep(0.25)
        # If server closed immediately due to parse errors, the next send will raise.
        s.sendall(DELIM)  # harmless delimiter ping
