# 核心配置参数
USE_TESTNET = False  # 模拟/真实交易切换
SYMBOL = "BNBUSDT"  # 交易标的物
ORDER_TYPE = "limit"  # 仅保留限价单模式
PRICE_MODE = "percentage"  # 价格模式: fixed(固定价)/percentage(比例)

# 固定价格模式参数
BUY_PRICE_FIXED = 40000  # 限价买入价(仅limit+fixed模式使用)
TAKE_PROFIT_FIXED = 42000  # 止盈价格
STOP_LOSS_FIXED = 38000  # 止损价格
time_chaxun = 30  # 多久检查一次买入单
# 比例模式参数
BUY_DISCOUNT = 0.995  # 买入折扣(例:0.99=市场价99折)
PROFIT_RATIO = 0.015  # 止盈比例(0.25%涨幅)
LOSS_RATIO = 0.009  # 止损比例，0.001=0.1%

# 通用参数
BUY_QUANTITY = None  # 买入数量(优先于金额)
BUY_AMOUNT = 10  # 买入金额(USDT)
CONFIRM = False  # 交易前确认
WAIT_TIMEOUT = 3510 # 订单确认超时(秒)
USE_KLINE_FOR_PRICE = False  # 是否用K线数据获取价格

import time
import signal
import json
from binance.exceptions import BinanceAPIException
from 登录 import get_binance_client
from 查询资产 import BalanceChecker
from 市场数据查询 import fetch_minute_kline_data


class ProfitLossTrader:
    def __init__(self):
        self.client = get_binance_client()
        self._set_network()
        self.balance_checker = BalanceChecker(is_testnet=USE_TESTNET)
        self.symbol = SYMBOL
        # 解析标的物基础资产和计价资产
        self.base_asset, self.quote_asset = self._parse_symbol()
        # 获取交易对精度信息
        self.quantity_precision = self._get_quantity_precision()
        self.price_precision = self._get_price_precision()  # 获取价格精度
        # 获取交易对最小数量限制
        self.min_quantity = self._get_min_quantity()
        self.current_price = None  # 存储当前市场价
        # 仅记录最近一笔买入订单信息
        self.latest_buy_order = {
            'order_id': None,
            'status': None  # 记录订单状态：None/ NEW/ FILLED/ CANCELED等
        }

        # 注册终止信号处理（用于撤销未成交订单）
        signal.signal(signal.SIGINT, self._handle_termination)  # Ctrl+C
        signal.signal(signal.SIGTERM, self._handle_termination)  # 强制终止

    def _parse_symbol(self):
        """解析交易对，获取基础资产和计价资产"""
        quote_assets = ['USDT', 'BUSD', 'USDC', 'TUSD', 'BNB', 'BTC', 'ETH']
        for qa in quote_assets:
            if self.symbol.endswith(qa):
                return self.symbol[:-len(qa)], qa
        return self.symbol[:3], self.symbol[3:]

    def _get_quantity_precision(self):
        """获取交易对允许的数量精度（小数位数）"""
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
            print(f"获取数量精度失败: {e}")
            return 6

    def _get_price_precision(self):
        """获取交易对允许的价格精度（小数位数）"""
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
            print(f"获取价格精度失败: {e}")
            return 2

    def _get_min_quantity(self):
        """获取交易对允许的最小数量"""
        try:
            info = self.client.get_symbol_info(self.symbol)
            for filter in info['filters']:
                if filter['filterType'] == 'LOT_SIZE':
                    return float(filter['minQty'])
            return 0.00001
        except Exception as e:
            print(f"获取最小数量失败: {e}")
            return 0.00001

    def _set_network(self):
        if USE_TESTNET:
            self.client.API_URL = 'https://testnet.binance.vision/api'
            self.client.WS_URL = 'wss://testnet.binance.vision/ws'
        else:
            self.client.API_URL = 'https://api.binance.com/api'
            self.client.WS_URL = 'wss://stream.binance.com:9443/ws'

    def _handle_termination(self, signum, frame):
        """程序终止时：仅撤销最近一笔未成交的买入单"""
        print("\n收到终止信号，正在安全退出...")
        if self.latest_buy_order['order_id']:
            order_id = self.latest_buy_order['order_id']
            try:
                order = self.client.get_order(symbol=self.symbol, orderId=order_id)
                current_status = order['status']
                if current_status in ['NEW', 'PARTIALLY_FILLED']:
                    self.client.cancel_order(symbol=self.symbol, orderId=order_id)
                    print(f"已撤销未成交买入单 | ID: {order_id}")
                else:
                    print(f"买入单 {order_id} 状态为 {current_status}，无需撤销")
            except BinanceAPIException as e:
                if e.code not in [-2011, -2021]:
                    print(f"处理订单 {order_id} 失败: {e.message}")
            except Exception as e:
                print(f"处理订单时出错: {str(e)}")
        print("安全退出完成")
        exit(0)

    def get_current_price(self):
        """获取当前市场价"""
        try:
            if USE_KLINE_FOR_PRICE:
                kline_df = fetch_minute_kline_data()
                if kline_df is not None and not kline_df.empty:
                    self.current_price = float(kline_df.iloc[0]['收盘价'])
            else:
                self.current_price = float(self.client.get_symbol_ticker(symbol=self.symbol)['price'])
            return self.current_price
        except Exception as e:
            print(f"价格获取失败: {e}")
            return None

    def calculate_prices(self):
        """计算交易价格，严格按照价格精度处理"""
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
        """执行买入（无时间限制的限价单）并设置止盈止损"""
        self.latest_buy_order = {'order_id': None, 'status': None}
        try:
            quantity_str = f"{quantity:.{self.quantity_precision}f}"
            buy_price_str = f"{buy_price:.{self.price_precision}f}"

            # 提交限价单
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
            print(f"限价买入单提交 | ID: {order_id}")
            self.latest_buy_order = {'order_id': order_id, 'status': buy_order['status']}

            # 等待买入成交
            executed_qty = 0.0
            for _ in range(WAIT_TIMEOUT // time_chaxun):
                order = self.client.get_order(symbol=self.symbol, orderId=order_id)
                self.latest_buy_order['status'] = order['status']
                executed_qty = float(order['executedQty'])
                if order['status'] in ['FILLED', 'PARTIALLY_FILLED'] and executed_qty > 0:
                    print(f"买入已成交部分 | 实际数量: {executed_qty:.{self.quantity_precision}f} {self.base_asset}")

                    # 基于实际成交数量设置 OCO
                    if executed_qty >= self.min_quantity:  # 确保达到最小数量
                        _, take_profit, stop_loss = self.calculate_prices()

                        # 推荐方案：止盈限价 + 纯止损单（最常用，不需要 stopLimitPrice）
                        oco_params = {
                            'symbol': self.symbol,
                            'side': self.client.SIDE_SELL,
                            'quantity': f"{executed_qty:.{self.quantity_precision}f}",
                            'price': f"{take_profit:.{self.price_precision}f}",
                            'stopPrice': f"{stop_loss:.{self.price_precision}f}",
                            # 关键：不传 stopLimitPrice 和 stopLimitTimeInForce
                        }

                        print("提交 OCO 参数:", json.dumps(oco_params, indent=2))

                        try:
                            oco_order = self.client.create_oco_order(**oco_params)
                            print(f"\n止盈止损设置完成 | OCO ID: {oco_order['orderListId']}")
                            print(f"止盈价: {take_profit} {self.quote_asset} | 止损价: {stop_loss} {self.quote_asset}")
                        except BinanceAPIException as e:
                            print(f"OCO 订单提交失败: {e.code} - {e.message}")
                            # 可选：如果 OCO 失败，可以选择撤销买入单（视需求）
                            self.client.cancel_order(symbol=self.symbol, orderId=order_id)
                            pass

                    # 如果部分成交，继续等待剩余部分（或根据需求撤销）
                    if order['status'] == 'PARTIALLY_FILLED':
                        print("订单部分成交，继续等待剩余部分...")
                    else:
                        break
                time.sleep(time_chaxun)

            # 最终检查订单状态
            order = self.client.get_order(symbol=self.symbol, orderId=order_id)
            if order['status'] not in ['FILLED', 'PARTIALLY_FILLED']:
                try:
                    self.client.cancel_order(symbol=self.symbol, orderId=order_id)
                    print(f"{WAIT_TIMEOUT}秒内未成交，已自动撤销订单 {order_id}")
                except Exception as e:
                    print(f"撤销订单失败: {e}")
            elif float(order['executedQty']) > 0 and executed_qty == 0:
                # 最后一次检查有成交但之前没处理
                print("检测到最后一刻成交，实际数量:", order['executedQty'])

            print(f"交易流程结束")
            return buy_order, None  # 返回 None 代表 OCO 可能已创建或失败
        except BinanceAPIException as e:
            print(f"API错误: {e.code} - {e.message}")
            return None, None
        except Exception as e:
            print(f"交易失败: {str(e)}")
            return None, None


def main():
    mode = "模拟" if USE_TESTNET else "真实"
    print(f"限价单交易工具 [{mode}模式] | 标的物: {SYMBOL}\n")

    try:
        trader = ProfitLossTrader()
    except Exception as e:
        print(f"初始化失败: {e}")
        return

    # 获取当前价格
    if not trader.get_current_price():
        return
    print(f"当前市场价: {trader.current_price:.{trader.price_precision}f} {trader.quote_asset}")
    print(f"交易对精度要求: 最小数量 {trader.min_quantity} {trader.base_asset}, "
          f"数量小数位 {trader.quantity_precision}位, "
          f"价格小数位 {trader.price_precision}位")

    # 计算交易价格
    buy_price, take_profit, stop_loss = trader.calculate_prices()
    if not take_profit:
        print("价格计算失败")
        return

    # 显示资产
    balances = trader.balance_checker.get_balances()
    if balances:
        trader.balance_checker.display_balances(balances)
    else:
        print("无法获取资产信息")
        if not CONFIRM:
            return

    # 计算买入量并调整精度
    quantity = BUY_QUANTITY if BUY_QUANTITY else (BUY_AMOUNT / trader.current_price if BUY_AMOUNT else None)
    if not quantity:
        print("请设置买入数量或金额")
        return
    if quantity < trader.min_quantity:
        print(f"买入数量低于最小限制 {trader.min_quantity} {trader.base_asset}，自动调整为最小数量")
        quantity = trader.min_quantity
    quantity = round(quantity, trader.quantity_precision)
    quantity_str = f"{quantity:.{trader.quantity_precision}f}"
    print(f"已调整买入数量: {quantity_str} {trader.base_asset}")

    # 计算实际买入金额
    actual_amount = quantity * buy_price

    # 交易信息确认
    print(f"\n交易计划:")
    print(f"交易资产: {trader.base_asset} | 计价资产: {trader.quote_asset} | 交易对: {trader.symbol}")
    print(f"类型: 限价单 \n| 数量: {quantity_str} {trader.base_asset} | 金额: {actual_amount:.2f} {trader.quote_asset}")
    print(f"买价: {buy_price:.{trader.price_precision}f} {trader.quote_asset} ({BUY_DISCOUNT * 100}%) | 市价: {trader.current_price:.{trader.price_precision}f} {trader.quote_asset}")
    print(f"止盈: {take_profit:.{trader.price_precision}f} {trader.quote_asset} ({PROFIT_RATIO * 100}%) | 止损: {stop_loss:.{trader.price_precision}f} {trader.quote_asset} ({LOSS_RATIO * 100}%)")

    # 检查计价资产余额
    quote_balance = 0.0
    try:
        for asset in balances:
            if asset.get('asset') == trader.quote_asset:
                quote_balance = float(asset.get('free', 0))
                break
        print(f"当前可用{trader.quote_asset}: {quote_balance:.2f}")
        required_amount = actual_amount * 1.01
        if quote_balance < required_amount:
            print(f"资金不足 | 需要: {required_amount:.2f} {trader.quote_asset} (含手续费)")
            return
    except Exception as e:
        print(f"检查{trader.quote_asset}余额时出错: {str(e)}")
        if CONFIRM and input("继续执行交易? (y/n): ").lower() != 'y':
            print("交易取消")
            return

    # 确认环节
    if CONFIRM and input("\n确认执行? (y/n): ").lower() != 'y':
        print("交易取消")
        return

    # 执行交易
    trader.execute_trade(quantity, buy_price)
    print("\n操作完成")


if __name__ == "__main__":
    main()
