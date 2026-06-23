import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_percentage_error
from datetime import datetime
import market_data_fetcher  # 自定义的分钟K线数据查询模块
import os
import pickle  # 用于保存scaler

# ========================
# 模型控制参数 - 直接在这里设置
# ========================
MODEL_PATH = "分钟模型.pth"
SCALER_PATH = "分钟标准化.pkl"
USE_EXISTING_MODEL = 0 # 核心控制参数：1 =使用已有模型，0=训练新模型

# ========================
# 参数配置区 - 优化以提高速度
# ========================
# 在参数配置区添加以下参数
# 系统参数
USE_VARIANCE_ADJUSTMENT = True  # 是否启用方差调整功能
VARIANCE_HISTORY_MULTIPLIER = 5  # 方差计算的历史数据倍数
# 数据获取与处理参数
TIMESTAMP_COL = 0  # 时间戳列索引
PRICE_COL = 1  # 价格列索引（要预测的目标列）
DATA_SAMPLE_RATE = 1  # 数据采样率，1=全量，2=每2条取1条

# 模型训练参数
SEQ_LENGTH = 180  # 用于预测的历史序列长度，建议小于kk的0.1
HIDDEN_SIZE = 80  # LSTM隐藏层大小（多变量适当增大）
NUM_LAYERS = 1  # LSTM层数
EPOCHS = 50  # 训练轮数
LEARNING_RATE = 0.001  # 学习率
TEST_SIZE = 0.15  # 测试集比例
BATCH_SIZE = 64  # 批次大小

# 策略参数
PRICE_RANGE_RATIO = 0.30  # 历史类似情况的价格波动范围比例
PREDICTION_STEPS = 60  # 预测未来的时间步数，建议小于kk的0.1
LOOKAHEAD_STEPS = 60  # 判断买入是否可能成交的未来时间步数，建议小于kk的0.1
WEIGHT_HISTORY = 0.7  # 历史数据在综合评分中的权重
WEIGHT_PREDICTION = 0.3  # 预测结果在综合评分中的权重
BUY_RATIO = 0.999  # 买入价相对于当前价格的比例
SELL_RATIO = 1.002  # 卖出价相对于买入价的比例
DECISION_THRESHOLD = 0.5  # 决策阈值（综合评分超过此值则建议执行）
# ========================
# 设备配置 - 自动检测并使用GPU
# ========================
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"\n使用设备: {device}")
if torch.cuda.is_available():
    print(f"GPU名称: {torch.cuda.get_device_name(0)}")
    print(f"GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1024 ** 3:.2f} GB")

# ========================
# 数据获取与准备
# ========================

# 获取分钟K线数据
kk = market_data_fetcher.fetch_minute_kline_data()
# 转换为DataFrame
kk = pd.DataFrame(kk)

# 对数据进行下采样，减少数据量
if DATA_SAMPLE_RATE > 1 and len(kk) > 0:
    kk = kk.iloc[::DATA_SAMPLE_RATE].reset_index(drop=True)
    print(f"数据已下采样，保留 {100 / DATA_SAMPLE_RATE}% 的数据点")

# 重命名时间戳和价格列以便于引用
column_mapping = {
    TIMESTAMP_COL: '时间戳',
    PRICE_COL: '开盘价'  # 预测目标列
}
kk = kk.rename(columns=column_mapping)

# 确保时间戳格式正确
kk['时间戳'] = pd.to_datetime(kk['时间戳'])

# 打印数据信息，确认结构
print("\n获取的K线数据:")
print(kk.head())
print(f"数据形状: {kk.shape}")
print(f"数据列名: {kk.columns.tolist()}")

# 设置随机种子，确保结果可复现
torch.manual_seed(42)
np.random.seed(42)
if torch.cuda.is_available():
    torch.cuda.manual_seed(42)

if USE_EXISTING_MODEL == 0 :
    USE_EXISTING_MODEL = False
else:
    USE_EXISTING_MODEL = True
# 检查模型是否存在
model_exists = os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH)

# 自动处理模型不存在的情况
if USE_EXISTING_MODEL and not model_exists:
    print("警告：指定使用已有模型，但未找到模型文件，将自动训练新模型")
    USE_EXISTING_MODEL = False
elif USE_EXISTING_MODEL:
    print(f"将使用已存在的模型：{MODEL_PATH}")
else:
    print("将训练新模型（如需使用已有模型，请将USE_EXISTING_MODEL设为True）")

# ========================
# 模型定义与工具函数
# ========================

class PricePredictor(nn.Module):
    """多变量LSTM模型用于价格预测"""

    def __init__(self, input_size, hidden_size=HIDDEN_SIZE,
                 output_size=1, num_layers=NUM_LAYERS):
        super(PricePredictor, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.fc(out[:, -1, :])  # 只关注最后一个时间步的输出
        return out


def create_sequences(data, seq_length=SEQ_LENGTH):
    """创建用于训练的多变量序列数据"""
    n = data.shape[0]
    if n <= seq_length:
        return np.array([]), np.array([])

    # 创建序列索引
    indices = np.arange(n - seq_length)[:, None] + np.arange(seq_length + 1)
    sequences = data[indices]

    # 分割输入和目标（目标是开盘价）
    X = sequences[:, :-1, :]  # 所有特征的历史序列
    y = sequences[:, -1, 0]  # 目标是下一个时间步的开盘价（假设开盘价是标准化后的第一列）

    return X, y


def train_model(X_train, y_train, input_size, epochs=EPOCHS, lr=LEARNING_RATE, batch_size=BATCH_SIZE):
    """训练多变量价格预测模型"""
    # 初始化模型并移动到指定设备
    model = PricePredictor(input_size=input_size).to(device)
    criterion = nn.MSELoss().to(device)  # 使用均方误差损失函数
    optimizer = optim.Adam(model.parameters(), lr=lr)  # 使用Adam优化器

    # 转换为PyTorch张量并移动到指定设备
    X_train_tensor = torch.FloatTensor(X_train).to(device)  # 多变量不需要再增加维度
    y_train_tensor = torch.FloatTensor(y_train).unsqueeze(1).to(device)

    # 创建数据集和数据加载器，支持批次训练
    dataset = torch.utils.data.TensorDataset(X_train_tensor, y_train_tensor)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=False)

    # 训练模型
    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        # 启用CUDA自动混合精度训练（如果可用）
        scaler = torch.amp.GradScaler('cuda') if torch.cuda.is_available() else None

        for batch_X, batch_y in dataloader:
            optimizer.zero_grad()  # 清零梯度

            if scaler:
                # 混合精度训练
                with torch.amp.autocast('cuda'):
                    outputs = model(batch_X)
                    loss = criterion(outputs, batch_y)

                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                # 标准训练
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

            total_loss += loss.item()

        # 每10个epoch打印一次平均损失
        if (epoch + 1) % 10 == 0:
            avg_loss = total_loss / len(dataloader)
            print(f'Epoch [{epoch + 1}/{epochs}], Average Loss: {avg_loss:.6f}')

    # 保存训练好的模型
    torch.save(model.state_dict(), MODEL_PATH)
    print(f"模型已保存到 {MODEL_PATH}")

    return model


def load_model(input_size):
    """加载已训练好的模型"""
    model = PricePredictor(input_size=input_size).to(device)
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    model.eval()  # 设置为评估模式
    return model


def predict_future_prices(model, last_sequence, n_steps=PREDICTION_STEPS):
    """批量预测未来价格，多变量版本"""
    model.eval()  # 切换到评估模式

    predictions = []
    current_sequence = last_sequence.copy()  # 复制最后一个序列作为初始输入

    with torch.no_grad():  # 不计算梯度，节省内存
        for _ in range(n_steps):
            # 转换为张量并移动到设备
            input_tensor = torch.FloatTensor(current_sequence).unsqueeze(0).to(device)

            # 预测下一个时间步的开盘价
            pred = model(input_tensor)
            pred_value = pred.item()
            predictions.append(pred_value)

            # 更新序列：移除最旧数据，添加最新预测（只更新开盘价，其他特征使用最后已知值）
            new_sequence = np.roll(current_sequence, -1, axis=0)

            # 更新最后一个时间步的数据
            # 开盘价使用预测值，其他特征使用最后已知值
            new_sequence[-1, 0] = pred_value  # 开盘价（预测值）
            if new_sequence.shape[1] > 1:
                new_sequence[-1, 1:] = current_sequence[-1, 1:]  # 其他特征沿用最后值

            current_sequence = new_sequence

    # 清理内存
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return predictions


def analyze_strategy(kk):
    """综合分析策略是否应该执行，多变量版本"""
    # 1. 数据准备与预处理
    kk_sorted = kk.sort_values('时间戳').reset_index(drop=True)  # 按时间排序

    # 提取特征（排除时间戳），确保开盘价是第一列
    feature_columns = ['开盘价'] + [col for col in kk_sorted.columns if col not in ['时间戳', '开盘价']]

    # 只选择数值型列，排除非数值数据（修复Timestamp错误的关键）
    numeric_features = kk_sorted[feature_columns].select_dtypes(include=[np.number])
    features = numeric_features.values  # 所有数值特征，开盘价在第一列
    NUM_FEATURES = features.shape[1]  # 实际使用的特征数量
    print(f"实际使用的数值特征数量: {NUM_FEATURES}")

    # 数据归一化（对所有特征进行标准化）
    if USE_EXISTING_MODEL:
        # 加载已保存的scaler
        with open(SCALER_PATH, 'rb') as f:
            scaler = pickle.load(f)
        scaled_features = scaler.transform(features)
    else:
        # 新建scaler并拟合所有特征
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_features = scaler.fit_transform(features)
        # 保存scaler
        with open(SCALER_PATH, 'wb') as f:
            pickle.dump(scaler, f)
        print(f"数据标准化器已保存到 {SCALER_PATH}")

    # 2. 准备训练数据和模型
    model = None
    # 用于存储测试集的预测结果和真实值，以便计算准确度
    test_predictions = None
    y_test = None

    if USE_EXISTING_MODEL:
        # 加载已有模型
        model = load_model(input_size=NUM_FEATURES)
        print("已加载已有模型进行预测")

        # 为已训练模型也计算准确度，需要准备测试数据
        X, y = create_sequences(scaled_features)
        if len(X) > 0 and len(y) > 0:
            _, X_test, _, y_test = train_test_split(X, y, test_size=TEST_SIZE, shuffle=False)
    else:
        # 准备训练数据（多变量序列）
        X, y = create_sequences(scaled_features)  # 创建多变量序列数据

        if len(X) == 0 or len(y) == 0:
            raise ValueError("数据量不足，无法创建训练序列")

        # 划分训练集和测试集（不打乱顺序，保持时间序列特性）
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, shuffle=False)

        # 3. 训练模型
        print("\n训练多变量价格预测模型...")
        model = train_model(X_train, y_train, input_size=NUM_FEATURES)

        # 4. 评估模型在测试集上的表现
        model.eval()
        with torch.no_grad():
            # 创建测试集数据加载器
            X_test_tensor = torch.FloatTensor(X_test).to(device)
            y_test_tensor = torch.FloatTensor(y_test).unsqueeze(1).to(device)

            test_dataset = torch.utils.data.TensorDataset(X_test_tensor, y_test_tensor)
            test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=BATCH_SIZE)

            total_test_loss = 0.0
            test_predictions = []

            for batch_X, batch_y in test_loader:
                batch_preds = model(batch_X)
                test_predictions.extend(batch_preds.cpu().numpy().flatten())
                loss = nn.MSELoss()(batch_preds, batch_y)
                total_test_loss += loss.item()

            avg_test_loss = total_test_loss / len(test_loader)
            print(f"测试集平均MSE损失: {avg_test_loss:.6f}")

    # 计算并打印模型准确度指标
    print("\n" + "=" * 50)
    print("模型准确度评估:")

    # 如果没有测试集预测结果，生成它们
    if test_predictions is None and y_test is not None and len(y_test) > 0:
        with torch.no_grad():
            X_test_tensor = torch.FloatTensor(X_test).to(device)
            test_preds_tensor = model(X_test_tensor)
            test_predictions = test_preds_tensor.cpu().numpy().flatten()

    if test_predictions is not None and y_test is not None and len(y_test) > 0:
        # 反归一化以计算实际价格的误差
        # 准备反归一化数组
        dummy_test_preds = np.zeros((len(test_predictions), NUM_FEATURES))
        dummy_test_preds[:, 0] = test_predictions
        actual_test_preds = scaler.inverse_transform(dummy_test_preds)[:, 0]

        dummy_test_actual = np.zeros((len(y_test), NUM_FEATURES))
        dummy_test_actual[:, 0] = y_test
        actual_test_actual = scaler.inverse_transform(dummy_test_actual)[:, 0]

        # 计算R²决定系数 (越接近1越好)
        r2 = r2_score(actual_test_actual, actual_test_preds)

        # 计算平均绝对百分比误差 (越低越好)
        # 避免除以零，添加微小值
        mape = mean_absolute_percentage_error(actual_test_actual, actual_test_preds) * 100

        print(f"R²决定系数: {r2:.4f} (1.0表示完美预测)")
        print(f"平均绝对百分比误差(MAPE): {mape:.2f}% (0%表示完美预测)")

        # 计算价格方向预测准确率 (上涨/下跌趋势预测准确率)
        actual_changes = np.sign(np.diff(actual_test_actual))
        predicted_changes = np.sign(np.diff(actual_test_preds))
        direction_accuracy = np.mean(actual_changes == predicted_changes) * 100
        print(f"价格方向预测准确率: {direction_accuracy:.2f}%")
    else:
        print("无法计算准确度指标: 测试数据不足或未生成预测结果")
    print("=" * 50 + "\n")

    # 5. 获取当前市场数据
    latest_data = kk_sorted.iloc[-1]  # 最新的一条数据
    current_time = latest_data['时间戳']
    current_price = latest_data['开盘价']

    # 计算买入价和卖出价
    buy_price = current_price * BUY_RATIO
    sell_price = buy_price * SELL_RATIO
    target_return = (sell_price / buy_price - 1) * 100  # 计算预期收益率

    # 6. 预测未来价格
    last_sequence = scaled_features[-SEQ_LENGTH:]  # 最新的序列数据（包含所有特征）
    future_scaled_preds = predict_future_prices(model, last_sequence,
                                                max(PREDICTION_STEPS, LOOKAHEAD_STEPS))

    # 准备反归一化所需的数组（只关心开盘价的预测）
    dummy_array = np.zeros((len(future_scaled_preds), NUM_FEATURES))
    dummy_array[:, 0] = future_scaled_preds  # 只有开盘价使用预测值

    # 将预测结果反归一化到原始价格范围
    future_price_preds = scaler.inverse_transform(dummy_array)[:, 0]  # 只取开盘价
    # 在 future_price_preds 生成之后添加以下代码
    if USE_VARIANCE_ADJUSTMENT:
        # 计算历史价格的方差并生成新的随机预测变量
        history_length = SEQ_LENGTH * VARIANCE_HISTORY_MULTIPLIER  # 基于参数的历史数据长度
        if len(kk_sorted) >= history_length:
            # 获取历史价格数据
            historical_prices = kk_sorted['开盘价'].iloc[-history_length:].values
            historical_mean = np.mean(historical_prices)
            historical_std = np.std(historical_prices)

            # 基于历史均值和方差生成随机预测
            # 使用与 future_price_preds 相同的长度
            future_price_preds = np.random.normal(historical_mean, historical_std, len(future_price_preds))
            print(f"基于方差调整:")
            print(f"  历史{history_length}个单位价格的均值: {historical_mean:.2f}")
            print(f"  历史{history_length}个单位价格的标准差: {historical_std:.2f}")
            print(f"  随机生成的预测价格序列: {[f'{p:.2f}' for p in future_price_preds[:10]]}...")

            # 可以将 random_predictions 用于后续的策略分析
            # 例如与模型预测结果进行加权平均或其他组合方式
        else:
            print(f"历史数据不足{history_length}个单位，无法计算历史方差")
    # 7. 分析买入可能性和卖出可能性
    # 7.1 分析买入是否可能成交
    future_prices_lookahead = future_price_preds[:LOOKAHEAD_STEPS]
    buy_conditions = future_prices_lookahead <= buy_price
    buy_possible = np.any(buy_conditions)
    predicted_buy_prob = np.mean(buy_conditions)

    # 7.2 分析卖出是否可能
    predicted_sell_prob = 0
    if buy_possible:
        # 找到第一个可能买入的位置
        first_buy_idx = np.argmax(buy_conditions)

        if first_buy_idx < len(future_price_preds):
            # 只考虑买入后的价格走势
            prices_after_buy = future_price_preds[first_buy_idx:]
            sell_conditions = prices_after_buy >= sell_price
            predicted_sell_prob = np.mean(sell_conditions)

    # 综合预测成功率
    predicted_success_prob = predicted_buy_prob * predicted_sell_prob

    # 8. 历史类似情况分析
    price_range = current_price * PRICE_RANGE_RATIO  # 价格波动范围

    # 使用向量化操作筛选历史数据
    price_mask = (kk_sorted['开盘价'] >= current_price - price_range) & \
                 (kk_sorted['开盘价'] <= current_price + price_range) & \
                 (kk_sorted['时间戳'] < current_time)

    similar_historical_data = kk_sorted[price_mask]
    total_similar = len(similar_historical_data)

    historical_success_rate = 0
    historical_buy_prob = 0
    buy_count = 0
    successful_count = 0

    if total_similar > 0:
        # 向量化计算历史买入价和卖出价
        hist_buy_prices = similar_historical_data['开盘价'] * BUY_RATIO
        hist_sell_prices = hist_buy_prices * SELL_RATIO

        # 提取所有开盘价用于快速查询
        all_open_prices = kk_sorted['开盘价'].values

        # 批量处理历史数据分析
        for idx, hist_buy_price, hist_sell_price in zip(
                similar_historical_data.index, hist_buy_prices, hist_sell_prices):

            # 计算未来数据的索引范围
            end_idx = min(idx + 1 + LOOKAHEAD_STEPS, len(all_open_prices))
            future_prices = all_open_prices[idx + 1:end_idx]

            # 检查是否能以目标价买入
            if np.any(future_prices <= hist_buy_price):
                buy_count += 1

                # 找到第一个买入点
                buy_positions = np.where(future_prices <= hist_buy_price)[0]
                if len(buy_positions) > 0:
                    first_buy_pos = idx + 1 + buy_positions[0]

                    # 检查买入后是否能达到卖出价
                    if first_buy_pos < len(all_open_prices):
                        after_buy_prices = all_open_prices[first_buy_pos:]
                        if np.any(after_buy_prices >= hist_sell_price):
                            successful_count += 1

        # 计算历史统计数据
        historical_buy_prob = (buy_count / total_similar) * 100
        historical_success_rate = (successful_count / total_similar) * 100

    # 9. 综合决策
    combined_score = (historical_success_rate / 100 * WEIGHT_HISTORY +
                      predicted_success_prob * WEIGHT_PREDICTION)

    # 10. 输出结果
    print("\n" + "=" * 50)
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"当前时间: {current_time}")
    print(f"当前价格: {current_price:.2f}")
    print(f"目标买入价: {buy_price:.2f} ({BUY_RATIO * 100:.1f}% of current)")
    print(f"目标卖出价: {sell_price:.2f} ({SELL_RATIO * 100:.1f}% of buy price)")
    print(f"预期收益率: {target_return:.2f}%")
    print("-" * 50)
    print(f"买入可能性分析:")
    print(f"  预测未来{LOOKAHEAD_STEPS}步内买入成功率: {predicted_buy_prob:.2%}")
    print(f"  历史类似情况下买入成功率: {historical_buy_prob:.2f}% ({buy_count}/{total_similar})")
    print("-" * 50)
    print(f"卖出可能性分析:")
    print(f"  预测买入后卖出成功率: {predicted_sell_prob:.2%}")
    print(f"  历史类似情况下整体成功率: {historical_success_rate:.2f}% ({successful_count}/{total_similar})")
    print("-" * 50)
    print(f"未来价格预测 (接下来{max(PREDICTION_STEPS, LOOKAHEAD_STEPS)}个时间单位):")
    print(f"  预测价格序列: {[f'{p:.2f}' for p in future_price_preds[:10]]}...")  # 只显示前10个预测值
    print(f"  综合预测成功概率: {predicted_success_prob:.2%}")
    print("-" * 50)
    print(f"综合评分: {combined_score:.2%}")

    # 决策建议
    if combined_score > DECISION_THRESHOLD:
        print("\n决策建议: 建议执行策略")
        confidence = "高" if combined_score > 0.7 else "中" if combined_score > 0.6 else "一般"
        print(f"信心程度: {confidence}")
    else:
        print("\n决策建议: 不建议执行策略")
        confidence = "高" if combined_score < 0.3 else "中" if combined_score < 0.4 else "一般"
        print(f"不执行信心程度: {confidence}")

    # 清理GPU内存
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return {
        'current_price': current_price,
        'buy_price': buy_price,
        'sell_price': sell_price,
        'predicted_buy_prob': predicted_buy_prob,
        'predicted_sell_prob': predicted_sell_prob,
        'historical_buy_prob': historical_buy_prob,
        'historical_success_rate': historical_success_rate,
        'predicted_success_prob': predicted_success_prob,
        'combined_score': combined_score,
        'should_execute': combined_score > DECISION_THRESHOLD,
        # 添加准确度指标到返回结果
        'r2_score': r2 if 'r2' in locals() else None,
        'mape': mape if 'mape' in locals() else None,
        'direction_accuracy': direction_accuracy if 'direction_accuracy' in locals() else None
    }


if __name__ == "__main__":
    result = analyze_strategy(kk)
