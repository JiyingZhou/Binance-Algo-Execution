# Binance-Algo-Trade-Suite
Lightweight Binance spot algorithmic trading infrastructure featuring OCO risk management and robust API resilience. | 轻量级币安现货自动化量化执行框架，内置 OCO 智能风控与高可用 API 处理机制。
# Binance-Algo-Execution | 币安现货自动化量化执行系统

🌍 Choose your language: [English](#english-version) | [中文版](#chinese-version)

---

## English Version

### 📖 Overview
**Binance-Algo-Execution** is a lightweight, robust, and highly focused infrastructure for automated spot trading on Binance. Stripped of overly complex predictive models, this framework is designed purely for **Execution Safety, API Resilience, and Strict Risk Management**. It provides a reliable foundation for any quantitative strategy looking to interface safely with the Binance Spot market.

### ✨ Core Features

* **🛡️ Security First (`auth_client.py`)**
  * Strict separation of sensitive API keys using environment variables (`.env`).
  * Built-in proxy configuration support and SSL verification handling for restricted network environments.
* **🎯 Precision & Asset Handling (`portfolio_manager.py`, `execution_engine.py`)**
  * Dynamic retrieval of Binance exchange symbol filters (`LOT_SIZE`, `PRICE_FILTER`, `minQty`).
  * Automatic float rounding to match strict API precision requirements, preventing order rejections.
  * Real-time portfolio valuation with fallback exchange rate calculations.
* **⚖️ Strict Risk Control (`execution_engine.py`)**
  * Asymmetric risk management using **OCO (One-Cancels-the-Other)** orders.
  * Buy orders immediately trigger Take-Profit and Stop-Loss limits, ensuring zero naked exposure.
* **⚙️ High Resilience & Throttling (`market_data_fetcher.py`, `task_scheduler.py`)**
  * Pagination logic and timestamp anchoring for fetching historical k-line data.
  * Built-in exponential backoff, request throttling (`time.sleep`), and automatic client re-initialization to handle API rate limits and network drops safely.

### 📂 Architecture

* `auth_client.py`: Singleton client initialization and secure credential management.
* `portfolio_manager.py`: Real-time asset scanning, precision formatting, and multi-currency valuation.
* `market_data_fetcher.py`: High-availability market data fetcher with pagination and retry mechanisms.
* `execution_engine.py`: Core execution engine handling limit orders, OCO routing, and precision rounding.
* `task_scheduler.py`: Scheduled task runner for periodic market scanning and trade execution.

---

## Chinese Version

### 📖 项目概述
**Binance-Algo-Execution** 是一个轻量、极简且高度聚焦的币安现货自动化交易底层框架。本项目剥离了复杂的预测模型，专注于**执行安全、API 高可用性以及严格的风控管理**，旨在为各类量化策略提供一个极其稳定的实盘接入通道。

### ✨ 核心特性

* **🛡️ 安全至上 (`auth_client.py`)**
  * 强制通过 `.env` 环境变量管理敏感 API Key，实现代码与密钥的物理隔离。
  * 内置代理配置选项与 SSL 验证处理，适配复杂或受限的网络环境。
* **🎯 严谨的精度与资产计算 (`portfolio_manager.py`, `execution_engine.py`)**
  * 动态获取交易所标的物规则（`LOT_SIZE`, `PRICE_FILTER`, `minQty`）。
  * 自动进行浮点数精度截断与对齐，彻底杜绝因精度溢出导致的 API 拒单。
  * 实时监控账户持仓，并支持双币种（USD/CNY）资产价值预估与稳定币汇率容错。
* **⚖️ 闭环风控体系 (`execution_engine.py`)**
  * 基于 **OCO (One-Cancels-the-Other)** 订单机制构建的不对称风控。
  * 买单成交后瞬间下发止盈限价与止损单，拒绝任何形式的裸量化敞口。
* **⚙️ 容错与防熔断机制 (`market_data_fetcher.py`, `task_scheduler.py`)**
  * 采用时间戳锚定与分页逻辑拉取 K 线数据，支持大规模历史数据获取。
  * 内置最大重试次数、API 节流休眠（Throttling）以及客户端断线重连机制，从容应对网络抖动和交易所限频。

### 📂 架构设计

* `auth_client.py`: 负责单例客户端初始化与底层凭证安全管理。
* `portfolio_manager.py`: 负责实时资产盘点、精度转换及多币种净值计算。
* `market_data_fetcher.py`: 高可用行情拉取模块，内置分页与重试逻辑。
* `execution_engine.py`: 核心执行引擎，负责限价单生成、OCO 路由及全流程精度控制。
* `task_scheduler.py`: 守护进程模块，提供周期性扫描与单次运行控制。
