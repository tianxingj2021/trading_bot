#!/usr/bin/env python3
"""
测试策略统计数据持久化与获取
流程：自动调用策略的头寸与止损计算自动下单 -> 等待10秒 -> 自动平仓 -> 输出统计信息
"""
import time
from strategies.ema_tunnel_strategy import EMATunnelStrategy

if __name__ == '__main__':
    strat = EMATunnelStrategy()
    exchange = 'backpack'  # 可改为'aster'
    symbol = 'BTCUSDT'
    leverage = 50
    risk_pct = 0.05  # 增加风险比例到50%，确保有足够头寸进行测试

    print("=== 自动下单（由策略自动计算头寸和止损） ===")
    # 只传入基础参数，头寸和止损均由策略自动计算
    df_15m = strat.get_binance_klines(symbol, '15m', limit=200)
    entry_price = df_15m['close'].iloc[-1]
    print(f"准备以价格 {entry_price} 开多仓...")
    result = strat.open_position(exchange, symbol, 'long', leverage, risk_pct, entry_price, df_15m)
    print("开仓结果:", result)
    if not result or result.get('action') != 'opened_long':
        print("开仓失败或未实际下单，测试终止。")
        exit(1)

    print("开始等待10秒...")
    time.sleep(10)
    print("等待结束，准备平仓...")

    print("=== 自动平仓 ===")
    close_result = strat.close_position(exchange, symbol, 'long')
    print("平仓结果:", close_result)

    print("=== 统计信息 ===")
    print("累计盈亏:", strat.total_pnl)
    print("订单历史:")
    for order in strat.order_history:
        print(order) 