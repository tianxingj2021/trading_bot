#!/usr/bin/env python3
"""
EMA趋势策略使用示例
展示如何使用策略进行交易
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.ema_trend_strategy import EMATrendStrategy
import time

def example_basic_usage():
    """基本使用示例"""
    print("=== EMA趋势策略基本使用示例 ===")
    
    # 创建策略实例
    strategy = EMATrendStrategy(
        atr_period=14,      # ATR周期
        atr_mult=2,         # ATR倍数（止损）
        risk_reward_ratio=2 # 盈亏比（止盈）
    )
    
    # 策略参数
    exchange = 'binance'    # 交易所
    symbol = 'BTCUSDT'      # 交易对
    leverage = 50           # 杠杆
    risk_pct = 0.05         # 风险比例（5%）
    
    print(f"策略参数:")
    print(f"交易所: {exchange}")
    print(f"交易对: {symbol}")
    print(f"杠杆: {leverage}")
    print(f"风险比例: {risk_pct}")
    print(f"ATR倍数: {strategy.atr_mult}")
    print(f"盈亏比: {strategy.risk_reward_ratio}")
    
    # 执行策略（只返回信号，不实际交易）
    print(f"\n执行策略（信号模式）...")
    result = strategy.execute_strategy(
        exchange=exchange,
        symbol=symbol,
        leverage=leverage,
        risk_pct=risk_pct,
        auto_trade=False  # 不自动交易，只返回信号
    )
    
    print(f"策略结果: {result}")
    
    return strategy

def example_auto_trade():
    """自动交易示例（需要配置API密钥）"""
    print("\n=== 自动交易示例 ===")
    print("注意：此示例需要配置真实的API密钥才能执行")
    
    strategy = EMATrendStrategy()
    
    # 策略参数
    exchange = 'binance'
    symbol = 'BTCUSDT'
    leverage = 50
    risk_pct = 0.05
    
    print(f"自动交易参数:")
    print(f"交易所: {exchange}")
    print(f"交易对: {symbol}")
    print(f"杠杆: {leverage}")
    print(f"风险比例: {risk_pct}")
    
    # 执行策略（自动交易）
    # result = strategy.execute_strategy(
    #     exchange=exchange,
    #     symbol=symbol,
    #     leverage=leverage,
    #     risk_pct=risk_pct,
    #     auto_trade=True  # 自动交易
    # )
    
    print("自动交易功能已注释，需要配置API密钥后启用")

def example_monitor_positions():
    """持仓监控示例"""
    print("\n=== 持仓监控示例 ===")
    
    strategy = EMATrendStrategy()
    
    print("开始监控持仓...")
    print("按 Ctrl+C 停止监控")
    
    # 监控持仓（每60秒检查一次）
    # strategy.monitor_positions(check_interval=60)
    
    print("持仓监控功能已注释，需要配置API密钥后启用")

def example_custom_parameters():
    """自定义参数示例"""
    print("\n=== 自定义参数示例 ===")
    
    # 创建不同参数的策略实例
    strategies = {
        "保守型": EMATrendStrategy(atr_mult=1.5, risk_reward_ratio=1.5),
        "标准型": EMATrendStrategy(atr_mult=2.0, risk_reward_ratio=2.0),
        "激进型": EMATrendStrategy(atr_mult=2.5, risk_reward_ratio=2.5)
    }
    
    for name, strategy in strategies.items():
        print(f"{name}策略:")
        print(f"  ATR倍数: {strategy.atr_mult}")
        print(f"  盈亏比: {strategy.risk_reward_ratio}")
        print(f"  ATR周期: {strategy.atr_period}")

def example_multiple_symbols():
    """多交易对示例"""
    print("\n=== 多交易对示例 ===")
    
    strategy = EMATrendStrategy()
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    exchange = 'binance'
    leverage = 50
    risk_pct = 0.05
    
    print(f"监控交易对: {symbols}")
    
    for symbol in symbols:
        try:
            print(f"\n{symbol}:")
            result = strategy.execute_strategy(
                exchange=exchange,
                symbol=symbol,
                leverage=leverage,
                risk_pct=risk_pct,
                auto_trade=False
            )
            print(f"  结果: {result['action']} - {result['reason']}")
        except Exception as e:
            print(f"  {symbol}执行失败: {e}")

def example_backtest_mode():
    """回测模式示例"""
    print("\n=== 回测模式示例 ===")
    
    strategy = EMATrendStrategy()
    
    # 获取历史数据
    symbol = 'BTCUSDT'
    df_4h = strategy.get_binance_klines(symbol, '4h', limit=700)
    df_1m = strategy.get_binance_klines(symbol, '1m', limit=200)
    
    print(f"获取{symbol}历史数据:")
    print(f"  4小时数据: {len(df_4h)}根K线")
    print(f"  1分钟数据: {len(df_1m)}根K线")
    
    # 分析趋势和信号
    trend = strategy.htf_trend_filter(df_4h)
    signal = strategy.ltf_signal_realtime(df_1m)
    
    print(f"  4小时趋势: {trend}")
    print(f"  1分钟信号: {signal}")
    
    # 检查开仓条件
    should_long = strategy.should_open_long(df_4h, df_1m)
    should_short = strategy.should_open_short(df_4h, df_1m)
    
    print(f"  开仓信号:")
    print(f"    多头: {should_long}")
    print(f"    空头: {should_short}")

def main():
    """主函数"""
    print("EMA趋势策略使用示例")
    print("=" * 50)
    
    try:
        # 基本使用示例
        strategy = example_basic_usage()
        
        # 自定义参数示例
        example_custom_parameters()
        
        # 多交易对示例
        example_multiple_symbols()
        
        # 回测模式示例
        example_backtest_mode()
        
        # 自动交易示例（注释状态）
        example_auto_trade()
        
        # 持仓监控示例（注释状态）
        example_monitor_positions()
        
        print("\n" + "=" * 50)
        print("使用示例完成！")
        print("\n使用说明:")
        print("1. 基本使用：创建策略实例，调用execute_strategy()")
        print("2. 自动交易：设置auto_trade=True，需要配置API密钥")
        print("3. 持仓监控：调用monitor_positions()持续监控")
        print("4. 自定义参数：调整ATR倍数、盈亏比等参数")
        print("5. 多交易对：循环执行多个交易对的策略")
        
    except Exception as e:
        print(f"示例执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 