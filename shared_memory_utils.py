# shared_memory_utils.py
# ---------------------------------------------------
# Shared memory interface for symbol-price array.
# Used by OrderBook (writer) and Strategy (reader).
# ---------------------------------------------------

import numpy as np
from multiprocessing import shared_memory

class SharedPriceBook:
    def __init__(self, symbols, name=None):
        """
        symbols: list of symbols (e.g., ["AAPL", "MSFT", "AMZN"])
        name: optional shared memory block name (if None, create new)
        """
        self.symbols = list(symbols)
        self.dtype = np.dtype([("symbol", "U8"), ("price", "f8")])
        self.size = len(symbols)

        if name is None:
            # Create a new shared memory block and initialize array
            self.shm = shared_memory.SharedMemory(create=True, size=self.size * self.dtype.itemsize)
            self.array = np.ndarray((self.size,), dtype=self.dtype, buffer=self.shm.buf)
            for i, sym in enumerate(symbols):
                self.array[i]["symbol"] = sym
                self.array[i]["price"] = np.nan
            print(f"[SharedPriceBook] Created new shared memory: {self.shm.name}")
        else:
            # Attach to an existing shared memory block
            self.shm = shared_memory.SharedMemory(name=name)
            self.array = np.ndarray((self.size,), dtype=self.dtype, buffer=self.shm.buf)
            print(f"[SharedPriceBook] Attached to shared memory: {name}")

    def update(self, symbol, price):
        """Update the price for a given symbol."""
        idx = self.symbols.index(symbol)
        self.array[idx]["price"] = float(price)

    def read(self, symbol):
        """Read the latest price for a given symbol."""
        idx = self.symbols.index(symbol)
        return float(self.array[idx]["price"])

    def snapshot(self):
        """Return a dict of {symbol: price} for all symbols."""
        return {row["symbol"]: float(row["price"]) for row in self.array}

    def close(self):
        """Detach from shared memory."""
        self.shm.close()

    def unlink(self):
        """Free shared memory (only call once, from the creator)."""
        self.shm.unlink()
