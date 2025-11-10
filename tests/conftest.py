import os
import socket
import time
import contextlib
import random
import string
import multiprocessing as mp

import pytest
def find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def wait_for_port(host: str, port: int, timeout: float = 5.0) -> None:
    """Wait until a TCP port starts accepting connections or time out."""
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError as e:
            last_err = e
            time.sleep(0.05)
    raise TimeoutError(f"Port {host}:{port} not ready: {last_err}")

def rand_name(prefix="shm-") -> str:
    return prefix + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


# ---------- Global env / ports for the test run ----------
@pytest.fixture(scope="session")
def ports():
    """Allocate ephemeral ports for price/news/order servers."""
    return {
        "HOST": "127.0.0.1",
        "PRICE_PORT": find_free_port(),
        "NEWS_PORT": find_free_port(),
        "ORDER_PORT": find_free_port(),
    }

@pytest.fixture(autouse=True)
def _patch_env(ports, monkeypatch):
    # Standardize env that your app can read. Adjust if your code uses different names.
    monkeypatch.setenv("GATEWAY_HOST", ports["HOST"])
    monkeypatch.setenv("GATEWAY_PRICE_PORT", str(ports["PRICE_PORT"]))
    monkeypatch.setenv("GATEWAY_NEWS_PORT", str(ports["NEWS_PORT"]))
    monkeypatch.setenv("ORDERMANAGER_HOST", ports["HOST"])
    monkeypatch.setenv("ORDERMANAGER_PORT", str(ports["ORDER_PORT"]))
    # Shared memory region name (if your code lets Strategy/OrderBook attach by name)
    monkeypatch.setenv("PRICEBOOK_NAME", rand_name("pricebook-"))
    # Message delimiter default
    monkeypatch.setenv("MESSAGE_DELIMITER", "*")
    yield

@pytest.fixture
def gateway_proc(ports):
    """Start gateway.run_gateway() in a child process, if available."""
    try:
        import gateway  # your module
    except Exception as e:
        pytest.skip(f"gateway module not importable: {e}")

    run = getattr(gateway, "run_gateway", None)
    if run is None:
        pytest.skip("gateway.run_gateway not implemented")

    p = mp.Process(target=run, daemon=True)
    p.start()
    # Wait for both ports to open
    wait_for_port(ports["HOST"], ports["PRICE_PORT"])
    wait_for_port(ports["HOST"], ports["NEWS_PORT"])
    yield p
    if p.is_alive():
        p.terminate()
        p.join(timeout=2)


@pytest.fixture
def ordermanager_proc(ports):
    """Start order_manager.run_ordermanager() in a child process, if available."""
    try:
        import order_manager  # your module
    except Exception as e:
        pytest.skip(f"order_manager module not importable: {e}")

    run = getattr(order_manager, "run_ordermanager", None)
    if run is None:
        pytest.skip("order_manager.run_ordermanager not implemented")

    p = mp.Process(target=run, daemon=True)
    p.start()
    wait_for_port(ports["HOST"], ports["ORDER_PORT"])
    yield p
    if p.is_alive():
        p.terminate()
        p.join(timeout=2)