#!/usr/bin/env python3
"""
EMA趋势策略实时测试脚本
使用真实市场数据测试策略信号
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.ema_trend_strategy import EMATrendStrategy
import pandas as pd
from datetime import datetime

def test_real_market_data():
    """使用真实市场数据测试策略"""
    print("=== EMA趋势策略实时测试 ===")
    
    strategy = EMATrendStrategy()
    symbol = 'BTCUSDT'
    
    try:
        print(f"获取{symbol}的K线数据...")
        
        # 获取4小时和1分钟K线数据
        df_4h = strategy.get_binance_klines(symbol, '4h', limit=700)
        df_1m = strategy.get_binance_klines(symbol, '1m', limit=200)
        
        print(f"4小时数据: {len(df_4h)}根K线")
        print(f"1分钟数据: {len(df_1m)}根K线")
        
        # 获取当前价格
        current_price = df_1m['close'].iloc[-1]
        print(f"当前价格: {current_price:.2f}")
        
        # 判断趋势
        trend = strategy.htf_trend_filter(df_4h)
        print(f"4小时趋势: {trend}")
        
        # 检测信号
        signal = strategy.ltf_signal_realtime(df_1m)
        print(f"1分钟信号: {signal}")
        
        # 计算EMA值
        ema13 = strategy.calc_ema(df_1m, 13)
        ema21 = strategy.calc_ema(df_1m, 21)
        ema34 = strategy.calc_ema(df_1m, 34)
        
        print(f"EMA13: {ema13.iloc[-1]:.2f}")
        print(f"EMA21: {ema21.iloc[-1]:.2f}")
        print(f"EMA34: {ema34.iloc[-1]:.2f}")
        
        # 计算EMA200
        ema200_4h = strategy.calc_ema(df_4h, 200)
        print(f"4小时EMA200: {ema200_4h.iloc[-1]:.2f}")
        
        # 测试开仓条件
        should_long = strategy.should_open_long(df_4h, df_1m)
        should_short = strategy.should_open_short(df_4h, df_1m)
        
        print(f"\n开仓信号:")
        print(f"应该开多头: {should_long}")
        print(f"应该开空头: {should_short}")
        
        # 如果满足开仓条件，计算止损止盈
        if should_long or should_short:
            direction = 'long' if should_long else 'short'
            stop_price, take_profit_price, atr = strategy.atr_stop_and_take_profit(df_1m, current_price, direction)
            
            print(f"\n{direction}头交易建议:")
            print(f"入场价: {current_price:.2f}")
            print(f"止损价: {stop_price:.2f}")
            print(f"止盈价: {take_profit_price:.2f}")
            print(f"ATR: {atr:.4f}")
            
            # 计算风险收益
            if direction == 'long':
                risk = current_price - stop_price
                reward = take_profit_price - current_price
            else:
                risk = stop_price - current_price
                reward = current_price - take_profit_price
            
            print(f"风险: {risk:.4f}")
            print(f"收益: {reward:.4f}")
            print(f"盈亏比: {reward/risk:.2f}")
        
        print("\n实时测试完成 ✓")
        
    except Exception as e:
        print(f"实时测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_multiple_symbols():
    """测试多个交易对"""
    print("\n=== 多交易对测试 ===")
    
    strategy = EMATrendStrategy()
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    
    for symbol in symbols:
        try:
            print(f"\n{symbol}:")
            
            # 获取数据
            df_4h = strategy.get_binance_klines(symbol, '4h', limit=700)
            df_1m = strategy.get_binance_klines(symbol, '1m', limit=200)
            
            current_price = df_1m['close'].iloc[-1]
            trend = strategy.htf_trend_filter(df_4h)
            signal = strategy.ltf_signal_realtime(df_1m)
            
            print(f"  价格: {current_price:.2f}")
            print(f"  趋势: {trend}")
            print(f"  信号: {signal}")
            
            # 检查开仓条件
            should_long = strategy.should_open_long(df_4h, df_1m)
            should_short = strategy.should_open_short(df_4h, df_1m)
            
            if should_long:
                print(f"  → 建议开多头")
            elif should_short:
                print(f"  → 建议开空头")
            else:
                print(f"  → 无信号")
                
        except Exception as e:
            print(f"  {symbol}测试失败: {e}")

def main():
    """主函数"""
    print("开始EMA趋势策略实时测试...")
    print("=" * 50)
    
    # 测试单个交易对
    test_real_market_data()
    
    # 测试多个交易对
    test_multiple_symbols()
    
    print("\n" + "=" * 50)
    print("实时测试完成！")

if __name__ == "__main__":
    main() 