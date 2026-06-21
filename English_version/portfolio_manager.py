# ==============================================================================
# ================= Configuration Parameters (Modify as needed) ================
# ==============================================================================

# 1. Mode Settings
USE_TESTNET = False  # True = Testnet, False = Mainnet

# 2. Filter Settings
SHOW_ALL_ASSETS = False  # Whether to show all assets (including those with 0 balance)
SHOW_ZERO_VALUE_ASSETS = False  # Whether to show zero-value assets

# 3. Priority Assets
PRIORITY_ASSETS = ["USDT", "BTC", "ETH", "BNB"]

# 4. Exchange Rate Settings
MANUAL_USD_CNY_RATE = 7.13  # Manual rate (used when real-time fetch fails)

# ==============================================================================
# ================================= Core Logic =================================
# ==============================================================================

from binance import Client
from auth_client import get_binance_client  # Ensure auth module exists and is correct
import time
import pandas as pd

class BalanceChecker:
    def __init__(self, is_testnet=USE_TESTNET):
        self.is_testnet = is_testnet
        self.client = self._init_client()
        self.usd_cny_rate = self._get_usd_cny_rate()

        mode = "Testnet" if is_testnet else "Mainnet"
        print(f"📊 Balance Checker initialized, Current Mode: {mode}")
        print(f"💱 USD to CNY Exchange Rate: 1 USD = {self.usd_cny_rate} CNY\n")

    def _init_client(self):
        """Initialize client and switch to the corresponding network"""
        try:
            client = get_binance_client()
            if self.is_testnet:
                client.API_URL = 'https://testnet.binance.vision/api'
                client.WS_URL = 'wss://testnet.binance.vision/ws'
            else:
                client.API_URL = 'https://api.binance.com/api'
                client.WS_URL = 'wss://stream.binance.com:9443/ws'
            return client
        except Exception as e:
            print(f"❌ Client initialization failed: {str(e)}")
            raise  # Raise exception for caller to handle

    def _get_usd_cny_rate(self):
        """Stable exchange rate solution without external APIs (indirect calculation using mainstream pairs)"""
        # Base fixed exchange rate (recommended to update manually weekly)
        BASE_USD_CNY = 7.13

        if self.is_testnet:
            return BASE_USD_CNY  # Testnet directly returns the fixed rate

        try:
            # Scheme: Calculate via the ratio of BTC/USDT and BTC/CNY (if supported)
            # 1. Get BTC to USDT price (globally universal, almost unrestricted)
            btc_usdt = float(self.client.get_symbol_ticker(symbol="BTCUSDT")['price'])

            # 2. Try to get BTC to CNY price (as reference)
            try:
                btc_cny = float(self.client.get_symbol_ticker(symbol="BTCCNY")['price'])
                # Calculate exchange rate = BTC/CNY / BTC/USDT
                calculated_rate = round(btc_cny / btc_usdt, 4)

                # Validate calculation result (avoid anomalies)
                if 5 < calculated_rate < 10:  # Normal exchange rate range
                    return calculated_rate
                else:
                    print(f"⚠️ Exchange rate calculation abnormal ({calculated_rate}), using fixed rate")
            except:
                # If BTCCNY is unsupported, return fixed rate directly
                pass

        except Exception as e:
            print(f"⚠️ Exchange rate calculation failed ({str(e)}), using fixed rate")

        return BASE_USD_CNY

    def _get_asset_price_usd(self, asset, total_balance):
        """Get asset USD price (optimized error handling)"""
        if total_balance <= 0:
            return 0.0

        # Stablecoins calculated directly at 1:1
        if asset in ["USDT", "USDC", "TUSD", "DAI", "BUSD"]:
            return 1.0

        # Query price
        try:
            symbol = f"{asset}USDT"
            return float(self.client.get_symbol_ticker(symbol=symbol)['price'])
        except:
            try:
                symbol = f"{asset}USDC"
                return float(self.client.get_symbol_ticker(symbol=symbol)['price'])
            except Exception as e:
                if total_balance > 0:
                    print(f"⚠️ Unable to get price for {asset} (has balance but cannot be priced): {str(e)}")
                return 0.0

    def get_balances(self):
        """Get all asset balances"""
        try:
            account_info = self.client.get_account()
            balances = account_info['balances']
            formatted_balances = []

            for balance in balances:
                asset = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked

                # Filter out assets that do not need to be displayed
                if total <= 0 and not SHOW_ALL_ASSETS:
                    continue

                # Get price and value
                price_usd = self._get_asset_price_usd(asset, total)
                value_usd = total * price_usd
                value_cny = value_usd * self.usd_cny_rate

                # Filter zero-value assets
                if value_usd <= 0 and not SHOW_ZERO_VALUE_ASSETS:
                    continue

                formatted_balances.append({
                    'asset': asset,
                    'free': free,
                    'locked': locked,
                    'total': total,
                    'price_usd': price_usd,
                    'value_usd': value_usd,
                    'value_cny': value_cny
                })

            return formatted_balances

        except Exception as e:
            print(f"❌ Failed to get balance: {str(e)}")
            return None

    def display_balances(self, balances):
        if not balances:
            print("❌ No balance data to display")
            return

        # Separate priority assets and other assets
        priority = []
        others = []
        for balance in balances:
            if balance['asset'] in PRIORITY_ASSETS:
                priority.append(balance)
            else:
                others.append(balance)

        all_balances = priority + sorted(others, key=lambda x: x['asset'])

        # Calculate total asset value
        total_value_usd = sum(item['value_usd'] for item in all_balances)
        total_value_cny = sum(item['value_cny'] for item in all_balances)

        # Calculate asset name width
        max_asset_width = max(len(item['asset']) for item in all_balances)
        max_asset_width = max(max_asset_width, len("Asset"))  # Match header width
        asset_column_width = max_asset_width + 2  # Add buffer

        # English header column width settings
        columns_width = {
            'free': 18,
            'locked': 18,
            'total': 18,
            'price_usd': 16,
            'value_usd': 18,
            'value_cny': 18
        }

        total_width = asset_column_width + sum(columns_width.values()) + 6
        print("=" * total_width)

        # English header format
        header_format = (
            f"{{:<{asset_column_width}}} "
            f"{{:^{columns_width['free']}}} "
            f"{{:^{columns_width['locked']}}} "
            f"{{:^{columns_width['total']}}} "
            f"{{:^{columns_width['price_usd']}}} "
            f"{{:^{columns_width['value_usd']}}} "
            f"{{:^{columns_width['value_cny']}}}"
        )
        print(header_format.format(
            "Asset",
            "Free Balance",
            "Locked Balance",
            "Total Balance",
            "Price (USD)",
            "Value (USD)",
            "Value (CNY)"
        ))
        print("-" * total_width)

        # Data row format
        row_format = (
            f"{{:<{asset_column_width}}} "
            f"{{:^{columns_width['free']}.8f}} "
            f"{{:^{columns_width['locked']}.8f}} "
            f"{{:^{columns_width['total']}.8f}} "
            f"{{:^{columns_width['price_usd']}.4f}} "
            f"{{:^{columns_width['value_usd']}.2f}} "
            f"{{:^{columns_width['value_cny']}.2f}}"
        )

        for item in all_balances:
            print(row_format.format(
                item['asset'],
                item['free'],
                item['locked'],
                item['total'],
                item['price_usd'],
                item['value_usd'],
                item['value_cny']
            ))

        print("-" * total_width)
        print(f"Total Portfolio Value: {total_value_usd:.2f} USD  /  {total_value_cny:.2f} CNY")
        print("Note: Data for reference only. Please refer to Binance official platform for accuracy.")
        print("=" * total_width)


# Main program entry
if __name__ == "__main__":
    try:
        checker = BalanceChecker()
        balances = checker.get_balances()
        if balances:
            checker.display_balances(balances)
            # Generate DataFrame and store data
            asset_df = pd.DataFrame(balances)
            print("\n📋 Asset Data DataFrame:")
            print(asset_df)
            # Optional: Save to CSV file
            # asset_df.to_csv('asset_data.csv', index=False, encoding='utf-8-sig')
            # Safely filter USDT (avoid empty DataFrame errors)
            if not asset_df.empty and 'asset' in asset_df.columns:
                usdt_data = asset_df[asset_df['asset'] == 'USDT']
                print("\nUSDT Data:")
                print(usdt_data if not usdt_data.empty else "No USDT held")
    except Exception as e:
        print(f"\n❌ Program execution failed: {str(e)}")