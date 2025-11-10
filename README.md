# FINM 32500 – Assignment 8
## Mini Trading System (IPC with TCP + Shared Memory)

This repository implements a tiny multi-process trading stack to practice **Inter-Process Communication (IPC)**, **message framing**, and **shared-memory state**.

- **Gateway** streams random-walk **prices** and **news sentiment** over TCP.
- **OrderBook** consumes prices and writes the latest state into **shared memory**.
- **Strategy** reads prices from shared memory, reads news via TCP, makes a decision, and sends **orders** via TCP.
- **OrderManager** accepts and logs orders.

> The repo also includes a **pytest** suite for connectivity and correctness.


---

## Architecture

```mermaid
flowchart LR
  G[Gateway
(Price & News TCP servers)] -->|TCP: prices| OB[OrderBook
(writer)]
  G -->|TCP: news| ST[Strategy]
  OB -->|SharedMemory| ST
  ST -->|TCP: orders| OM[OrderManager
(server)]
```
> **IPC choices:** TCP sockets for *messages*, POSIX shared memory for *state* (latest prices).  
> **Framing:** Delimiter by default (e.g., `*`), optional length-prefix helpers in `codec.py`.  
> **Serialization:** JSON (default). MessagePack supported if you add it.

### Dataflow (at a glance)

1. **Gateway → OrderBook** (TCP, price ticks) → **OrderBook** writes latest prices to shared memory.  
2. **Gateway → Strategy** (TCP, news/sentiment).  
3. **Strategy** reads current prices from shared memory + combines with news → emits **orders**.  
4. **Strategy → OrderManager** (TCP, framed JSON order messages).


---

## Modules (quick tour)

- `gateway.py` – Two TCP servers:
  - **Price server** on `$GATEWAY_PRICE_PORT`
  - **News server** on `$GATEWAY_NEWS_PORT`
  - Emits **JSON** + delimiter (default `*`), configurable via env.
- `shared_memory_utils.py` – `SharedPriceBook` (creates-or-attaches) with a simple float array for prices.
- `order_manager.py` – TCP order server reading **framed JSON** orders.
- `codec.py` – Optional **length-prefix** helpers (`send_msg`/`recv_msg`) for binary-robust framing.
- `strategy.py` – (Reference helper functions for tests) simple signal rules; expand as you implement your full strategy.
- `tests/` – Pytest suite for **connectivity** and **correctness**.

> All servers honor `SO_REUSEADDR` and read **ports/host** from env variables so tests can allocate ephemeral ports.


---

## Environment Variables

| Variable | Default | Used by | Notes |
|---|---|---|---|
| `GATEWAY_HOST` | `127.0.0.1` | gateway | Bind host for price/news servers |
| `GATEWAY_PRICE_PORT` | `5001` | gateway | Price TCP port |
| `GATEWAY_NEWS_PORT` | `5002` | gateway | News TCP port |
| `ORDERMANAGER_HOST` | `127.0.0.1` | order_manager | Bind host for order server |
| `ORDERMANAGER_PORT` | `5003` | order_manager | Orders TCP port |
| `PRICEBOOK_NAME` | `pricebook` | shared_memory_utils | Name of shared memory region |
| `MESSAGE_DELIMITER` | `*` | gateway, order_manager | Byte used for delimiter framing |
| `SYMBOLS` | `AAPL,MSFT,GOOG,AMZN` | gateway | Symbols for price stream |

> Tests set these automatically. For manual runs, you can export them yourself.


---

## Quick Start (manual run)

Create and activate a virtual environment, then install dev dependencies (optional but recommended):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install pytest pytest-timeout
```

### 1) Start the Order Manager (orders TCP server)

```bash
export ORDERMANAGER_HOST=127.0.0.1
export ORDERMANAGER_PORT=5003
python order_manager.py
```
You should see it start listening. It logs any orders it receives.

### 2) Start the Gateway (price + news servers)

Open a new terminal:

```bash
export GATEWAY_HOST=127.0.0.1
export GATEWAY_PRICE_PORT=5001
export GATEWAY_NEWS_PORT=5002
export MESSAGE_DELIMITER='*'
export SYMBOLS="AAPL,MSFT,GOOG,AMZN"
python gateway.py
```

### 3) (If implemented) Start OrderBook and Strategy

If you have your own `order_book.py` and full `strategy.py` runners, start them next, for example:

```bash
# OrderBook consumes Gateway price TCP and writes shared memory
python order_book.py

# Strategy consumes news TCP + shared memory, sends orders to OrderManager
python strategy.py
```

> Order of startup that minimizes retries: **OrderManager → Gateway → OrderBook → Strategy**.  
> But each client should reconnect on failure (as your assignment likely requires).


---

## Protocols

### Delimiter framing (default)

Messages end with a special byte, e.g. `*` (config via `MESSAGE_DELIMITER`). Example price tick:

```json
{"type":"price","sym":"AAPL","px":172.53,"ts":1699999999.123}*
```

### Length-prefix framing (optional / more robust)

Send a 4-byte big-endian length, then the payload. See `codec.py`:

```python
from codec import send_msg, recv_msg
send_msg(sock, b'{"type":"order","id":1}')
payload = recv_msg(sock)
```

### Serialization

- **JSON** is the default (human-readable, cross-language).  
- **MessagePack** can be added for compact binary encoding.  
- **Pickle** should be used only between trusted Python processes (security concern).


---

## Running the Tests

Install pytest and (optionally) the timeout plugin:

```bash
pip install pytest pytest-timeout
pytest -q
```

What the suite covers:

- **Connectivity:** Gateway price/news servers accept connections and emit **framed** messages; OrderManager accepts framed orders.
- **Shared Memory:** `SharedPriceBook` creates-or-attaches and returns the latest value correctly.
- **Protocol:** delimiter split correctness; optional **length-prefix** roundtrip if `codec.py` exists.
- **Strategy (optional):** helper functions if present (`price_signal`, `news_signal`, `combine_signals`, or `generate_trade_decision`).


---

## Troubleshooting

- **OSError: [Errno 48] Address already in use (macOS)**  
  A previous run is still bound or in `TIME_WAIT`. Either wait ~60s, kill the process, or use `lsof -nP -iTCP:<port> | grep LISTEN` to find and kill. We already set `SO_REUSEADDR` to reduce this.

- **TimeoutError: Port not ready**  
  Ensure you exported the env vars and started the server (OrderManager or Gateway) *before* the client. The tests handle this by waiting for the port to open.

- **SharedMemory FileNotFoundError**  
  The book is now “create-if-missing”. If you explicitly attach to a name, create it first. Clean up with `.close()` and `.unlink()` when done.

- **pytest timeout warnings**  
  Install the plugin `pytest-timeout` or add a `pytest.ini` to register the marker.

Example `pytest.ini`:
```ini
[pytest]
markers =
    timeout: per-test timeout marker
```


---

## Notes & Next Steps

- You can extend the shared-memory dtype to include `timestamp` and a `version` counter (seqlock pattern) to guarantee **lock-free consistent reads**.
- For higher concurrency on servers, consider `selectors`/`asyncio` instead of per-connection threads.
- Add structured **JSON logs** for easier perf tracing (tick → decision → order latency).


---

## Credits

Built for **FINM 32500 – Assignment 8** as a minimal, testable reference of IPC patterns: **TCP + Shared Memory + Framing + Serialization**.
