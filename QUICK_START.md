# EMA趋势策略Backpack交易程序 - 快速开始

## 🚀 5分钟快速开始

### 1. 安装程序
```bash
# 克隆或下载程序文件后，运行安装脚本
./install_trader.sh
```

### 2. 配置API密钥
在 `config.py` 中配置您的Backpack API密钥：
```python
BACKPACK_API_KEY = "your_api_key_here"
BACKPACK_API_SECRET = "your_api_secret_here"
```

### 3. 测试程序
```bash
# 测试模式（不实际交易）
./start_backpack_trader.sh --test --symbol BTCUSDT
```

### 4. 开始交易
```bash
# 实盘交易（请确保已充分测试）
./start_backpack_trader.sh
```

## 📋 常用命令

| 命令 | 说明 |
|------|------|
| `./start_backpack_trader.sh --help` | 显示帮助信息 |
| `./start_backpack_trader.sh --test` | 测试模式 |
| `./start_backpack_trader.sh --symbol BTCUSDT` | 单次执行 |
| `./start_backpack_trader.sh --stats` | 查看统计 |
| `./start_backpack_trader.sh` | 实盘交易 |

## ⚙️ 配置说明

### 默认配置
```json
{
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "leverage": 50,
  "risk_pct": 0.05,
  "check_interval": 60,
  "atr_period": 14,
  "atr_mult": 2,
  "risk_reward_ratio": 2,
  "max_positions": 3
}
```

### 关键参数
- **risk_pct**: 风险比例（5% = 0.05）
- **leverage**: 杠杆倍数（50倍）
- **max_positions**: 最大同时持仓数（3个）
- **check_interval**: 检查间隔（60秒）

## 🔍 监控和日志

### 实时监控
程序运行时会显示：
- 账户余额和持仓状态
- 策略执行结果
- 开仓和平仓信息

### 日志文件
- 位置：`backpack_trader.log`
- 包含详细的时间戳记录

### 交易统计
```bash
./start_backpack_trader.sh --stats
```

## ⚠️ 重要提醒

1. **首次使用请务必测试**
   ```bash
   ./start_backpack_trader.sh --test
   ```

2. **小额资金开始**
   - 建议使用小额资金测试
   - 确认策略表现后再增加资金

3. **监控运行状态**
   - 定期检查程序运行
   - 关注日志文件
   - 监控账户余额

4. **风险控制**
   - 设置合理的风险比例
   - 不要超过最大持仓限制
   - 定期检查止损止盈设置

## 🆘 故障排除

### 常见问题

**1. 模块导入错误**
```bash
# 确保激活虚拟环境
source venv/bin/activate

# 重新安装依赖
pip install -r requirements_trader.txt
```

**2. API密钥错误**
- 检查 `config.py` 中的API密钥配置
- 确认API密钥有交易权限

**3. 余额不足**
- 增加账户余额
- 或降低 `risk_pct` 参数

## 📞 技术支持

如遇到问题，请提供：
- 错误日志
- 配置文件内容
- 系统环境信息

---

**免责声明**: 本程序仅供学习和研究使用，加密货币交易存在风险，使用者需自行承担交易风险。 