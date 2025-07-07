# 项目结构说明

```
aster_bot_python/
├── README.md                 # 项目说明文档
├── requirements.txt          # Python依赖包
├── config.py                # 配置文件
├── run.py                   # 统一启动脚本
├── test_basic.py            # 基本功能测试
├── env.example              # 环境变量示例
├── __init__.py              # 包初始化文件
│
├── bot.py                   # 套利机器人主逻辑
├── trend_v2.py              # 趋势策略V2
├── maker.py                 # 做市策略
├── cli.py                   # 命令行界面
│
├── exchanges/               # 交易所API封装
│   ├── __init__.py
│   └── aster.py            # AsterDex交易所API
│
└── utils/                   # 工具函数
    ├── __init__.py
    ├── helper.py           # 辅助函数
    ├── log.py              # 日志工具
    └── order.py            # 订单工具
```

## 文件功能说明

### 核心文件

- **config.py**: 配置文件，包含交易参数和API密钥配置
- **bot.py**: 套利机器人，实现Bitget和AsterDex之间的套利策略
- **trend_v2.py**: 趋势策略V2，基于SMA30均线的自动化交易策略
- **maker.py**: 做市策略，自动在盘口挂双边单的做市策略
- **cli.py**: 命令行界面，提供CLI交互功能

### 交易所模块

- **exchanges/aster.py**: AsterDex交易所的完整API封装，包括：
  - REST API接口
  - WebSocket实时数据
  - 订单管理
  - 账户信息
  - 持仓管理

### 工具模块

- **utils/helper.py**: 辅助函数
  - 获取持仓信息
  - 计算SMA30均线
  - 价格和数量格式化

- **utils/log.py**: 日志工具
  - 交易日志记录
  - 状态信息显示
  - 彩色输出

- **utils/order.py**: 订单工具
  - 下单操作
  - 撤单操作
  - 止损止盈计算
  - 订单锁管理

### 启动和测试

- **run.py**: 统一启动脚本，支持多种策略启动
- **test_basic.py**: 基本功能测试
- **requirements.txt**: Python依赖包列表

## 使用方式

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
复制 `env.example` 为 `.env` 并填入API密钥

### 3. 启动策略

#### 方式一：使用统一启动脚本
```bash
# 启动趋势策略
python run.py trend

# 启动做市策略
python run.py maker

# 启动套利策略
python run.py arb
```

#### 方式二：直接运行策略文件
```bash
# 趋势策略
python trend_v2.py

# 做市策略
python maker.py

# 套利策略
python bot.py
```

#### 方式三：使用CLI
```bash
# 启动套利机器人
python cli.py start

# 查看日志
python cli.py log

# 重置统计
python cli.py reset
```

### 4. 运行测试
```bash
python test_basic.py
```

## 技术特点

1. **异步编程**: 使用asyncio进行异步处理，提高性能
2. **模块化设计**: 清晰的模块分离，便于维护和扩展
3. **错误处理**: 完善的异常处理和错误恢复机制
4. **实时监控**: WebSocket实时数据推送
5. **风控机制**: 内置止损止盈和风险控制
6. **美观界面**: 使用rich库提供彩色命令行界面

## 扩展性

项目采用模块化设计，可以轻松扩展：

1. **添加新交易所**: 在exchanges目录下添加新的交易所API封装
2. **添加新策略**: 创建新的策略文件并集成到run.py中
3. **添加新指标**: 在utils/helper.py中添加新的技术指标
4. **添加新功能**: 在utils目录下添加新的工具模块 