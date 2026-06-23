# ==============================================================================
# ============================ 配置参数（请根据需求修改） ============================
# ==============================================================================

# 1. 模式设置
USE_TESTNET = False  # True=模拟盘，False=真实盘

# 2. 过滤设置
SHOW_ALL_ASSETS = False  # 是否显示所有资产（包括余额为0的）
SHOW_ZERO_VALUE_ASSETS = False  # 是否显示价值为0的资产

# 3. 重点关注资产
PRIORITY_ASSETS = ["USDT", "BTC", "ETH", "BNB"]

# 4. 汇率设置
MANUAL_USD_CNY_RATE = 7.13  # 手动汇率（实时获取失败时使用）

# ==============================================================================
# ============================ 核心逻辑（已修复报错） ============================
# ==============================================================================

from binance import Client
from 登录 import get_binance_client  # 确保登录模块存在且正确
import time
import pandas as pd

class BalanceChecker:
    def __init__(self, is_testnet=USE_TESTNET):
        self.is_testnet = is_testnet
        self.client = self._init_client()
        self.usd_cny_rate = self._get_usd_cny_rate()

        mode = "模拟盘（测试网）" if is_testnet else "真实盘（主网）"
        print(f"📊 已初始化余额查询器，当前模式：{mode}")
        print(f"💱 美元兑人民币汇率：1 USD = {self.usd_cny_rate} CNY\n")

    def _init_client(self):
        """初始化客户端并切换到对应网络"""
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
            print(f"❌ 客户端初始化失败：{str(e)}")
            raise  # 抛出异常以便调用者处理

    def _get_usd_cny_rate(self):
        """不依赖外部API的稳定汇率方案（使用主流交易对间接计算）"""
        # 基础固定汇率（建议每周手动更新一次）
        BASE_USD_CNY = 7.13

        if self.is_testnet:
            return BASE_USD_CNY  # 测试网直接返回固定汇率

        try:
            # 方案：通过BTC/USDT和BTC/CNY（如果支持）的比值计算
            # 1. 获取BTC对USDT的价格（全球通用，几乎无限制）
            btc_usdt = float(self.client.get_symbol_ticker(symbol="BTCUSDT")['price'])

            # 2. 尝试获取BTC对CNY的价格（作为参考）
            try:
                btc_cny = float(self.client.get_symbol_ticker(symbol="BTCCNY")['price'])
                # 计算汇率 = BTC/CNY ÷ BTC/USDT
                calculated_rate = round(btc_cny / btc_usdt, 4)

                # 校验计算结果是否合理（避免异常值）
                if 5 < calculated_rate < 10:  # 正常汇率范围
                    return calculated_rate
                else:
                    print(f"⚠️ 计算汇率异常（{calculated_rate}），使用固定汇率")
            except:
                # 如果BTCCNY不支持，直接返回固定汇率
                pass

        except Exception as e:
            print(f"⚠️ 汇率计算失败（{str(e)}），使用固定汇率")

        return BASE_USD_CNY

    def _get_asset_price_usd(self, asset, total_balance):
        """获取资产美元价格（优化错误处理）"""
        if total_balance <= 0:
            return 0.0

        # 稳定币直接按1:1计算
        if asset in ["USDT", "USDC", "TUSD", "DAI", "BUSD"]:
            return 1.0

        # 查询价格
        try:
            symbol = f"{asset}USDT"
            return float(self.client.get_symbol_ticker(symbol=symbol)['price'])
        except:
            try:
                symbol = f"{asset}USDC"
                return float(self.client.get_symbol_ticker(symbol=symbol)['price'])
            except Exception as e:
                if total_balance > 0:
                    print(f"⚠️ 无法获取{asset}的价格（有余额但无法计价）：{str(e)}")
                return 0.0

    def get_balances(self):
        """获取所有资产余额"""
        try:
            account_info = self.client.get_account()
            balances = account_info['balances']
            formatted_balances = []

            for balance in balances:
                asset = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked

                # 过滤不需要显示的资产
                if total <= 0 and not SHOW_ALL_ASSETS:
                    continue

                # 获取价格和价值
                price_usd = self._get_asset_price_usd(asset, total)
                value_usd = total * price_usd
                value_cny = value_usd * self.usd_cny_rate

                # 过滤零价值资产
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
            print(f"❌ 获取余额失败：{str(e)}")
            return None

    # 只修改display_balances方法中的数据行部分
    def display_balances(self, balances):
        if not balances:
            print("❌ No balance data to display")
            return

        # 分离重点资产和其他资产
        priority = []
        others = []
        for balance in balances:
            if balance['asset'] in PRIORITY_ASSETS:
                priority.append(balance)
            else:
                others.append(balance)

        all_balances = priority + sorted(others, key=lambda x: x['asset'])

        # 计算总资产价值
        total_value_usd = sum(item['value_usd'] for item in all_balances)
        total_value_cny = sum(item['value_cny'] for item in all_balances)

        # 计算资产名称宽度（英文统一按1字符宽度计算）
        max_asset_width = max(len(item['asset']) for item in all_balances)
        max_asset_width = max(max_asset_width, len("Asset"))  # 匹配表头宽度
        asset_column_width = max_asset_width + 2  # 增加缓冲

        # 英文表头列宽设置（全英文无宽度差异）
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

        # 英文表头格式
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
            "Asset",  # 资产
            "Free Balance",  # 可用余额
            "Locked Balance",  # 冻结余额
            "Total Balance",  # 总余额
            "Price (USD)",  # 美元单价
            "Value (USD)",  # 总价值(USD)
            "Value (CNY)"  # 总价值(CNY)
        ))
        print("-" * total_width)

        # 数据行格式
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


# 主程序入口
if __name__ == "__main__":
    try:
        checker = BalanceChecker()
        balances = checker.get_balances()
        if balances:
            checker.display_balances(balances)
            # 生成DataFrame并存储数据
            asset_df = pd.DataFrame(balances)  # 新增行：将资产数据转换为DataFrame
            print("\n📋 资产数据DataFrame:")
            print(asset_df)
            # 可选：保存为CSV文件
            # asset_df.to_csv('资产数据.csv', index=False, encoding='utf-8-sig')
            # 安全筛选USDT（避免空DataFrame报错）
            if not asset_df.empty and 'asset' in asset_df.columns:
                usdt_data = asset_df[asset_df['asset'] == 'USDT']
                print("\nUSDT数据：")
                print(usdt_data if not usdt_data.empty else "未持有USDT")
    except Exception as e:
        print(f"\n❌ 程序执行失败：{str(e)}")
