#!/bin/bash

# EMA趋势策略交易程序安装脚本

echo "EMA趋势策略交易程序安装脚本"
echo "============================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi

echo "Python版本: $(python3 --version)"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo "升级pip..."
pip install --upgrade pip

# 安装依赖
echo "安装依赖包..."
pip install -r requirements_trader.txt

# 检查安装结果
echo "检查安装结果..."
python3 -c "import pandas, numpy, requests; print('依赖包安装成功')"

echo ""
echo "安装完成！"
echo "使用方法:"
echo "1. 激活虚拟环境: source venv/bin/activate"
echo "2. 运行交易程序: ./start_backpack_trader.sh --test"
echo "" 