# tests/test_shared_memory.py
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import importlib
import os
import time

import numpy as np
import pytest
from shared_memory_utils import *


@pytest.mark.timeout(10)
def test_shared_price_book_update_read_roundtrip():
    """SharedPriceBook.update() then read() should return the latest price accurately."""
    smu = importlib.import_module("shared_memory_utils")
    if not hasattr(smu, "SharedPriceBook"):
        pytest.skip("SharedPriceBook not implemented in shared_memory_utils.py")

    # Try to accommodate different constructors:
    symbols = ["AAPL", "MSFT"]
    name = os.environ.get("PRICEBOOK_NAME", "pricebook-test")
    try:
        spb = smu.SharedPriceBook(symbols=symbols, name=name)  # preferred signature
    except TypeError:
        spb = smu.SharedPriceBook(symbols, name)  # fallback

    try:
        px = 123.456
        spb.update("AAPL", px)
        got = spb.read("AAPL")
        # read() could return float or a tuple/dict with "price"
        if isinstance(got, (tuple, list)):
            got = got[0]
        elif isinstance(got, dict):
            got = got.get("price", got.get("px"))
        assert got == pytest.approx(px, rel=1e-6, abs=1e-9)
    finally:
        # Clean up if API provided
        for method in ("close", "unlink", "shutdown"):
            if hasattr(spb, method):
                try:
                    getattr(spb, method)()
                except Exception:
                    pass


@pytest.mark.timeout(10)
def test_shared_price_book_many_updates_is_consistent():
    """Multiple updates must not produce torn reads (basic consistency)."""
    smu = importlib.import_module("shared_memory_utils")
    if not hasattr(smu, "SharedPriceBook"):
        pytest.skip("SharedPriceBook not implemented")

    symbols = ["AAPL"]
    name = os.environ.get("PRICEBOOK_NAME", "pricebook-consistency")
    try:
        spb = smu.SharedPriceBook(symbols=symbols, name=name)
    except TypeError:
        spb = smu.SharedPriceBook(symbols, name)

    try:
        for k in range(200):
            spb.update("AAPL", float(k))
            v = spb.read("AAPL")
            if isinstance(v, (tuple, list)):
                v = v[0]
            elif isinstance(v, dict):
                v = v.get("price", v.get("px"))
            # Value should be between last two writes; allow eventuality but never "nonsense"
            assert 0 <= v <= 200
        # Final value should be close to last write
        v = spb.read("AAPL")
        if isinstance(v, (tuple, list)):
            v = v[0]
        elif isinstance(v, dict):
            v = v.get("price", v.get("px"))
        assert v == pytest.approx(199.0, abs=1e-9)
    finally:
        for method in ("close", "unlink", "shutdown"):
            if hasattr(spb, method):
                try:
                    getattr(spb, method)()
                except Exception:
                    pass
