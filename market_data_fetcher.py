import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from binance import Client
from auth_client import get_binance_client


def fetch_minute_kline_data():
    # ==============================================
    # 配置参数 - 在此处修改参数
    # ==============================================
    MAX_RECORD_COUNT = 10000  # 要获取的总数据条数
    SYMBOL = "BNBUSDT"  # 交易对
    LIMIT_PER_PAGE = 1000  # 单页最大量（Binance API限制，1-1000）
    MAX_RETRY = 3  # 最大重试次数
    RETRY_INTERVAL = 1.5  # 重试间隔（秒）
    REQUEST_INTERVAL = 0.5  # 增加请求间隔，避免API限制
    TIMEOUT = 10  # 请求超时时间（秒）
    # ==============================================

    # 参数校验
    if not 1 <= LIMIT_PER_PAGE <= 1000:
        print(f"单页数量错误：{LIMIT_PER_PAGE}，必须在1-1000之间")
        return None
    if MAX_RETRY < 1 or RETRY_INTERVAL < 0 or REQUEST_INTERVAL < 0:
        print("参数错误：重试次数必须大于0，时间间隔不能为负")
        return None
    if MAX_RECORD_COUNT < 1:
        print(f"最大记录数必须大于0，当前为：{MAX_RECORD_COUNT}")
        return None

    # 计算需要的总页数
    total_pages = (MAX_RECORD_COUNT + LIMIT_PER_PAGE - 1) // LIMIT_PER_PAGE
    print(f"配置参数：将获取 {MAX_RECORD_COUNT} 条 {SYMBOL} 分钟K线数据，分为 {total_pages} 页获取")

    # 获取Binance客户端
    client = get_binance_client()
    if not client:
        print("登录失败：无法获取Binance客户端")
        return None
    client.session.timeout = TIMEOUT

    # 分页获取K线数据
    all_klines = []
    # 从当前时间开始往前获取
    current_end = int(datetime.now().timestamp() * 1000)
    total_fetched = 0
    page = 1

    print(f"开始获取数据...")

    while page <= total_pages and total_fetched < MAX_RECORD_COUNT:
        # 计算当前页需要获取的数量
        remaining = MAX_RECORD_COUNT - total_fetched
        current_limit = min(LIMIT_PER_PAGE, remaining)

        # 计算当前页的起始时间（往前推current_limit分钟）
        # 增加5分钟缓冲，避免因时间计算误差导致数据重复或遗漏
        current_start = current_end - (current_limit * 60000) - (5 * 60000)

        # 准备请求参数
        params = {
            "symbol": SYMBOL,
            "interval": Client.KLINE_INTERVAL_1MINUTE,
            "limit": current_limit,
            "endTime": current_end,
            "startTime": current_start
        }

        # 带重试机制的API请求
        klines = None
        for attempt in range(MAX_RETRY + 1):
            try:
                klines = client.get_klines(**params)
                break
            except Exception as e:
                if attempt < MAX_RETRY:
                    print(f"请求失败（尝试 {attempt + 1}/{MAX_RETRY + 1}）：{str(e)[:50]}，将重试...")
                    time.sleep(RETRY_INTERVAL)
                    # 重新获取客户端，处理可能的连接问题
                    from auth_client import _global_client
                    _global_client = None
                    client = get_binance_client()
                    client.session.timeout = TIMEOUT
                else:
                    print(f"达到最大重试次数，请求失败：{str(e)[:50]}")
                    return pd.DataFrame() if all_klines else None

        # 处理获取到的数据
        if not klines:
            print("未获取到数据，结束分页请求")
            break

        # 过滤已存在的数据（防重复）
        existing_timestamps = {x[0] for x in all_klines}
        new_klines = [k for k in klines if k[0] not in existing_timestamps]
        all_klines.extend(new_klines)
        total_fetched += len(new_klines)

        print(f"第 {page} 页：获取 {len(new_klines)} 条数据，累计 {total_fetched}/{MAX_RECORD_COUNT} 条")

        # 更新当前结束时间为新获取数据中最早的时间戳
        if new_klines:
            # 使用新获取数据中最早的时间戳作为下一页的结束时间
            current_end = min(k[0] for k in new_klines)
        else:
            # 如果没有获取到新数据，向前推进current_limit分钟
            current_end = current_start - (60000)

        # 检查是否还有更多数据
        if len(klines) < current_limit:
            print(f"已获取所有可用历史数据，共 {total_fetched} 条")
            break

        page += 1
        time.sleep(REQUEST_INTERVAL)

    if not all_klines:
        print("未获取到任何K线数据")
        return None

    # 数据处理
    try:
        kline_matrix = np.array(all_klines, dtype=object)

        # 转换时间列
        timestamps = (kline_matrix[:, 0].astype(float) / 1000).astype('datetime64[s]')
        close_timestamps = (kline_matrix[:, 6].astype(float) / 1000).astype('datetime64[s]')

        # 转换数值列
        numeric_matrix = kline_matrix[:, [1, 2, 3, 4, 5, 7, 8, 9, 10]].astype(float)

        # 创建DataFrame
        df = pd.DataFrame({
            "时间戳": timestamps,
            "开盘价": numeric_matrix[:, 0],
            "最高价": numeric_matrix[:, 1],
            "最低价": numeric_matrix[:, 2],
            "收盘价": numeric_matrix[:, 3],
            "成交量": numeric_matrix[:, 4],
            "收盘时间": close_timestamps,
            "报价成交量": numeric_matrix[:, 5],
            "交易次数": numeric_matrix[:, 6].astype(int),
            "主动买入量": numeric_matrix[:, 7],
            "主动买入额": numeric_matrix[:, 8],
            "忽略字段": kline_matrix[:, 11]
        })

        # 去重并排序
        df = df.drop_duplicates("时间戳").sort_values('时间戳', ascending=False).reset_index(drop=True)
        print(f"数据处理完成：共 {len(df)} 条有效数据")
        return df

    except Exception as e:
        print(f"数据处理出错：{str(e)}")
        return pd.DataFrame(all_klines) if all_klines else None


if __name__ == "__main__":
    df = fetch_minute_kline_data()
    if df is not None and not df.empty:
        print(f"\n最终数据形状：{df.shape}")
        print(f"时间范围：从 {df['时间戳'].min()} 到 {df['时间戳'].max()}")
        filename = "分钟.csv"
        df.to_csv(filename, encoding="utf-8-sig", index=False)
    print(df)