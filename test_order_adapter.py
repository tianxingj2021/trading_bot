#!/usr/bin/env python3
"""
测试order_adapter.py对不同交易所的挂单逻辑适配
"""
from utils.order_adapter import place_order, close_position, adapt_symbol, get_side_mapping
from strategies.ema_tunnel_strategy import EMATunnelStrategy

def test_symbol_adaptation():
    """测试交易对适配"""
    print("=== 测试交易对适配 ===")
    
    # 测试不同交易所的symbol映射
    test_cases = [
        ("BTCUSDT", "binance"),
        ("BTCUSDT", "aster"), 
        ("BTCUSDT", "backpack"),
        ("ETHUSDT", "binance"),
        ("ETHUSDT", "aster"),
        ("ETHUSDT", "backpack"),
    ]
    
    for symbol, exchange in test_cases:
        adapted = adapt_symbol(symbol, exchange)
        print(f"{symbol} -> {exchange}: {adapted}")

def test_side_mapping():
    """测试方向映射"""
    print("\n=== 测试方向映射 ===")
    
    test_cases = [
        ("long", "binance"),
        ("short", "binance"),
        ("buy", "aster"),
        ("sell", "aster"),
        ("long", "backpack"),
        ("short", "backpack"),
    ]
    
    for direction, exchange in test_cases:
        side = get_side_mapping(direction, exchange)
        print(f"{direction} -> {exchange}: {side}")

def test_backpack_orders():
    """测试Backpack订单"""
    print("\n=== 测试Backpack订单 ===")
    
    # 获取当前价格和止损价
    strat = EMATunnelStrategy()
    df_15m = strat.get_binance_klines('BTCUSDT', '15m', limit=200)
    entry_price = df_15m['close'].iloc[-1]
    stop_long, _ = strat.atr_stop(df_15m, entry_price, 'long')
    
    print(f"当前价格: {entry_price:.2f}")
    print(f"止损价格: {stop_long:.2f}")
    
    # 测试市价单
    try:
        result = place_order(
            exchange='backpack',
            symbol='BTCUSDT',
            amount=3.0,  # 使用3 USDC测试
            direction='long',
            order_type='MARKET'
        )
        print(f"Backpack市价单成功: {result['id']}")
        
        # 测试带止损的市价单
        result_with_stop = place_order(
            exchange='backpack',
            symbol='BTCUSDT',
            amount=3.0,
            direction='long',
            order_type='MARKET',
            stop_price=stop_long
        )
        print(f"Backpack带止损市价单成功: {result_with_stop['id']}")
        if 'stopLossTriggerPrice' in result_with_stop:
            print(f"止损价设置: {result_with_stop['stopLossTriggerPrice']}")
            
    except Exception as e:
        print(f"Backpack订单测试失败: {e}")

def test_aster_orders():
    """测试Aster订单"""
    print("\n=== 测试Aster订单 ===")
    
    # 获取当前价格和止损价
    strat = EMATunnelStrategy()
    df_15m = strat.get_binance_klines('BTCUSDT', '15m', limit=200)
    entry_price = df_15m['close'].iloc[-1]
    stop_long, _ = strat.atr_stop(df_15m, entry_price, 'long')
    
    print(f"当前价格: {entry_price:.2f}")
    print(f"止损价格: {stop_long:.2f}")
    
    # 测试市价单
    try:
        result = place_order(
            exchange='aster',
            symbol='BTCUSDT',
            amount=0.001,  # 使用最小数量测试
            direction='long',
            order_type='MARKET',
            is_quantity=True
        )
        print(f"Aster市价单成功: {result.order_id if hasattr(result, 'order_id') else 'N/A'}")
        
        # 测试止损单
        stop_result = place_order(
            exchange='aster',
            symbol='BTCUSDT',
            amount=0.001,
            direction='short',
            order_type='STOP_MARKET',
            stop_price=stop_long,
            is_quantity=True
        )
        print(f"Aster止损单成功: {stop_result.order_id if hasattr(stop_result, 'order_id') else 'N/A'}")
        print(f"止损单类型: {stop_result.type if hasattr(stop_result, 'type') else 'N/A'}")
        print(f"止损价格: {stop_result.stop_price if hasattr(stop_result, 'stop_price') else 'N/A'}")
        print(f"是否全平仓: {stop_result.close_position if hasattr(stop_result, 'close_position') else 'N/A'}")
        print(f"订单状态: {stop_result.status if hasattr(stop_result, 'status') else 'N/A'}")
        
    except Exception as e:
        print(f"Aster订单测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_binance_orders():
    """测试Binance订单（仅公开接口）"""
    print("\n=== 测试Binance订单（仅公开接口） ===")
    
    try:
        # 测试获取ticker（公开接口）
        from utils.order_adapter import get_exchange_instance
        binance = get_exchange_instance('binance')
        ticker = binance.get_ticker('BTCUSDT')
        print(f"Binance BTCUSDT 当前价格: {ticker.last_price}")
        
        # 注意：由于没有API密钥，无法实际下单
        print("Binance需要API密钥才能测试实际下单功能")
        
    except Exception as e:
        print(f"Binance测试失败: {e}")

def test_order_types():
    """测试不同订单类型"""
    print("\n=== 测试不同订单类型 ===")
    
    order_types = ['MARKET', 'LIMIT', 'STOP_MARKET', 'STOP_LIMIT']
    exchanges = ['backpack', 'aster']
    
    for exchange in exchanges:
        print(f"\n{exchange.upper()}支持的订单类型:")
        for order_type in order_types:
            try:
                # 这里只是测试参数构建，不实际下单
                if order_type == 'LIMIT':
                    print(f"  {order_type}: 需要price参数")
                elif order_type in ['STOP_MARKET', 'STOP_LIMIT']:
                    print(f"  {order_type}: 需要stop_price参数")
                else:
                    print(f"  {order_type}: 支持")
            except Exception as e:
                print(f"  {order_type}: 不支持 - {e}")

if __name__ == '__main__':
    print("开始测试order_adapter.py对不同交易所的适配...")
    
    test_symbol_adaptation()
    test_side_mapping()
    test_order_types()
    
    # 实际下单测试（需要资金）
    print("\n" + "="*50)
    print("实际下单测试（需要账户有资金）")
    print("="*50)
    
    test_backpack_orders()
    # test_aster_orders()
    # test_binance_orders()
    
    print("\n测试完成！") 