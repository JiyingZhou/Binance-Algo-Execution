# Binance-Algo-Trade-Suite
Lightweight Binance spot algorithmic trading infrastructure featuring OCO risk management and robust API resilience. | 轻量级币安现货自动化量化执行框架，内置 OCO 智能风控与高可用 API 处理机制。

# 🚀 Binance-Algo-Execution

**Language / 语言导航**
* [English Documentation](#english-documentation)
* [中文文档](#中文文档)

---

## English Documentation

### 📖 Overview
**Binance-Algo-Execution** is a lightweight, robust, and highly focused infrastructure for automated spot trading on Binance. Stripped of overly complex predictive models, this framework is designed purely for **Execution Safety**, **API Resilience**, and **Strict Risk Management**. It provides a reliable foundation for any quantitative strategy looking to interface safely with the Binance Spot market.

### ✨ Core Features
* **🛡️ Security First:** Strict separation of sensitive API keys using environment variables (`.env`). Built-in proxy configuration support and SSL verification handling for restricted network environments.
* **🎯 Precision & Asset Handling:** Dynamic retrieval of Binance exchange symbol filters (LOT_SIZE, PRICE_FILTER, minQty). Automatic float rounding to match strict API precision requirements, preventing order rejections. 
* **⚖️ Strict Risk Control:** Asymmetric risk management using OCO (One-Cancels-the-Other) orders. Buy orders immediately trigger Take-Profit and Stop-Loss limits, ensuring zero naked exposure.
* **⚙️ High Resilience & Throttling:** Pagination logic and timestamp anchoring for fetching historical k-line data. Built-in exponential backoff, request throttling, and automatic client re-initialization to handle API rate limits and network drops safely.

### 📂 Architecture
* `auth_client.py`: Singleton client initialization and secure credential management.
* `portfolio_manager.py`: Real-time asset scanning, precision formatting, and multi-currency valuation.
* `market_data_fetcher.py`: High-availability market data fetcher with pagination and retry mechanisms.
* `execution_engine.py`: Core execution engine handling limit orders, OCO routing, and precision rounding.
* `task_scheduler.py`: Scheduled task runner for periodic market scanning and trade execution.

### 🚀 Getting Started

**1. Install Dependencies**
Ensure you have Python 3.8+ installed, then run the following command in your terminal:
```bash
pip install python-binance pandas numpy python-dotenv urllib3
```

**2. Secure Environment Setup (CRITICAL)**
For absolute fund security, **never hardcode your API keys in the scripts.**
Open the file named `Binance_API_KEY and SECRET.env` in the root directory of this project and fill in your Binance credentials:
```ini
# .env file content
BINANCE_API_KEY=your_actual_binance_api_key_here_at_least_50_chars
BINANCE_API_SECRET=your_actual_binance_api_secret_here_at_least_50_chars
```

### 💻 Usage Guide & Configuration

Each module is designed to be run independently. Before running, open the respective `.py` files and adjust the global configuration variables at the top of the scripts.

**A. Run the Automated Trading Daemon (`task_scheduler.py`)**
This is the main entry point for automated trading. It calls `execution_engine.py` based on your specified intervals.
* **Key Parameters to adjust:**
  * `RUN_INTERVAL = 3600` (Time in seconds between each execution cycle).
  * `RUN_ONCE = False` (Set to True if you only want it to run one time without looping).
* **Command:**
```bash
python 定时交易.py
```

**B. Configure the Execution Engine (`execution_engine.py`)**
Before starting the scheduler, configure your trading logic here.
* **Key Parameters to adjust:**
  * `USE_TESTNET = False` (Change to True to use Binance Testnet for paper trading).
  * `SYMBOL = "BNBUSDT"` (Your target trading pair).
  * `PRICE_MODE = "percentage"` (Choose "fixed" for absolute prices or "percentage" to calculate dynamically from the current market price).
  * `PROFIT_RATIO = 0.015` / `LOSS_RATIO = 0.009` (Your OCO Stop-Loss / Take-Profit margins).

**C. Fetch Historical Market Data (`market_data_fetcher.py`)**
Downloads massive amounts of minute-level candlesticks into a clean, deduplicated CSV file.
* **Key Parameters to adjust:**
  * `MAX_RECORD_COUNT = 10000` (Total number of K-lines to download).
  * `SYMBOL = "BNBUSDT"` (Target pair for the data).
* **Command:**
```bash
python 市场数据查询.py
```

**D. Check Real-Time Portfolio (`portfolio_manager.py`)**
Outputs a beautifully formatted terminal dashboard showing your spot assets, frozen balances, and fiat valuations (USD/CNY).
* **Key Parameters to adjust:**
  * `PRIORITY_ASSETS = ["USDT", "BTC", "ETH", "BNB"]` (Assets to pin at the top of the table).
* **Command:**
```bash
python 查询资产.py
```

---

## 中文文档

### 📖 项目概述
**Binance-Algo-Execution** 是一个轻量、极简且高度聚焦的币安现货自动化交易底层框架。本项目剥离了复杂的预测模型，专注于**执行安全**、**API 高可用性**以及**严格的风控管理**，旨在为各类量化策略提供一个极其稳定、容错极高的实盘接入通道。

### ✨ 核心特性
* **🛡️ 安全至上:** 强制通过 `.env` 环境变量管理敏感 API Key，实现代码与密钥的物理隔离。内置代理配置选项与 SSL 验证处理，适配复杂或受限的网络环境。
* **🎯 严谨的精度与资产计算:** 动态获取交易所标的物规则（LOT_SIZE, PRICE_FILTER, minQty）。自动进行浮点数精度截断与对齐，彻底杜绝因精度溢出导致的 API 拒单。
* **⚖️ 闭环风控体系:** 基于 OCO (One-Cancels-the-Other) 订单机制构建的不对称风控。买单成交后瞬间下发止盈限价与止损单，拒绝任何形式的裸量化敞口。
* **⚙️ 容错与防熔断机制:** 采用时间戳锚定与分页逻辑拉取 K 线数据，支持大规模历史数据获取。内置最大重试次数、API 节流休眠（Throttling）以及客户端断线重连机制，从容应对网络抖动。

### 📂 架构设计
* `auth_client.py`: 负责单例客户端初始化与底层凭证安全管理。
* `portfolio_manager.py`: 负责实时资产盘点、精度转换及多币种净值计算。
* `market_data_fetcher.py`: 高可用行情拉取模块，内置分页与重试逻辑。
* `execution_engine.py`: 核心执行引擎，负责限价单生成、OCO 路由及全流程精度控制。
* `task_scheduler.py`: 守护进程模块，提供周期性扫描与单次运行控制。

### 🚀 快速开始

**1. 安装运行依赖**
请确保本地已安装 Python 3.8 或更高版本，并在终端执行以下命令安装必要的三方库：
```bash
pip install python-binance pandas numpy python-dotenv urllib3
```

**2. 配置安全密钥（非常重要）**
为了绝对的资金安全，**切勿在代码中明文写入密钥**。
请在项目根目录下的 `Binance_API_KEY and SECRET.env` 填入你从币安获取的真实密钥：
```ini
# .env 文件内容
BINANCE_API_KEY=你的真实币安API_KEY（长度通常大于50位）
BINANCE_API_SECRET=你的真实币安API_SECRET（长度通常大于50位）
```
### 💻 使用指南与参数配置

本项目的每个模块都可以独立运行。在执行前，请使用编辑器打开对应的 `.py` 文件，根据需求修改代码顶部的**全局配置参数**。

**A. 启动自动化交易守护进程 (`task_scheduler.py`)**
这是自动化交易的总控开关，它会根据你设定的时间周期自动唤醒并执行交易策略。
* **运行前需修改的参数：**
  * `RUN_INTERVAL = 3600`（每次循环运行的时间间隔，单位为秒）。
  * `RUN_ONCE = False`（如果只想运行一次不循环，将其改为 True）。
* **运行命令：**
```bash
python 定时交易.py
```

**B. 配置核心交易引擎 (`execution_engine.py`)**
在启动调度器前，请务必在此文件中配置你的交易标的和风控比例。
* **运行前需修改的参数：**
  * `USE_TESTNET = False`（如果是新手调试，强烈建议改为 True 使用币安模拟盘测试）。
  * `SYMBOL = "BNBUSDT"`（你要交易的具体交易对）。
  * `PRICE_MODE = "percentage"`（定价模式：fixed为固定价格，percentage为按市价折扣的百分比计算）。
  * `PROFIT_RATIO = 0.015` / `LOSS_RATIO = 0.009`（OCO 挂单的止盈和止损比例）。

**C. 拉取历史行情数据 (`market_data_fetcher.py`)**
用于自动处理分页与重试，将海量分钟级 K 线数据导出为本地 CSV 文件供量化回测使用。
* **运行前需修改的参数：**
  * `MAX_RECORD_COUNT = 10000`（你需要拉取的历史 K 线总条数）。
  * `SYMBOL = "BNBUSDT"`（你要拉取数据的交易对）。
* **运行命令：**
```bash
python 市场数据查询.py
```

**D. 唤出资产盘点看板 (`portfolio_manager.py`)**
在终端即时输出排版整齐的现货持仓明细（包括可用、冻结资产），以及实时的 USD 和 CNY 净值估算。
* **运行前需修改的参数：**
  * `PRIORITY_ASSETS = ["USDT", "BTC", "ETH", "BNB"]`（将你最关心的资产名称放在这里，打印时会自动置顶）。
* **运行命令：**
```bash
python 查询资产.py
```
