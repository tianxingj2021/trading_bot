#!/usr/bin/env python3
"""
测试EMA隧道策略的完整执行流程
包括：信号检测、自动开仓、止损设置、止盈监控、自动平仓
"""
from strategies.ema_tunnel_strategy import EMATunnelStrategy
import time

def test_signal_detection():
    """测试信号检测（不实际交易）"""
    print("=== 测试信号检测 ===")
    
    strat = EMATunnelStrategy()
    
    # 测试不同交易对
    symbols = ['BTCUSDT', 'ETHUSDT']
    exchanges = ['aster', 'backpack']
    
    for symbol in symbols:
        for exchange in exchanges:
            print(f"\n--- {exchange} {symbol} ---")
            
            # 只检测信号，不实际交易
            result = strat.execute_strategy(
                exchange=exchange,
                symbol=symbol,
                leverage=50,
                risk_pct=0.05,
                auto_trade=False  # 只检测信号
            )
            
            print(f"策略结果: {result}")

def test_single_execution():
    """测试单次策略执行（实际交易）"""
    print("\n=== 测试单次策略执行 ===")
    
    strat = EMATunnelStrategy()
    
    # 选择一个交易对和交易所进行测试
    exchange = 'aster'  # 或 'backpack'
    symbol = 'BTCUSDT'
    
    print(f"测试交易所: {exchange}")
    print(f"测试交易对: {symbol}")
    
    # 执行策略（实际交易）
    result = strat.execute_strategy(
        exchange=exchange,
        symbol=symbol,
        leverage=50,
        risk_pct=0.05,
        auto_trade=True  # 实际交易
    )
    
    print(f"执行结果: {result}")
    
    return strat

def test_position_monitoring(strat):
    """测试持仓监控"""
    print("\n=== 测试持仓监控 ===")
    
    if not strat.active_positions:
        print("无活跃持仓，跳过监控测试")
        return
    
    print("开始监控持仓...")
    print("按 Ctrl+C 停止监控")
    
    try:
        # 监控30秒（测试用）
        strat.monitor_positions(check_interval=30)
    except KeyboardInterrupt:
        print("监控已停止")

def test_manual_position_management():
    """测试手动持仓管理"""
    print("\n=== 测试手动持仓管理 ===")
    
    strat = EMATunnelStrategy()
    
    # 模拟已有持仓
    strat.active_positions['BTCUSDT'] = {
        'direction': 'long',
        'entry_price': 109000.0,
        'stop_price': 108500.0,
        'quantity': 0.001,
        'exchange': 'aster',
        'open_time': time.time()
    }
    
    print("模拟持仓信息:")
    for symbol, pos in strat.active_positions.items():
        print(f"  {symbol}: {pos['direction']} @ {pos['entry_price']:.2f}")
    
    # 检查平仓条件
    print("\n检查平仓条件...")
    df_4h = strat.get_binance_klines('BTCUSDT', '4h', limit=700)
    df_15m = strat.get_binance_klines('BTCUSDT', '15m', limit=200)
    
    htf_trend = strat.htf_trend(df_4h)
    ltf_signal = strat.ltf_signal(df_15m)
    
    print(f"4小时趋势: {htf_trend}")
    print(f"15分钟信号: {ltf_signal}")
    
    should_close = strat.should_close_long(df_4h, df_15m)
    print(f"是否应该平多仓: {should_close}")

def test_strategy_parameters():
    """测试不同策略参数"""
    print("\n=== 测试不同策略参数 ===")
    
    # 测试不同ATR倍数
    atr_mults = [1.5, 2.0, 2.5, 3.0]
    
    for atr_mult in atr_mults:
        print(f"\n--- ATR倍数: {atr_mult} ---")
        strat = EMATunnelStrategy(atr_period=14, atr_mult=atr_mult)
        
        # 获取K线数据
        df_15m = strat.get_binance_klines('BTCUSDT', '15m', limit=200)
        current_price = df_15m['close'].iloc[-1]
        
        # 计算止损价
        stop_long, atr = strat.atr_stop(df_15m, current_price, 'long')
        stop_short, _ = strat.atr_stop(df_15m, current_price, 'short')
        
        print(f"当前价格: {current_price:.2f}")
        print(f"ATR: {atr:.2f}")
        print(f"多头止损: {stop_long:.2f} (距离: {current_price - stop_long:.2f})")
        print(f"空头止损: {stop_short:.2f} (距离: {stop_short - current_price:.2f})")

def test_risk_management():
    """测试风险管理"""
    print("\n=== 测试风险管理 ===")
    
    strat = EMATunnelStrategy()
    
    # 测试不同风险比例
    risk_pcts = [0.01, 0.02, 0.05, 0.10]
    exchanges = ['aster', 'backpack']
    
    for exchange in exchanges:
        print(f"\n--- {exchange} ---")
        
        for risk_pct in risk_pcts:
            # 计算推荐头寸
            position_size = strat.recommend_position_size_by_account(
                exchange=exchange,
                symbol='BTCUSDT',
                user_leverage=50,
                stop_distance=500,  # 假设止损距离500点
                entry_price=109000.0,
                risk_pct=risk_pct
            )
            
            print(f"风险比例 {risk_pct*100}%: 推荐头寸 {position_size:.6f}")

if __name__ == '__main__':
    print("开始测试EMA隧道策略完整执行流程...")
    
    # 1. 测试信号检测（不实际交易）
    test_signal_detection()
    
    # 2. 测试策略参数
    test_strategy_parameters()
    
    # 3. 测试风险管理
    test_risk_management()
    
    # 4. 测试手动持仓管理
    test_manual_position_management()
    
    # 5. 询问是否进行实际交易测试
    print("\n" + "="*50)
    print("是否进行实际交易测试？")
    print("注意：这将使用真实资金进行交易！")
    print("输入 'yes' 继续，其他任意键跳过")
    print("="*50)
    
    user_input = input("请输入选择: ").strip().lower()
    
    if user_input == 'yes':
        # 6. 测试单次策略执行（实际交易）
        strat = test_single_execution()
        
        # 7. 测试持仓监控
        test_position_monitoring(strat)
    else:
        print("跳过实际交易测试")
    
    print("\n测试完成！") 