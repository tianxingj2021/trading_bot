#!/bin/bash

# EMA趋势策略Backpack实盘交易程序启动脚本

echo "EMA趋势策略Backpack实盘交易程序"
echo "=================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi

# 检查配置文件
if [ ! -f "backpack_trader_config.json" ]; then
    echo "警告: 未找到配置文件，将使用默认配置"
fi

# 检查API密钥配置
if [ ! -f "config.py" ]; then
    echo "错误: 未找到config.py文件，请先配置API密钥"
    exit 1
fi

# 显示使用说明
echo ""
echo "使用方法:"
echo "1. 显示帮助: $0 --help"
echo "2. 测试模式: $0 --test"
echo "3. 单次执行: $0 --symbol BTCUSDT"
echo "4. 显示统计: $0 --stats"
echo "5. 实盘交易: $0"
echo ""

# 检查参数
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "参数说明:"
    echo "  --config FILE    指定配置文件路径"
    echo "  --symbol SYMBOL  单次执行指定交易对"
    echo "  --stats          显示交易统计"
    echo "  --test           测试模式（不实际交易）"
    echo "  --help, -h       显示帮助信息"
    exit 0
fi

# 激活虚拟环境（如果存在）
if [ -d "venv" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
fi

# 运行交易程序
echo "启动交易程序..."
python3 ema_trend_backpack_trader.py "$@" 