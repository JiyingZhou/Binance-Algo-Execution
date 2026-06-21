# Core Configuration Parameters
USE_TESTNET = False  # Toggle Testnet/Mainnet
SYMBOL = "BNBUSDT"  # Trading Symbol
ORDER_TYPE = "limit"  # Limit order mode only
PRICE_MODE = "percentage"  # Price Mode: fixed/percentage

# Fixed Price Mode Parameters
BUY_PRICE_FIXED = 40000  # Limit buy price (used only in limit+fixed mode)
TAKE_PROFIT_FIXED = 42000  # Take profit price
STOP_LOSS_FIXED = 38000  # Stop loss price
CHECK_INTERVAL = 30  # Polling interval for buy order status (seconds)

# Percentage Mode Parameters
BUY_DISCOUNT = 0.995  # Buy discount (e.g., 0.99 = 99% of market price)
PROFIT_RATIO = 0.015  # Take profit ratio (e.g., 0.015 = 1.5% increase)
LOSS_RATIO = 0.009  # Stop loss ratio (e.g., 0.009 = 0.9%)

# General Parameters
BUY_QUANTITY = None  # Buy quantity (takes precedence over amount)
BUY_AMOUNT = 10  # Buy amount (USDT)
CONFIRM = False  # Confirmation before trading
WAIT_TIMEOUT = 3510  # Order confirmation timeout (seconds)
USE_KLINE_FOR_PRICE = False  # Use K-line data to fetch price

import time
import signal
import json
from binance.exceptions import BinanceAPIException
from auth_client import get_binance_client
from portfolio_manager import BalanceChecker
from market_data_fetcher import fetch_minute_kline_data


class ProfitLossTrader:
    def __init__(self):
        self.client = get_binance_client()
        self._set_network()
        self.balance_checker = BalanceChecker(is_testnet=USE_TESTNET)
        self.symbol = SYMBOL
        # Parse base asset and quote asset from symbol
        self.base_asset, self.quote_asset = self._parse_symbol()
        # Get symbol precision information
        self.quantity_precision = self._get_quantity_precision()
        self.price_precision = self._get_price_precision()  # Get price precision
        # Get minimum quantity limit for the symbol
        self.min_quantity = self._get_min_quantity()
        self.current_price = None  # Store current market price
        # Record only the latest buy order information
        self.latest_buy_order = {
            'order_id': None,
            'status': None  # Record order status: None/ NEW/ FILLED/ CANCELED, etc.
        }

        # Register termination signal handler (to cancel unfilled orders)
        signal.signal(signal.SIGINT, self._handle_termination)  # Ctrl+C
        signal.signal(signal.SIGTERM, self._handle_termination)  # Force terminate

    def _parse_symbol(self):
        """Parse trading pair to get base and quote assets"""
        quote_assets = ['USDT', 'BUSD', 'USDC', 'TUSD', 'BNB', 'BTC', 'ETH']
        for qa in quote_assets:
            if self.symbol.endswith(qa):
                return self.symbol[:-len(qa)], qa
        return self.symbol[:3], self.symbol[3:]

    def _get_quantity_precision(self):
        """Get allowed quantity precision (decimal places) for the symbol"""
        try:
            info = self.client.get_symbol_info(self.symbol)
            for filter in info['filters']:
                if filter['filterType'] == 'LOT_SIZE':
                    step_size = filter['stepSize']
                    if '.' in step_size:
                        return len(step_size.split('.')[1].rstrip('0'))
                    return 0
            return 6
        except Exception as e:
            print(f"Failed to get quantity precision: {e}")
            return 6

    def _get_price_precision(self):
        """Get allowed price precision (decimal places) for the symbol"""
        try:
            info = self.client.get_symbol_info(self.symbol)
            for filter in info['filters']:
                if filter['filterType'] == 'PRICE_FILTER':
                    tick_size = filter['tickSize']
                    if '.' in tick_size:
                        return len(tick_size.split('.')[1].rstrip('0'))
                    return 0
            return 2
        except Exception as e:
            print(f"Failed to get price precision: {e}")
            return 2

    def _get_min_quantity(self):
        """Get minimum allowed quantity for the symbol"""
        try:
            info = self.client.get_symbol_info(self.symbol)
            for filter in info['filters']:
                if filter['filterType'] == 'LOT_SIZE':
                    return float(filter['minQty'])
            return 0.00001
        except Exception as e:
            print(f"Failed to get minimum quantity: {e}")
            return 0.00001

    def _set_network(self):
        if USE_TESTNET:
            self.client.API_URL = 'https://testnet.binance.vision/api'
            self.client.WS_URL = 'wss://testnet.binance.vision/ws'
        else:
            self.client.API_URL = 'https://api.binance.com/api'
            self.client.WS_URL = 'wss://stream.binance.com:9443/ws'

    def _handle_termination(self, signum, frame):
        """On program termination: Cancel only the latest unfilled buy order"""
        print("\nTermination signal received, exiting safely...")
        if self.latest_buy_order['order_id']:
            order_id = self.latest_buy_order['order_id']
            try:
                order = self.client.get_order(symbol=self.symbol, orderId=order_id)
                current_status = order['status']
                if current_status in ['NEW', 'PARTIALLY_FILLED']:
                    self.client.cancel_order(symbol=self.symbol, orderId=order_id)
                    print(f"Canceled unfilled buy order | ID: {order_id}")
                else:
                    print(f"Buy order {order_id} status is {current_status}, no need to cancel")
            except BinanceAPIException as e:
                if e.code not in [-2011, -2021]:
                    print(f"Failed to process order {order_id}: {e.message}")
            except Exception as e:
                print(f"Error occurred while processing order: {str(e)}")
        print("Safe exit completed")
        exit(0)

    def get_current_price(self):
        """Get current market price"""
        try:
            if USE_KLINE_FOR_PRICE:
                kline_df = fetch_minute_kline_data()
                if kline_df is not None and not kline_df.empty:
                    # WARNING: Ensure market_data_fetcher.py uses 'Close' instead of '收盘价'
                    self.current_price = float(kline_df.iloc[0]['Close'])
            else:
                self.current_price = float(self.client.get_symbol_ticker(symbol=self.symbol)['price'])
            return self.current_price
        except Exception as e:
            print(f"Failed to get price: {e}")
            return None

    def calculate_prices(self):
        """Calculate trading prices, strictly handling price precision"""
        if not self.current_price:
            return None, None, None
        if PRICE_MODE == "fixed":
            buy_price = BUY_PRICE_FIXED
            take_profit = TAKE_PROFIT_FIXED
            stop_loss = STOP_LOSS_FIXED
        else:
            buy_price = round(self.current_price * BUY_DISCOUNT, self.price_precision)
            take_profit = round(self.current_price * (1 + PROFIT_RATIO), self.price_precision)
            stop_loss = round(self.current_price * (1 - LOSS_RATIO), self.price_precision)
        return buy_price, take_profit, stop_loss

    def execute_trade(self, quantity, buy_price):
        """Execute buy (Limit order with no time limit) and set take profit / stop loss"""
        self.latest_buy_order = {'order_id': None, 'status': None}
        try:
            quantity_str = f"{quantity:.{self.quantity_precision}f}"
            buy_price_str = f"{buy_price:.{self.price_precision}f}"

            # Submit limit order
            buy_order = self.client.create_order(
                symbol=self.symbol,
                side=self.client.SIDE_BUY,
                type=self.client.ORDER_TYPE_LIMIT,
                timeInForce=self.client.TIME_IN_FORCE_GTC,
                quantity=quantity_str,
                price=buy_price_str,
                recvWindow=5000
            )
            order_id = buy_order['orderId']
            print(f"Limit buy order submitted | ID: {order_id}")
            self.latest_buy_order = {'order_id': order_id, 'status': buy_order['status']}

            # Wait for buy order to fill
            executed_qty = 0.0
            for _ in range(WAIT_TIMEOUT // CHECK_INTERVAL):
                order = self.client.get_order(symbol=self.symbol, orderId=order_id)
                self.latest_buy_order['status'] = order['status']
                executed_qty = float(order['executedQty'])
                if order['status'] in ['FILLED', 'PARTIALLY_FILLED'] and executed_qty > 0:
                    print(f"Buy order partially/fully filled | Actual quantity: {executed_qty:.{self.quantity_precision}f} {self.base_asset}")

                    # Set OCO based on actual filled quantity
                    if executed_qty >= self.min_quantity:  # Ensure minimum quantity is met
                        _, take_profit, stop_loss = self.calculate_prices()

                        # Recommended setup: Limit Take-Profit + Pure Stop-Loss (Most common, stopLimitPrice not needed)
                        oco_params = {
                            'symbol': self.symbol,
                            'side': self.client.SIDE_SELL,
                            'quantity': f"{executed_qty:.{self.quantity_precision}f}",
                            'price': f"{take_profit:.{self.price_precision}f}",
                            'stopPrice': f"{stop_loss:.{self.price_precision}f}",
                            # Key: Do not pass stopLimitPrice and stopLimitTimeInForce
                        }

                        print("Submitting OCO parameters:", json.dumps(oco_params, indent=2))

                        try:
                            oco_order = self.client.create_oco_order(**oco_params)
                            print(f"\nTake Profit and Stop Loss set | OCO ID: {oco_order['orderListId']}")
                            print(f"Take profit price: {take_profit} {self.quote_asset} | Stop loss price: {stop_loss} {self.quote_asset}")
                        except BinanceAPIException as e:
                            print(f"Failed to submit OCO order: {e.code} - {e.message}")
                            # Optional: If OCO fails, choose to cancel the buy order (depending on needs)
                            self.client.cancel_order(symbol=self.symbol, orderId=order_id)
                            pass

                    # If partially filled, continue waiting for the rest (or cancel depending on needs)
                    if order['status'] == 'PARTIALLY_FILLED':
                        print("Order partially filled, continuing to wait for the remaining amount...")
                    else:
                        break
                time.sleep(CHECK_INTERVAL)

            # Final check of order status
            order = self.client.get_order(symbol=self.symbol, orderId=order_id)
            if order['status'] not in ['FILLED', 'PARTIALLY_FILLED']:
                try:
                    self.client.cancel_order(symbol=self.symbol, orderId=order_id)
                    print(f"Unfilled within {WAIT_TIMEOUT} seconds, automatically canceled order {order_id}")
                except Exception as e:
                    print(f"Failed to cancel order: {e}")
            elif float(order['executedQty']) > 0 and executed_qty == 0:
                # Filled on final check but not processed previously
                print("Last-minute fill detected, actual quantity:", order['executedQty'])

            print(f"Trading process completed")
            return buy_order, None  # Returning None indicates OCO may have been created or failed
        except BinanceAPIException as e:
            print(f"API Error: {e.code} - {e.message}")
            return None, None
        except Exception as e:
            print(f"Trade failed: {str(e)}")
            return None, None


def main():
    mode = "Testnet" if USE_TESTNET else "Mainnet"
    print(f"Limit Order Trading Tool [{mode} Mode] | Symbol: {SYMBOL}\n")

    try:
        trader = ProfitLossTrader()
    except Exception as e:
        print(f"Initialization failed: {e}")
        return

    # Get current price
    if not trader.get_current_price():
        return
    print(f"Current market price: {trader.current_price:.{trader.price_precision}f} {trader.quote_asset}")
    print(f"Symbol precision requirements: Min quantity {trader.min_quantity} {trader.base_asset}, "
          f"Quantity decimals {trader.quantity_precision}, "
          f"Price decimals {trader.price_precision}")

    # Calculate trade prices
    buy_price, take_profit, stop_loss = trader.calculate_prices()
    if not take_profit:
        print("Price calculation failed")
        return

    # Display balances
    balances = trader.balance_checker.get_balances()
    if balances:
        trader.balance_checker.display_balances(balances)
    else:
        print("Failed to retrieve balance information")
        if not CONFIRM:
            return

    # Calculate buy quantity and adjust precision
    quantity = BUY_QUANTITY if BUY_QUANTITY else (BUY_AMOUNT / trader.current_price if BUY_AMOUNT else None)
    if not quantity:
        print("Please set buy quantity or amount")
        return
    if quantity < trader.min_quantity:
        print(f"Buy quantity is below minimum limit {trader.min_quantity} {trader.base_asset}, automatically adjusted to minimum quantity")
        quantity = trader.min_quantity
    quantity = round(quantity, trader.quantity_precision)
    quantity_str = f"{quantity:.{trader.quantity_precision}f}"
    print(f"Adjusted buy quantity: {quantity_str} {trader.base_asset}")

    # Calculate actual buy amount
    actual_amount = quantity * buy_price

    # Trade Information Confirmation
    print(f"\nTrade Plan:")
    print(f"Base Asset: {trader.base_asset} | Quote Asset: {trader.quote_asset} | Symbol: {trader.symbol}")
    print(f"Type: Limit Order \n| Quantity: {quantity_str} {trader.base_asset} | Amount: {actual_amount:.2f} {trader.quote_asset}")
    print(f"Buy Price: {buy_price:.{trader.price_precision}f} {trader.quote_asset} ({BUY_DISCOUNT * 100}%) | Market Price: {trader.current_price:.{trader.price_precision}f} {trader.quote_asset}")
    print(f"Take Profit: {take_profit:.{trader.price_precision}f} {trader.quote_asset} ({PROFIT_RATIO * 100}%) | Stop Loss: {stop_loss:.{trader.price_precision}f} {trader.quote_asset} ({LOSS_RATIO * 100}%)")

    # Check quote asset balance
    quote_balance = 0.0
    try:
        for asset in balances:
            if asset.get('asset') == trader.quote_asset:
                quote_balance = float(asset.get('free', 0))
                break
        print(f"Currently available {trader.quote_asset}: {quote_balance:.2f}")
        required_amount = actual_amount * 1.01
        if quote_balance < required_amount:
            print(f"Insufficient funds | Required: {required_amount:.2f} {trader.quote_asset} (including fees)")
            return
    except Exception as e:
        print(f"Error checking {trader.quote_asset} balance: {str(e)}")
        if CONFIRM and input("Continue executing trade? (y/n): ").lower() != 'y':
            print("Trade canceled")
            return

    # Confirmation Step
    if CONFIRM and input("\nConfirm execution? (y/n): ").lower() != 'y':
        print("Trade canceled")
        return

    # Execute trade
    trader.execute_trade(quantity, buy_price)
    print("\nOperation completed")


if __name__ == "__main__":
    main()