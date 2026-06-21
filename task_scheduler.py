
import time
import execution_engine  # 导入交易模块

# 配置运行间隔（秒），例如300秒=5分钟
RUN_INTERVAL = 3600
# 新增配置：是否只运行一次
RUN_ONCE = False  # 设置为True则只运行一次，False则保持原有周期性运行


def periodic_run():
    print(f"开始周期性运行 | 间隔: {RUN_INTERVAL}秒 | 标的物: {安全交易.SYMBOL}")
    print("=" * 60)

    try:
        while True:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始新一轮运行")

            # 执行交易主逻辑
            try:
                # 初始化交易实例
                trader = 安全交易.ProfitLossTrader()
                安全交易.trader = trader  # 暴露变量供外部访问

                # 执行核心流程
                if trader.get_current_price():
                    buy_price, take_profit, stop_loss = trader.calculate_prices()
                    安全交易.main()  # 执行交易逻辑

                # 可直接访问的变量
                print(f"当前价格: {trader.current_price:.2f} USDT (可外部访问)")

            except Exception as e:
                print(f"本轮运行出错: {str(e)}")

            # 根据RUN_ONCE参数决定是否只运行一次
            if RUN_ONCE:
                print("\n已设置为单次运行模式，程序即将退出")
                break
            else:
                # 固定间隔等待，不计算运行耗时
                print(f"\n本轮结束，将在 {RUN_INTERVAL}秒后再次运行")
                print("-" * 60)
                time.sleep(RUN_INTERVAL)

    except KeyboardInterrupt:
        print("\n用户终止程序")
    finally:
        print("周期性运行结束")


if __name__ == "__main__":
    periodic_run()