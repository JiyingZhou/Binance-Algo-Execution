import time
import execution_engine  # Import trading module

# Configure run interval (seconds), e.g., 300 seconds = 5 minutes
RUN_INTERVAL = 3600
# New configuration: Whether to run only once
RUN_ONCE = False  # Set to True to run only once, False to maintain periodic execution


def periodic_run():
    print(f"Starting periodic run | Interval: {RUN_INTERVAL}s | Symbol: {execution_engine.SYMBOL}")
    print("=" * 60)

    try:
        while True:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting new execution cycle")

            # Execute main trading logic
            try:
                # Initialize trader instance
                trader = execution_engine.ProfitLossTrader()
                execution_engine.trader = trader  # Expose variable for external access

                # Execute core process
                if trader.get_current_price():
                    buy_price, take_profit, stop_loss = trader.calculate_prices()
                    execution_engine.main()  # Execute trading logic

                # Directly accessible variable
                print(f"Current price: {trader.current_price:.2f} USDT (Externally accessible)")

            except Exception as e:
                print(f"Error in current cycle: {str(e)}")

            # Determine whether to run only once based on the RUN_ONCE parameter
            if RUN_ONCE:
                print("\nSingle run mode is enabled. The program will exit now.")
                break
            else:
                # Fixed interval wait, does not calculate execution time
                print(f"\nCycle ended. Running again in {RUN_INTERVAL} seconds")
                print("-" * 60)
                time.sleep(RUN_INTERVAL)

    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    finally:
        print("Periodic run ended")


if __name__ == "__main__":
    periodic_run()