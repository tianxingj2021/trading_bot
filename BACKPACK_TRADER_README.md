# EMA趋势策略Backpack实盘交易程序

## 概述

这是一个基于EMA趋势策略的Backpack交易所自动交易程序，使用多时间框架分析进行交易决策。

### 策略逻辑

- **4小时趋势过滤**: 价格位于EMA200上方只做多，下方只做空
- **1分钟入场信号**: EMA13/21/34三条均线金叉/死叉
- **风险控制**: 2ATR倍数止损，2:1盈亏比固定止盈
- **平仓机制**: 止损、止盈、信号平仓

## 文件结构

```
├── ema_trend_backpack_trader.py    # 主交易程序
├── backpack_trader_config.json     # 配置文件
├── start_backpack_trader.sh        # 启动脚本
├── strategies/
│   └── ema_trend_strategy.py       # EMA趋势策略
└── utils/
    └── order_adapter.py            # 订单适配器
```

## 安装和配置

### 1. 快速安装

```bash
# 运行安装脚本
./install_trader.sh
```

### 2. 手动安装

#### 环境要求
- Python 3.7+
- 已配置Backpack API密钥

#### 安装步骤
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements_trader.txt
```

### 2. API密钥配置

在 `config.py` 中配置Backpack API密钥：

```python
BACKPACK_API_KEY = "your_api_key"
BACKPACK_API_SECRET = "your_api_secret"
```

### 3. 配置文件

程序会自动创建默认配置文件 `backpack_trader_config.json`：

```json
{
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "leverage": 50,
  "risk_pct": 0.05,
  "check_interval": 60,
  "atr_period": 14,
  "atr_mult": 2,
  "risk_reward_ratio": 2,
  "max_positions": 3,
  "enable_logging": true,
  "log_file": "backpack_trader.log"
}
```

## 使用方法

### 1. 启动脚本

```bash
# 给启动脚本执行权限
chmod +x start_backpack_trader.sh

# 显示帮助
./start_backpack_trader.sh --help
```

### 2. 命令行参数

```bash
# 测试模式（不实际交易）
python3 ema_trend_backpack_trader.py --test

# 单次执行指定交易对
python3 ema_trend_backpack_trader.py --symbol BTCUSDT

# 显示交易统计
python3 ema_trend_backpack_trader.py --stats

# 实盘交易
python3 ema_trend_backpack_trader.py

# 使用自定义配置文件
python3 ema_trend_backpack_trader.py --config my_config.json
```

### 3. 运行模式

#### 测试模式
```bash
python3 ema_trend_backpack_trader.py --test --symbol BTCUSDT
```
- 不执行实际交易
- 只显示信号和策略逻辑
- 用于验证策略和配置

#### 单次执行
```bash
python3 ema_trend_backpack_trader.py --symbol BTCUSDT
```
- 执行一次策略检查
- 如果满足条件会实际开仓
- 适合手动触发交易

#### 持续交易
```bash
python3 ema_trend_backpack_trader.py
```
- 持续监控市场
- 自动执行开仓和平仓
- 按配置间隔检查信号

## 配置参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| symbols | ["BTCUSDT", "ETHUSDT"] | 监控的交易对列表 |
| leverage | 50 | 杠杆倍数 |
| risk_pct | 0.05 | 风险比例（5%） |
| check_interval | 60 | 检查间隔（秒） |
| atr_period | 14 | ATR计算周期 |
| atr_mult | 2 | ATR倍数（止损） |
| risk_reward_ratio | 2 | 盈亏比（止盈） |
| max_positions | 3 | 最大同时持仓数 |
| enable_logging | true | 是否启用日志 |
| log_file | "backpack_trader.log" | 日志文件路径 |

## 风险控制

### 1. 头寸管理
- 基于账户余额和风险比例计算头寸
- 单笔交易风险不超过账户的5%
- 最大同时持仓3个交易对

### 2. 止损止盈
- 2ATR倍数止损
- 2:1盈亏比固定止盈
- 开仓时自动设置止损和止盈单

### 3. 信号过滤
- 4小时趋势过滤，避免逆势交易
- 1分钟精确入场，提高胜率
- 趋势反转时自动平仓

## 监控和日志

### 1. 实时监控
程序运行时会显示：
- 账户余额和持仓状态
- 策略执行结果
- 开仓和平仓信息
- 错误和异常信息

### 2. 日志文件
- 默认保存到 `backpack_trader.log`
- 包含时间戳的详细记录
- 可通过配置文件修改路径

### 3. 交易统计
```bash
python3 ema_trend_backpack_trader.py --stats
```
显示：
- 总交易次数
- 已平仓次数
- 累计盈亏
- 胜率统计
- 最近交易记录

## 安全注意事项

### 1. API密钥安全
- 不要在代码中硬编码API密钥
- 使用环境变量或配置文件
- 定期更换API密钥

### 2. 资金管理
- 建议使用小额资金测试
- 监控账户余额和持仓
- 设置合理的风险比例

### 3. 程序监控
- 定期检查程序运行状态
- 监控日志文件
- 设置异常告警

## 故障排除

### 1. 常见错误

**API密钥错误**
```
错误: API请求失败: 401 - {"code":-2014,"msg":"API-key format invalid."}
```
解决：检查API密钥配置是否正确

**余额不足**
```
错误: 金额不足，按当前价格最小下单量为0.001
```
解决：增加账户余额或降低风险比例

**网络连接错误**
```
错误: 网络连接超时
```
解决：检查网络连接，重试

### 2. 调试模式

启用详细日志：
```python
# 在config.py中设置
DEBUG = True
```

### 3. 联系支持

如遇到问题，请提供：
- 错误日志
- 配置文件内容
- 系统环境信息

## 免责声明

- 本程序仅供学习和研究使用
- 加密货币交易存在风险，可能导致资金损失
- 使用者需自行承担交易风险
- 建议在实盘交易前充分测试

## 更新日志

### v1.0.0 (2025-07-05)
- 初始版本发布
- 支持EMA趋势策略
- 集成Backpack交易所
- 完整的风险控制机制 