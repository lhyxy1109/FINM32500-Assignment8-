# tests/test_connectivity_gateway.py
import json
import socket
import time
import os

import pytest


DELIM = os.environ.get("MESSAGE_DELIMITER", "*").encode()


def recv_some(sock, timeout=2.0) -> bytes:
    sock.settimeout(timeout)
    chunks = []
    start = time.time()
    while time.time() - start < timeout:
        try:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
            if DELIM in data:
                break
        except BlockingIOError:
            time.sleep(0.01)
    return b"".join(chunks)


@pytest.mark.timeout(10)
def test_gateway_price_stream_delimited(gateway_proc, ports):
    """Gateway should accept a TCP connection on price port and send delimited messages."""
    with socket.create_connection((ports["HOST"], ports["PRICE_PORT"]), timeout=2) as s:
        data = recv_some(s, timeout=3.0)
    assert data, "no data received from price stream"
    # Must contain the delimiter and at least one message body
    assert DELIM in data, "price messages must be framed with delimiter"
    # Try JSON parse when possible (your gateway may send CSV; both are okay)
    sample = data.split(DELIM)[0]
    try:
        msg = json.loads(sample.decode())
        assert "type" in msg and msg["type"] in ("price", "tick")
        assert "sym" in msg or "symbol" in msg
        assert "px" in msg or "price" in msg
    except Exception:
        # fall back to CSV like "AAPL,172.53"
        text = sample.decode()
        parts = text.split(",")
        assert len(parts) == 2 and parts[0] and parts[1], f"unexpected price format: {text}"


@pytest.mark.timeout(10)
def test_gateway_news_stream_delimited(gateway_proc, ports):
    """Gateway should accept a TCP connection on news port and send delimited messages."""
    with socket.create_connection((ports["HOST"], ports["NEWS_PORT"]), timeout=2) as s:
        data = recv_some(s, timeout=3.0)
    assert data, "no data received from news stream"
    assert DELIM in data, "news messages must be framed with delimiter"
    # Try JSON parse: {"type":"news","sentiment": int}
    sample = data.split(DELIM)[0]
    try:
        msg = json.loads(sample.decode())
        assert msg.get("type") in ("news", "sentiment")
        sent = msg.get("sentiment", None)
        assert isinstance(sent, int) and 0 <= sent <= 100
    except Exception:
        # If not JSON, accept plain integer text
        val = int(sample.decode())
        assert 0 <= val <= 100
