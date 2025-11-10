# shared_memory_utils.py
import os, time
import numpy as np
from multiprocessing import shared_memory
from threading import Lock

class SharedPriceBook:
    """
    Minimal shared price table:
      - symbols: list[str]
      - array dtype: float64 prices only (expand later if you like)
    Creates the region if it doesn't exist; otherwise attaches.
    """
    def __init__(self, symbols, name=None, create=None):
        self.symbols = list(symbols)
        self.index = {s: i for i, s in enumerate(self.symbols)}
        self.name = name or os.getenv("PRICEBOOK_NAME", "pricebook")
        self.dtype = np.float64
        self.n = len(self.symbols)
        self._lock = Lock()

        nbytes = self.n * np.dtype(self.dtype).itemsize

        # auto-create if missing
        try:
            self.shm = shared_memory.SharedMemory(name=self.name, create=False)
        except FileNotFoundError:
            self.shm = shared_memory.SharedMemory(name=self.name, create=True, size=nbytes)

        self.arr = np.ndarray((self.n,), dtype=self.dtype, buffer=self.shm.buf)
        # initialize NaNs on first create
        if np.all(self.arr == 0):  # crude check; OK for tests
            self.arr[:] = np.nan

    def update(self, symbol, price):
        i = self.index[symbol]
        with self._lock:
            self.arr[i] = float(price)

    def read(self, symbol):
        i = self.index[symbol]
        return float(self.arr[i])

    def close(self):
        self.shm.close()

    def unlink(self):
        try:
            self.shm.unlink()
        except FileNotFoundError:
            pass
