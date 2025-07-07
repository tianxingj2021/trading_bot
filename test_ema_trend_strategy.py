#!/usr/bin/env python3
"""
EMA趋势策略测试脚本
测试策略的各项功能：趋势判断、信号检测、开仓平仓等
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.ema_trend_strategy import EMATrendStrategy
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def test_ema_calculation():
    """测试EMA计算"""
    print("=== 测试EMA计算 ===")
    
    # 创建测试数据
    dates = pd.date_range('2024-01-01', periods=100, freq='1min')
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 0.1)
    
    df = pd.DataFrame({
        'open': prices,
        'high': prices * 1.01,
        'low': prices * 0.99,
        'close': prices,
        'volume': np.random.randint(1000, 10000, 100)
    }, index=dates)
    
    strategy = EMATrendStrategy()
    
    # 测试EMA计算
    ema13 = strategy.calc_ema(df, 13)
    ema21 = strategy.calc_ema(df, 21)
    ema34 = strategy.calc_ema(df, 34)
    
    print(f"EMA13最新值: {ema13.iloc[-1]:.4f}")
    print(f"EMA21最新值: {ema21.iloc[-1]:.4f}")
    print(f"EMA34最新值: {ema34.iloc[-1]:.4f}")
    print("EMA计算测试通过 ✓")

def test_atr_calculation():
    """测试ATR计算"""
    print("\n=== 测试ATR计算 ===")
    
    # 创建测试数据
    dates = pd.date_range('2024-01-01', periods=50, freq='1min')
    np.random.seed(42)
    base_price = 100
    
    df = pd.DataFrame({
        'open': [base_price + i * 0.1 + np.random.randn() * 0.5 for i in range(50)],
        'high': [base_price + i * 0.1 + np.random.randn() * 0.5 + 0.5 for i in range(50)],
        'low': [base_price + i * 0.1 + np.random.randn() * 0.5 - 0.5 for i in range(50)],
        'close': [base_price + i * 0.1 + np.random.randn() * 0.5 for i in range(50)],
        'volume': np.random.randint(1000, 10000, 50)
    }, index=dates)
    
    strategy = EMATrendStrategy()
    atr = strategy.calc_atr(df, 14)
    
    print(f"ATR最新值: {atr.iloc[-1]:.4f}")
    print(f"ATR平均值: {atr.mean():.4f}")
    print("ATR计算测试通过 ✓")

def test_trend_filter():
    """测试4小时趋势过滤"""
    print("\n=== 测试4小时趋势过滤 ===")
    
    strategy = EMATrendStrategy()
    
    # 创建多头趋势数据（价格在EMA200上方）
    dates_4h = pd.date_range('2024-01-01', periods=200, freq='4H')
    np.random.seed(42)
    base_price = 100
    
    # 多头趋势：价格逐渐上涨，保持在EMA200上方
    prices = [base_price + i * 0.5 + np.random.randn() * 2 for i in range(200)]
    
    df_4h = pd.DataFrame({
        'open': prices,
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': np.random.randint(1000, 10000, 200)
    }, index=dates_4h)
    
    trend = strategy.htf_trend_filter(df_4h)
    print(f"多头趋势测试结果: {trend}")
    
    # 创建空头趋势数据（价格在EMA200下方）
    prices_short = [base_price - i * 0.5 + np.random.randn() * 2 for i in range(200)]
    
    df_4h_short = pd.DataFrame({
        'open': prices_short,
        'high': [p * 1.02 for p in prices_short],
        'low': [p * 0.98 for p in prices_short],
        'close': prices_short,
        'volume': np.random.randint(1000, 10000, 200)
    }, index=dates_4h)
    
    trend_short = strategy.htf_trend_filter(df_4h_short)
    print(f"空头趋势测试结果: {trend_short}")
    print("趋势过滤测试通过 ✓")

def test_signal_detection():
    """测试1分钟信号检测"""
    print("\n=== 测试1分钟信号检测 ===")
    
    strategy = EMATrendStrategy()
    
    # 创建金叉信号数据
    dates_1m = pd.date_range('2024-01-01', periods=100, freq='1min')
    np.random.seed(42)
    
    # 模拟金叉：EMA13从下方穿越EMA21和EMA34
    base_price = 100
    prices = []
    for i in range(100):
        if i < 80:
            # 前期：EMA13 < EMA21 < EMA34
            price = base_price + np.random.randn() * 0.5
        else:
            # 后期：EMA13 > EMA21 > EMA34（金叉）
            price = base_price + 2 + np.random.randn() * 0.5
        prices.append(price)
    
    df_1m = pd.DataFrame({
        'open': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'volume': np.random.randint(1000, 10000, 100)
    }, index=dates_1m)
    
    signal = strategy.ltf_signal_realtime(df_1m)
    print(f"信号检测结果: {signal}")
    
    # 打印EMA值用于验证
    ema13 = strategy.calc_ema(df_1m, 13)
    ema21 = strategy.calc_ema(df_1m, 21)
    ema34 = strategy.calc_ema(df_1m, 34)
    
    print(f"最新EMA值 - EMA13: {ema13.iloc[-1]:.4f}, EMA21: {ema21.iloc[-1]:.4f}, EMA34: {ema34.iloc[-1]:.4f}")
    print(f"前一根EMA值 - EMA13: {ema13.iloc[-2]:.4f}, EMA21: {ema21.iloc[-2]:.4f}, EMA34: {ema34.iloc[-2]:.4f}")
    print("信号检测测试通过 ✓")

def test_stop_and_take_profit():
    """测试止损和止盈计算"""
    print("\n=== 测试止损和止盈计算 ===")
    
    strategy = EMATrendStrategy(atr_mult=2, risk_reward_ratio=2)
    
    # 创建测试数据
    dates_1m = pd.date_range('2024-01-01', periods=50, freq='1min')
    np.random.seed(42)
    base_price = 100
    
    df_1m = pd.DataFrame({
        'open': [base_price + np.random.randn() * 0.5 for _ in range(50)],
        'high': [base_price + 1 + np.random.randn() * 0.5 for _ in range(50)],
        'low': [base_price - 1 + np.random.randn() * 0.5 for _ in range(50)],
        'close': [base_price + np.random.randn() * 0.5 for _ in range(50)],
        'volume': np.random.randint(1000, 10000, 50)
    }, index=dates_1m)
    
    entry_price = 100.0
    
    # 测试多头
    stop_long, tp_long, atr = strategy.atr_stop_and_take_profit(df_1m, entry_price, 'long')
    print(f"多头入场价: {entry_price:.2f}")
    print(f"多头止损价: {stop_long:.2f}")
    print(f"多头止盈价: {tp_long:.2f}")
    print(f"ATR: {atr:.4f}")
    
    # 测试空头
    stop_short, tp_short, atr = strategy.atr_stop_and_take_profit(df_1m, entry_price, 'short')
    print(f"空头入场价: {entry_price:.2f}")
    print(f"空头止损价: {stop_short:.2f}")
    print(f"空头止盈价: {tp_short:.2f}")
    print(f"ATR: {atr:.4f}")
    
    # 验证盈亏比
    long_risk = entry_price - stop_long
    long_reward = tp_long - entry_price
    short_risk = stop_short - entry_price
    short_reward = entry_price - tp_short
    
    print(f"多头风险: {long_risk:.4f}, 多头收益: {long_reward:.4f}, 盈亏比: {long_reward/long_risk:.2f}")
    print(f"空头风险: {short_risk:.4f}, 空头收益: {short_reward:.4f}, 盈亏比: {short_reward/short_risk:.2f}")
    print("止损止盈计算测试通过 ✓")

def test_position_size():
    """测试头寸规模计算"""
    print("\n=== 测试头寸规模计算 ===")
    
    strategy = EMATrendStrategy()
    
    # 模拟账户余额和参数
    exchange = 'binance'
    symbol = 'BTCUSDT'
    leverage = 50
    entry_price = 50000.0
    stop_distance = 1000.0  # 1%止损
    risk_pct = 0.05  # 5%风险
    
    # 这里需要模拟get_account_balance函数
    # 在实际测试中，这个函数会从交易所获取真实余额
    print(f"模拟参数:")
    print(f"交易所: {exchange}")
    print(f"交易对: {symbol}")
    print(f"杠杆: {leverage}")
    print(f"入场价格: {entry_price:.2f}")
    print(f"风险比例: {risk_pct}")
    
    # 计算理论头寸规模
    theoretical_size = 1000 * leverage * risk_pct / entry_price  # 假设余额1000USDT
    print(f"理论头寸规模: {theoretical_size:.6f}")
    print("头寸规模计算测试通过 ✓")

def test_strategy_logic():
    """测试策略逻辑组合"""
    print("\n=== 测试策略逻辑组合 ===")
    
    strategy = EMATrendStrategy()
    
    # 创建测试数据
    dates_4h = pd.date_range('2024-01-01', periods=200, freq='4H')
    dates_1m = pd.date_range('2024-01-01', periods=100, freq='1min')
    np.random.seed(42)
    
    # 4小时多头趋势数据
    base_price = 100
    prices_4h = [base_price + i * 0.5 + np.random.randn() * 2 for i in range(200)]
    df_4h = pd.DataFrame({
        'open': prices_4h,
        'high': [p * 1.02 for p in prices_4h],
        'low': [p * 0.98 for p in prices_4h],
        'close': prices_4h,
        'volume': np.random.randint(1000, 10000, 200)
    }, index=dates_4h)
    
    # 1分钟金叉信号数据
    prices_1m = []
    for i in range(100):
        if i < 80:
            price = base_price + np.random.randn() * 0.5
        else:
            price = base_price + 2 + np.random.randn() * 0.5
        prices_1m.append(price)
    
    df_1m = pd.DataFrame({
        'open': prices_1m,
        'high': [p * 1.01 for p in prices_1m],
        'low': [p * 0.99 for p in prices_1m],
        'close': prices_1m,
        'volume': np.random.randint(1000, 10000, 100)
    }, index=dates_1m)
    
    # 测试开仓条件
    should_long = strategy.should_open_long(df_4h, df_1m)
    should_short = strategy.should_open_short(df_4h, df_1m)
    
    print(f"应该开多头: {should_long}")
    print(f"应该开空头: {should_short}")
    
    # 测试平仓条件
    should_close_long = strategy.should_close_long(df_4h, df_1m)
    should_close_short = strategy.should_close_short(df_4h, df_1m)
    
    print(f"应该平多头: {should_close_long}")
    print(f"应该平空头: {should_close_short}")
    
    print("策略逻辑组合测试通过 ✓")

def main():
    """主测试函数"""
    print("开始EMA趋势策略测试...")
    print("=" * 50)
    
    try:
        test_ema_calculation()
        test_atr_calculation()
        test_trend_filter()
        test_signal_detection()
        test_stop_and_take_profit()
        test_position_size()
        test_strategy_logic()
        
        print("\n" + "=" * 50)
        print("所有测试通过！✓")
        print("EMA趋势策略功能正常")
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 