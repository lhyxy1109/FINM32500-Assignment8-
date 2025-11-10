# tests/test_strategy_logic.py
"""
This test checks *pure* signal logic if your strategy module exposes helpers.
It will be skipped automatically if those helpers aren't present yet.

Expected helpers (any of these names):
- price_signal(short_ma, long_ma) -> "BUY"/"SELL"
- news_signal(sentiment, bull, bear) -> "BUY"/"SELL"/"NEUTRAL"
- combine_signals(price_sig, news_sig) -> "BUY"/"SELL"/"HOLD"
OR a single function:
- generate_trade_decision(short_ma, long_ma, sentiment, bull, bear) -> side or None
"""
import importlib
import pytest


def _import_strategy():
    try:
        return importlib.import_module("strategy")
    except Exception as e:
        pytest.skip(f"strategy module not importable: {e}")


def _call_if_exists(mod, name, *args, **kwargs):
    fn = getattr(mod, name, None)
    if fn is None:
        return None, False
    return fn(*args, **kwargs), True


def test_price_and_news_both_buy():
    strat = _import_strategy()
    # Try combined first
    out, ok = _call_if_exists(strat, "generate_trade_decision", 105.0, 100.0, 80, 60, 40)
    if ok:
        assert (out or "").upper().startswith("BUY")
        return

    # Otherwise use individual helpers if available
    p_sig, p_ok = _call_if_exists(strat, "price_signal", 105.0, 100.0)
    n_sig, n_ok = _call_if_exists(strat, "news_signal", 80, 60, 40)
    c_sig, c_ok = _call_if_exists(strat, "combine_signals", p_sig, n_sig) if (p_ok and n_ok) else (None, False)

    if p_ok and n_ok and c_ok:
        assert p_sig == "BUY"
        assert n_sig in ("BUY", "BULL")
        assert c_sig in ("BUY", "TRADE_BUY")
    else:
        pytest.skip("Strategy helpers not implemented")

def test_conflict_means_hold_or_none():
    strat = _import_strategy()
    out, ok = _call_if_exists(strat, "generate_trade_decision", 95.0, 100.0, 80, 60, 40)
    if ok:
        assert out in (None, "", "HOLD", "NOOP")
        return

    p_sig, p_ok = _call_if_exists(strat, "price_signal", 95.0, 100.0)  # SELL
    n_sig, n_ok = _call_if_exists(strat, "news_signal", 80, 60, 40)    # BUY
    c_sig, c_ok = _call_if_exists(strat, "combine_signals", p_sig, n_sig) if (p_ok and n_ok) else (None, False)

    if p_ok and n_ok and c_ok:
        assert p_sig == "SELL"
        assert n_sig in ("BUY", "BULL")
        assert c_sig in ("HOLD", "NOOP", None, "")
    else:
        pytest.skip("Strategy helpers not implemented")
