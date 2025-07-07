#!/usr/bin/env python3
"""
专门测试Aster止损单功能
"""
from utils.order_adapter import place_order, get_exchange_instance
from strategies.ema_tunnel_strategy import EMATunnelStrategy

def test_aster_stop_market():
    """测试Aster的STOP_MARKET止损单"""
    print("=== 测试Aster的STOP_MARKET止损单 ===")
    
    # 获取当前价格和止损价
    strat = EMATunnelStrategy()
    df_15m = strat.get_binance_klines('BTCUSDT', '15m', limit=200)
    entry_price = df_15m['close'].iloc[-1]
    stop_long, _ = strat.atr_stop(df_15m, entry_price, 'long')
    
    print(f"当前价格: {entry_price:.2f}")
    print(f"止损价格: {stop_long:.2f}")
    
    try:
        # 先开一个多头仓位
        print("\n1. 开多头仓位...")
        long_order = place_order(
            exchange='aster',
            symbol='BTCUSDT',
            amount=0.001,  # 最小数量
            direction='long',
            order_type='MARKET',
            is_quantity=True
        )
        print(f"开仓成功: {long_order.orderId if hasattr(long_order, 'orderId') else 'N/A'}")
        
        # 设置止损单
        print("\n2. 设置止损单...")
        stop_order = place_order(
            exchange='aster',
            symbol='BTCUSDT',
            amount=0.001,  # 这个参数在STOP_MARKET+closePosition=true时会被忽略
            direction='short',  # 平多仓
            order_type='STOP_MARKET',
            stop_price=stop_long,
            is_quantity=True  # 这个参数在STOP_MARKET+closePosition=true时会被忽略
        )
        print(f"止损单设置成功: {stop_order.order_id if hasattr(stop_order, 'order_id') else 'N/A'}")
        
        # 检查止损单参数
        print(f"止损单类型: {stop_order.type if hasattr(stop_order, 'type') else 'N/A'}")
        print(f"止损价格: {stop_order.stop_price if hasattr(stop_order, 'stop_price') else 'N/A'}")
        print(f"是否全平仓: {stop_order.close_position if hasattr(stop_order, 'close_position') else 'N/A'}")
        print(f"订单状态: {stop_order.status if hasattr(stop_order, 'status') else 'N/A'}")
        print(f"是否仅减仓: {stop_order.reduce_only if hasattr(stop_order, 'reduce_only') else 'N/A'}")
        
        # 详细打印订单对象的所有属性
        print("\n订单对象详细信息:")
        print(f"订单对象类型: {type(stop_order)}")
        print(f"订单对象属性: {dir(stop_order)}")
        if hasattr(stop_order, '__dict__'):
            print(f"订单对象字典: {stop_order.__dict__}")
        else:
            print("订单对象没有__dict__属性")
        
    except Exception as e:
        print(f"Aster止损单测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_aster_stop():
    """测试Aster的STOP止损单（限价止损单）"""
    print("\n=== 测试Aster的STOP止损单（限价止损单） ===")
    
    # 获取当前价格和止损价
    strat = EMATunnelStrategy()
    df_15m = strat.get_binance_klines('BTCUSDT', '15m', limit=200)
    entry_price = df_15m['close'].iloc[-1]
    stop_long, _ = strat.atr_stop(df_15m, entry_price, 'long')
    
    print(f"当前价格: {entry_price:.2f}")
    print(f"止损价格: {stop_long:.2f}")
    
    try:
        # 设置STOP止损单（限价止损单）
        print("\n设置STOP止损单...")
        stop_order = place_order(
            exchange='aster',
            symbol='BTCUSDT',
            amount=0.001,
            direction='short',
            order_type='STOP',
            stop_price=stop_long,
            price=stop_long - 10,  # 限价单价格，比止损价低10个点
            is_quantity=True
        )
        print(f"STOP止损单设置成功: {stop_order.order_id if hasattr(stop_order, 'order_id') else 'N/A'}")
        
        # 检查止损单参数
        print(f"止损单类型: {stop_order.type if hasattr(stop_order, 'type') else 'N/A'}")
        print(f"止损价格: {stop_order.stop_price if hasattr(stop_order, 'stop_price') else 'N/A'}")
        print(f"限价: {stop_order.price if hasattr(stop_order, 'price') else 'N/A'}")
        print(f"数量: {stop_order.quantity if hasattr(stop_order, 'quantity') else 'N/A'}")
        print(f"是否仅减仓: {stop_order.reduce_only if hasattr(stop_order, 'reduce_only') else 'N/A'}")
        
        # 详细打印订单对象的所有属性
        print("\nSTOP订单对象详细信息:")
        print(f"订单对象类型: {type(stop_order)}")
        print(f"订单对象属性: {dir(stop_order)}")
        if hasattr(stop_order, '__dict__'):
            print(f"订单对象字典: {stop_order.__dict__}")
        else:
            print("订单对象没有__dict__属性")
        
    except Exception as e:
        print(f"Aster STOP止损单测试失败: {e}")
        import traceback
        traceback.print_exc()

def check_aster_positions():
    """检查Aster当前持仓"""
    print("\n=== 检查Aster当前持仓 ===")
    
    try:
        aster = get_exchange_instance('aster')
        account = aster.get_account()
        positions = account.positions if hasattr(account, 'positions') else []
        
        print("当前持仓:")
        for pos in positions:
            pos_symbol = getattr(pos, 'symbol', None) or pos.get('symbol')
            pos_amt = float(getattr(pos, 'position_amt', 0) or pos.get('positionAmt', 0) or 0)
            if pos_amt != 0:
                print(f"  {pos_symbol}: {pos_amt}")
        
        if not any(float(getattr(pos, 'position_amt', 0) or pos.get('positionAmt', 0) or 0) != 0 for pos in positions):
            print("  无持仓")
            
    except Exception as e:
        print(f"检查持仓失败: {e}")

if __name__ == '__main__':
    print("开始测试Aster止损单功能...")
    
    check_aster_positions()
    test_aster_stop_market()
    test_aster_stop()
    
    print("\n测试完成！") 