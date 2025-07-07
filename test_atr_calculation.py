#!/usr/bin/env python3
"""
测试ATR计算和止损价设置
"""
from strategies.ema_tunnel_strategy import EMATunnelStrategy
import pandas as pd

if __name__ == '__main__':
    strat = EMATunnelStrategy()
    symbol = 'BTCUSDT'
    
    print("=== 测试ATR计算和止损价设置 ===")
    
    # 获取K线数据
    df_15m = strat.get_binance_klines(symbol, '15m', limit=200)
    
    # 计算ATR
    atr = strat.calc_atr(df_15m, strat.atr_period)
    current_atr = atr.iloc[-1]
    
    print(f"ATR周期: {strat.atr_period}")
    print(f"ATR倍数: {strat.atr_mult}")
    print(f"当前ATR值: {current_atr:.2f}")
    
    # 显示最近几根K线的ATR值
    print("\n最近10根K线的ATR值:")
    for i in range(-10, 0):
        print(f"  {df_15m.index[i]}: {atr.iloc[i]:.2f}")
    
    # 测试止损价计算
    entry_price = df_15m['close'].iloc[-1]
    print(f"\n当前价格: {entry_price:.2f}")
    
    # 多头止损
    long_stop, long_atr = strat.atr_stop(df_15m, entry_price, 'long')
    print(f"多头止损价: {long_stop:.2f}")
    print(f"多头止损距离: {entry_price - long_stop:.2f}")
    print(f"多头止损距离/ATR: {(entry_price - long_stop) / long_atr:.2f}")
    
    # 空头止损
    short_stop, short_atr = strat.atr_stop(df_15m, entry_price, 'short')
    print(f"空头止损价: {short_stop:.2f}")
    print(f"空头止损距离: {short_stop - entry_price:.2f}")
    print(f"空头止损距离/ATR: {(short_stop - entry_price) / short_atr:.2f}")
    
    # 检查当前价格是否已经触及止损价
    print(f"\n=== 止损价检查 ===")
    print(f"当前价格: {entry_price:.2f}")
    print(f"多头止损价: {long_stop:.2f}")
    print(f"空头止损价: {short_stop:.2f}")
    
    if entry_price <= long_stop:
        print("⚠️  警告：当前价格已触及多头止损价！")
    else:
        print("✅ 当前价格未触及多头止损价")
        
    if entry_price >= short_stop:
        print("⚠️  警告：当前价格已触及空头止损价！")
    else:
        print("✅ 当前价格未触及空头止损价") 