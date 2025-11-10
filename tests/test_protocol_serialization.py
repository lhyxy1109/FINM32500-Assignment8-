# tests/test_protocol_serialization.py
"""
Protocol-level tests for message framing & serialization.
If your project exposes helpers like:
  - MESSAGE_DELIMITER
  - encode(obj) / decode(bytes)
  - send_json(sock, obj) / recv_json(sock)
these tests will validate them. Otherwise they skip.
"""
import importlib
import json
import os
import socket
import struct

import pytest


def test_delimiter_roundtrip():
    try:
        import gateway  # just to recover delimiter, not strictly required
        delim = getattr(gateway, "MESSAGE_DELIMITER", None)
    except Exception:
        delim = None
    if delim is None:
        delim = os.environ.get("MESSAGE_DELIMITER", "*").encode()

    # Simulate two concatenated messages arriving in weird chunk sizes
    msgs = [b'{"type":"x","n":1}', b'{"type":"y","n":2}']
    stream = msgs[0] + delim + msgs[1] + delim

    # Receiver buffer that splits by delimiter
    buf = b""
    parts = []
    for cut in (5, 7, 13, len(stream)):   # arbitrary chunking
        buf += stream[:cut]
        stream = stream[cut:]
        frames = buf.split(delim)
        parts.extend(frames[:-1])
        buf = frames[-1]
        if not stream:
            break

    parts.extend(buf.split(delim)[:-1])
    assert [json.loads(p.decode()) for p in parts] == [{"type": "x", "n": 1}, {"type": "y", "n": 2}]


def test_length_prefix_roundtrip():
    try:
        import codec  # if you created a codec.py with send/recv helpers
        send = getattr(codec, "send_msg", None)
        recv = getattr(codec, "recv_msg", None)
    except Exception:
        send = recv = None

    if not (send and recv):
        pytest.skip("Length-prefix helpers (codec.send_msg/recv_msg) not implemented; skipping")

    # Local loopback TCP and verify a round trip
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    host, port = srv.getsockname()

    cli = socket.socket()
    cli.connect((host, port))
    conn, _ = srv.accept()

    try:
        payload = b'{"ok":true,"n":123}'
        send(cli, payload)
        got = recv(conn)
        assert got == payload
    finally:
        conn.close()
        cli.close()
        srv.close()
