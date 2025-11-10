# main.py
# ---------------------------------------------------
# Launches Gateway, OrderBook, Strategy, and OrderManager
# in proper startup order with multiprocessing.
# ---------------------------------------------------

from multiprocessing import Process
import time
import os

# Import entry functions from each module
from gateway import run_gateway
from orderbook import run_orderbook
from strategy import run_strategy
from order_manager import run_ordermanager

def main():
    """
    Starts all components in order:
    1. Gateway (news stream)
    2. OrderBook (price feed + shared memory)
    3. Strategy (reads shared memory + sends orders)
    4. OrderManager (receives and logs orders)
    """
    print("[Main] Starting trading system...")

    # --- Step 1: Start Gateway ---
    p_gateway = Process(target=run_gateway, name="Gateway")
    p_gateway.start()
    time.sleep(1)  # give server time to bind

    # --- Step 2: Start OrderManager ---
    p_om = Process(target=run_ordermanager, name="OrderManager")
    p_om.start()
    time.sleep(1)

    # --- Step 3: Start OrderBook ---
    # run_orderbook() should print the shared memory name
    # which strategy.py will need to connect.
    p_ob = Process(target=run_orderbook, name="OrderBook")
    p_ob.start()
    time.sleep(2)

    # --- Step 4: Start Strategy ---
    p_st = Process(target=run_strategy, name="Strategy")
    p_st.start()

    # --- Wait for all to finish ---
    processes = [p_gateway, p_om, p_ob, p_st]
    for p in processes:
        p.join()

    print("[Main] All processes finished.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Main] Terminating system...")
        os._exit(0)
