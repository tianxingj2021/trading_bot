import pandas as pd
from strategies.ema_tunnel_strategy import EMATunnelStrategy
from utils.account_adapter import get_account_balance, get_max_leverage
from utils.order_adapter import place_order

if __name__ == '__main__':
    symbol = 'BTCUSDT'
    exchange = 'aster'  # 可改为binance/backpack
    user_leverage = 50
    strat = EMATunnelStrategy()
    print('--- 测试K线缓存与加载 ---')
    df_4h = strat.get_binance_klines(symbol, '4h', limit=200)
    df_15m = strat.get_binance_klines(symbol, '15m', limit=200)
    print(f'4h K线数量: {len(df_4h)}, 15m K线数量: {len(df_15m)}')
    print('4h最新K线:', df_4h.tail(2))
    print('15m最新K线:', df_15m.tail(2))

    print('\n--- 测试4小时趋势判断 ---')
    trend = strat.htf_trend(df_4h)
    print('当前4小时趋势:', trend)

    print('\n--- 测试15分钟金叉/死叉信号 ---')
    ltf_sig = strat.ltf_signal(df_15m)
    print('当前15分钟信号:', ltf_sig)

    print('\n--- 测试ATR止损价 ---')
    entry_price = df_15m['close'].iloc[-1]
    stop_long, atr_val = strat.atr_stop(df_15m, entry_price, 'long')
    stop_short, _ = strat.atr_stop(df_15m, entry_price, 'short')
    print(f'多头止损: {stop_long:.2f}, 空头止损: {stop_short:.2f}, ATR: {atr_val:.2f}')

    print('\n--- 测试策略开多/开空信号 ---')
    print('should_open_long:', strat.should_open_long(df_4h, df_15m))
    print('should_open_short:', strat.should_open_short(df_4h, df_15m))

    print('\n--- 测试头寸规模计算 ---')
    stop_distance = abs(entry_price - stop_long)
    print(f'entry_price={entry_price}, stop_long={stop_long}, ATR={atr_val}, 止损距离={stop_distance}')
    # 查询余额和最大杠杆
    balance = get_account_balance(exchange, 'USDT')
    max_lev = get_max_leverage(exchange, symbol)
    print(f'账户余额={balance}, 最大杠杆={max_lev}, 用户杠杆={user_leverage}')
    pos_size = strat.recommend_position_size_by_account(exchange, symbol, user_leverage, stop_distance, entry_price, risk_pct=0.05, point_value=1, asset='USDT')
    print(f'推荐头寸规模={pos_size:.4f}')

    print('\n--- 测试统一下单接口下单 ---')
    order_amount = pos_size * entry_price  # 换算为USDT金额
    print(f'下单参数: exchange={exchange}, symbol={symbol}, amount={order_amount:.2f}, direction=long, leverage={user_leverage}')
    try:
        order_result = place_order(exchange, symbol, order_amount, 'long', order_type="MARKET", price=None, leverage=user_leverage)
        print('开多下单结果:', order_result)
        
        # 从开仓结果中获取实际成交数量
        actual_quantity = float(order_result.quantity)  # 实际成交数量
        print(f'实际成交数量: {actual_quantity}')
        
        # 使用实际成交数量设置市价止损单（直接传代币数量）
        stop_order_result = place_order(
            exchange, symbol, actual_quantity, 'short', order_type="STOP_MARKET", price=None, leverage=user_leverage, stop_price=stop_long, reduce_only=True, is_quantity=True
        )
        print('市价止损单下单结果:', stop_order_result)
    except Exception as e:
        print('下单异常:', e)

    print(f'建议止损价: {stop_long:.2f}')

    print('\n--- 测试backpack交易所头寸计算（自动使用USDC） ---')
    balance_bk = get_account_balance('backpack', 'USDC')
    print(f'backpack账户余额={balance_bk}')
    for lev in [10, 25, 50]:
        print(f"\nbackpack杠杆={lev}，实际杠杆=50.0")
        pos_size = strat.recommend_position_size_by_account('backpack', symbol, lev, stop_distance, entry_price, risk_pct=0.05, point_value=1, asset='USDT')
        print(f'backpack推荐头寸规模={pos_size:.4f}')

    print('\n--- 测试backpack交易所下单和止损挂单 ---')
    backpack_exchange = 'backpack'
    backpack_symbol = 'BTCUSDT'  # 使用标准交易对，会自动转换为BTC_USDC_PERP合约
    
    # 使用更小的下单金额，避免资金不足，backpack默认50倍杠杆
    small_amount = 5.0  # 只使用5 USDC进行测试
    print(f'Backpack下单参数: exchange={backpack_exchange}, symbol={backpack_symbol}, amount={small_amount}, direction=long, stop_price={stop_long:.2f}')
    try:
        # Backpack开仓并设置止损（在开仓时直接设置止损）
        backpack_order_result = place_order(
            backpack_exchange, backpack_symbol, small_amount, 'long', 
            order_type="MARKET", price=None, stop_price=stop_long
        )
        print('Backpack开多并设置止损下单结果:', backpack_order_result)
        
        # 检查止损是否设置成功
        if 'stopLossTriggerPrice' in backpack_order_result:
            print(f'止损设置成功，止损价: {backpack_order_result["stopLossTriggerPrice"]}')
        else:
            print('止损设置失败或未返回止损信息')
    except Exception as e:
        print('Backpack下单异常:', e)

    print(f'建议止损价: {stop_long:.2f}') 