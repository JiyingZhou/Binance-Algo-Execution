# 核心配置参数
USE_TESTNET = False  # 模拟/真实环境切换
SYMBOL = "BTCUSDT"  # 目标交易对(留空则查询所有)
START_DATE = "2025-10-01"  # 开始日期(YYYY-MM-DD)
END_DATE = None  # 结束日期(None则到当前)
EXPORT_CSV = True  # 是否导出为CSV文件
CSV_PATH = "交易历史记录.csv"  # 导出文件路径

import time
import csv
from datetime import datetime, timedelta
import pandas as pd
from binance.exceptions import BinanceAPIException
from 登录 import get_binance_client
from 查询资产 import BalanceChecker


class TradeHistoryRecorder:
    def __init__(self):
        self.client = get_binance_client()
        self._set_network()
        self.balance_checker = BalanceChecker(is_testnet=USE_TESTNET)
        self.symbol = SYMBOL.upper() if SYMBOL else None
        self._time_format = "%Y-%m-%d %H:%M:%S"

    def _set_network(self):
        if USE_TESTNET:
            self.client.API_URL = 'https://testnet.binance.vision/api'
        else:
            self.client.API_URL = 'https://api.binance.com/api'

    def _str_to_ms(self, date_str):
        """将日期字符串转换为毫秒时间戳"""
        if not date_str:
            return None
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return int(dt.timestamp() * 1000)
        except Exception as e:
            print(f"日期格式错误: {e}")
            return None

    def _generate_time_ranges(self, start_ms, end_ms):
        """
        将时间范围分割为多个24小时区间（解决API 24小时限制）
        :return: 时间区间列表 [(start1, end1), (start2, end2), ...]
        """
        ranges = []
        current_start = start_ms

        # 24小时的毫秒数
        one_day_ms = 24 * 60 * 60 * 1000

        while current_start < end_ms:
            # 每个区间结束时间 = 当前开始时间 + 24小时，或总结束时间（取较小值）
            current_end = min(current_start + one_day_ms, end_ms)
            ranges.append((current_start, current_end))
            current_start = current_end  # 下一个区间从当前结束时间开始

        return ranges

    def get_historical_orders(self):
        """获取历史挂单记录(支持跨天查询)"""
        print("\n==== 获取历史挂单记录 ====")
        orders = []
        start_ms = self._str_to_ms(START_DATE)
        end_ms = self._str_to_ms(END_DATE) or int(time.time() * 1000)

        if not start_ms or start_ms >= end_ms:
            print("时间范围无效")
            return None

        # 生成多个24小时区间
        time_ranges = self._generate_time_ranges(start_ms, end_ms)
        print(f"时间范围过大，自动分割为 {len(time_ranges)} 个查询区间")

        try:
            for i, (range_start, range_end) in enumerate(time_ranges, 1):
                print(
                    f"查询区间 {i}/{len(time_ranges)}: {datetime.fromtimestamp(range_start / 1000).strftime('%Y-%m-%d')} 至 {datetime.fromtimestamp(range_end / 1000).strftime('%Y-%m-%d')}")

                last_order_id = 0
                while True:
                    params = {
                        "symbol": self.symbol,
                        "startTime": range_start,
                        "endTime": range_end,
                        "limit": 1000,
                        "orderId": last_order_id + 1 if last_order_id else None
                    }

                    params = {k: v for k, v in params.items() if v is not None}
                    current_orders = self.client.get_all_orders(**params)

                    if not current_orders:
                        break

                    for order in current_orders:
                        order_time = datetime.fromtimestamp(order['time'] / 1000).strftime(self._time_format)
                        update_time = datetime.fromtimestamp(order['updateTime'] / 1000).strftime(self._time_format)

                        orders.append({
                            "记录类型": "挂单",
                            "订单ID": order['orderId'],
                            "交易对": order['symbol'],
                            "方向": "买入" if order['side'] == "BUY" else "卖出",
                            "类型": order['type'],
                            "价格": float(order['price']),
                            "数量": float(order['origQty']),
                            "已成交数量": float(order['executedQty']),
                            "状态": order['status'],
                            "提交时间": order_time,
                            "更新时间": update_time
                        })

                    last_order_id = current_orders[-1]['orderId']
                    if len(current_orders) < 1000:
                        break

                    time.sleep(0.1)

                time.sleep(0.1)  # 区间之间稍作停顿

            print(f"共获取 {len(orders)} 条挂单记录")
            return pd.DataFrame(orders)

        except BinanceAPIException as e:
            print(f"获取订单失败: {e.code} - {e.message}")
            return None
        except Exception as e:
            print(f"异常: {str(e)}")
            return None

    def get_trade_history(self):
        """获取实际成交记录(支持跨天查询)"""
        print("\n==== 获取成交记录 ====")
        trades = []
        start_ms = self._str_to_ms(START_DATE)
        end_ms = self._str_to_ms(END_DATE) or int(time.time() * 1000)

        if not start_ms or start_ms >= end_ms:
            print("时间范围无效")
            return None

        # 生成多个24小时区间
        time_ranges = self._generate_time_ranges(start_ms, end_ms)
        print(f"时间范围过大，自动分割为 {len(time_ranges)} 个查询区间")

        try:
            for i, (range_start, range_end) in enumerate(time_ranges, 1):
                print(
                    f"查询区间 {i}/{len(time_ranges)}: {datetime.fromtimestamp(range_start / 1000).strftime('%Y-%m-%d')} 至 {datetime.fromtimestamp(range_end / 1000).strftime('%Y-%m-%d')}")

                from_id = 0
                while True:
                    params = {
                        "symbol": self.symbol,
                        "startTime": range_start,
                        "endTime": range_end,
                        "limit": 1000,
                        "fromId": from_id
                    }

                    params = {k: v for k, v in params.items() if v is not None and v != 0}
                    current_trades = self.client.get_my_trades(**params)

                    if not current_trades:
                        break

                    for trade in current_trades:
                        trade_time = datetime.fromtimestamp(trade['time'] / 1000).strftime(self._time_format)
                        is_buyer = "买入" if trade['isBuyer'] else "卖出"

                        trades.append({
                            "记录类型": "成交",
                            "成交ID": trade['id'],
                            "关联订单ID": trade['orderId'],
                            "交易对": trade['symbol'],
                            "方向": is_buyer,
                            "成交价格": float(trade['price']),
                            "成交数量": float(trade['qty']),
                            "成交金额": float(trade['quoteQty']),
                            "手续费": float(trade['commission']),
                            "手续费资产": trade['commissionAsset'],
                            "成交时间": trade_time
                        })

                    from_id = current_trades[-1]['id'] + 1
                    if len(current_trades) < 1000:
                        break

                    time.sleep(0.1)

                time.sleep(0.1)  # 区间之间稍作停顿

            print(f"共获取 {len(trades)} 条成交记录")
            return pd.DataFrame(trades)

        except BinanceAPIException as e:
            print(f"获取成交记录失败: {e.code} - {e.message}")
            return None
        except Exception as e:
            print(f"异常: {str(e)}")
            return None

    # 以下方法保持不变（get_balance_changes/export_to_csv/display_summary）
    def get_balance_changes(self):
        """获取资产变动记录(基于成交记录推导)"""
        print("\n==== 计算资产变动记录 ====")
        trades_df = self.get_trade_history()
        if trades_df is None or trades_df.empty:
            return None

        changes = []
        trades_df = trades_df.sort_values(by="成交时间")

        for _, trade in trades_df.iterrows():
            base_asset = trade['交易对'][:-4]
            quote_asset = trade['交易对'][-4:]

            if trade['方向'] == "买入":
                changes.append({
                    "记录类型": "资产变动",
                    "时间": trade['成交时间'],
                    "资产": base_asset,
                    "变动类型": "增加",
                    "变动数量": trade['成交数量'],
                    "关联成交ID": trade['成交ID']
                })
                changes.append({
                    "记录类型": "资产变动",
                    "时间": trade['成交时间'],
                    "资产": quote_asset,
                    "变动类型": "减少",
                    "变动数量": trade['成交金额'],
                    "关联成交ID": trade['成交ID']
                })
            else:
                changes.append({
                    "记录类型": "资产变动",
                    "时间": trade['成交时间'],
                    "资产": base_asset,
                    "变动类型": "减少",
                    "变动数量": trade['成交数量'],
                    "关联成交ID": trade['成交ID']
                })
                changes.append({
                    "记录类型": "资产变动",
                    "时间": trade['成交时间'],
                    "资产": quote_asset,
                    "变动类型": "增加",
                    "变动数量": trade['成交金额'],
                    "关联成交ID": trade['成交ID']
                })

            changes.append({
                "记录类型": "资产变动",
                "时间": trade['成交时间'],
                "资产": trade['手续费资产'],
                "变动类型": "减少",
                "变动数量": trade['手续费'],
                "关联成交ID": trade['成交ID']
            })

        print(f"共生成 {len(changes)} 条资产变动记录")
        return pd.DataFrame(changes)

    def export_to_csv(self, dataframes):
        if not EXPORT_CSV:
            return

        try:
            with open(CSV_PATH, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["交易历史记录", f"生成时间: {datetime.now().strftime(self._time_format)}"])
                writer.writerow(["环境", "模拟网" if USE_TESTNET else "真实网"])
                writer.writerow(["时间范围", f"{START_DATE} 至 {END_DATE or '现在'}"])
                writer.writerow([])

                for df in dataframes:
                    if df is not None and not df.empty:
                        writer.writerow([f"{df.iloc[0]['记录类型']}记录"])
                        writer.writerow(df.columns.tolist())
                        for _, row in df.iterrows():
                            writer.writerow(row.tolist())
                        writer.writerow([])

            print(f"\n✅ 历史记录已导出至: {CSV_PATH}")
        except Exception as e:
            print(f"导出CSV失败: {str(e)}")

    def display_summary(self, orders_df, trades_df, changes_df):
        print("\n" + "=" * 80)
        print("交易历史记录摘要")
        print("=" * 80)

        if orders_df is not None and not orders_df.empty:
            print("\n最近5条挂单记录:")
            print(orders_df[['订单ID', '交易对', '方向', '状态', '提交时间']].head().to_string(index=False))

        if trades_df is not None and not trades_df.empty:
            print("\n最近5条成交记录:")
            print(trades_df[['成交ID', '交易对', '方向', '成交价格', '成交数量', '成交时间']].head().to_string(
                index=False))

        if changes_df is not None and not changes_df.empty:
            print("\n最近5条资产变动记录:")
            print(changes_df[['时间', '资产', '变动类型', '变动数量']].head().to_string(index=False))

        print("\n" + "=" * 80)


def main():
    mode = "模拟" if USE_TESTNET else "真实"
    print(f"交易历史记录查询工具 [{mode}环境]")
    print(f"查询范围: {START_DATE} 至 {END_DATE or '现在'}{f' | 交易对: {SYMBOL}' if SYMBOL else ''}\n")

    try:
        recorder = TradeHistoryRecorder()
    except Exception as e:
        print(f"初始化失败: {e}")
        return

    orders_df = recorder.get_historical_orders()
    trades_df = recorder.get_trade_history()
    changes_df = recorder.get_balance_changes()

    recorder.display_summary(orders_df, trades_df, changes_df)
    recorder.export_to_csv([orders_df, trades_df, changes_df])

    print("\n查询完成")


if __name__ == "__main__":
    main()
