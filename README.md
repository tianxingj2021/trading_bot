# aster-bot Python版本

[English README](README_en.md)

## 项目简介

aster-bot Python版本是一个用于在 AsterDex 交易所进行自动化交易和监控的机器人。项目支持多种自动化交易策略，包括趋势策略和做市策略，适用于数字货币量化交易、套利等场景。

**使用我的邀请链接注册获取 20%手续费优惠+额外积分奖励：[asterdex](https://www.asterdex.com/en/referral/375926)**

## 项目原理

本项目通过调用 AsterDex 的 API，实现以下核心功能：

- 实时监听行情：通过 WebSocket 获取交易对的最新价格和盘口深度。
- 自动化下单：根据预设策略，自动在 AsterDex 上进行买入、卖出操作。
- 策略执行：支持自定义交易策略，如价格差套利、趋势跟踪、做市等。
- 风控与日志：内置基础风控逻辑，记录所有操作日志，便于追踪和复盘。

API 文档参考：
- [AsterDex API 文档（中文）](https://github.com/asterdex/api-docs/blob/master/aster-finance-api_CN.md)
- [Bitget API 文档（中文）](https://www.bitget.com/zh-CN/api-doc/)

## 安装与运行

### 依赖环境

- Python 3.8 及以上
- pip 包管理器

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

请在 `.env` 文件中配置相关参数，例如 API Key、Secret、监听的交易对等。可参考 `env.example` 文件。

```env
BITGET_API_KEY=你的Bitget_API_Key
BITGET_SECRET=你的Bitget_Secret
ASTER_API_KEY=你的AsterDex_API_Key
ASTER_API_SECRET=你的AsterDex_API_Secret
# 其他配置项
```

### 启动机器人

#### 1. 启动趋势策略（trendV2）

趋势策略基于SMA30均线突破，自动判断做多/做空并动态管理止损止盈。

```bash
python trend_v2.py
```

**trendV2 主要优势：**
- 多类型订单锁，防止并发下单导致的风控问题
- 止损、追踪止盈、盈利后自动移动止损等高级风控
- 实时行情快照与订单状态追踪，自动撤销无效挂单
- 策略逻辑更清晰，日志输出更详细
- 兼容原有 SMA30 趋势突破逻辑，易于迁移

#### 2. 启动做市策略（maker）

做市策略自动在盘口挂双边单，成交后自动只挂平仓方向单，并带有风控止损。

```bash
python maker.py
```

#### 3. 启动双交易所对冲策略(bitget/aster)

```bash
python cli.py start
```

### 运行测试

```bash
python -m pytest tests/
```

## 主要文件说明

- `bot.py`：套利机器人逻辑，包含行情监听、下单、策略等核心功能。
- `trend_v2.py`：趋势策略，基于SMA30均线突破自动做多/做空，支持动态止损止盈。
- `maker.py`：做市策略，自动在盘口挂单，成交后只挂平仓方向单，带风控止损。
- `config.py`：配置文件，交易参数。
- `exchanges/aster.py`：AsterDex交易所API封装。
- `utils/`：工具函数目录。
  - `helper.py`：辅助函数，如获取持仓、计算SMA等。
  - `log.py`：日志工具，格式化输出。
  - `order.py`：订单工具，下单、撤单等操作。

## 策略说明

### 1. 趋势策略（trendV2）

- 实时监听盘口和价格，计算SMA30均线。
- 价格上穿SMA30时自动做多，下穿时自动做空。
- 持仓后自动挂止损单和动态止盈单，支持盈利后移动止损。
- 支持风控，亏损超限自动平仓。
- 控制台实时输出当前状态、持仓、累计收益和最近交易记录。

### 2. 做市策略（maker）

- 无持仓时自动在盘口挂买一/卖一双边单，成交后只挂平仓方向单。
- 自动撤销非平仓方向挂单，保证风控。
- 持仓亏损超限时自动强制平仓。
- 实时输出订单状态、持仓变化和盈亏情况。

### 3. 对冲策略 (bot)

- 在bitget和asterdex上同时进行交易，通过价格差进行对冲。
- 根据价格差自动在bitget和asterdex上进行买入和卖出操作。

## CLI命令

```bash
# 启动套利机器人
python cli.py start

# 查看历史记录
python cli.py log

# 重置统计数据
python cli.py reset
```

## 使用方法

1. 配置好 API 密钥等参数。
2. 选择合适的策略脚本（trend_v2.py 或 maker.py）启动机器人。
3. 观察日志输出，确认连接和策略运行正常。
4. 如需自定义策略，可在对应 py 文件中修改逻辑。
5. 运行测试脚本，确保功能正常。

## 注意事项

- 请妥善保管 API 密钥，避免泄露。
- 机器人涉及真实资金操作，请先在测试环境验证策略安全性。
- 参考官方 API 文档，确保接口调用方式正确。
- 建议在云服务器或本地稳定网络环境下运行。

## 与原TypeScript版本的区别

1. **语言差异**：使用Python重写，语法更简洁易读
2. **异步处理**：使用asyncio进行异步编程，提高性能
3. **依赖管理**：使用pip和requirements.txt管理依赖
4. **界面优化**：使用rich库提供更美观的命令行界面
5. **错误处理**：增强了异常处理和错误恢复机制

## 开发计划

- [ ] 添加更多技术指标支持
- [ ] 实现回测功能
- [ ] 添加Web界面
- [ ] 支持更多交易所
- [ ] 优化性能和稳定性

---

如需更详细的说明或有其他定制需求，请补充具体问题！ 