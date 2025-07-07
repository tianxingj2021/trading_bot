#!/usr/bin/env python3
"""
测试修改后的EMA趋势策略在Backpack交易所的开仓和条件单补发功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.ema_trend_strategy import EMATrendStrategy
from utils.order_adapter import get_exchange_instance, adapt_symbol, place_order
import time

def main():
    print("=== 测试EMA趋势策略Backpack开仓和条件单补发（跳过K线拉取） ===")
    
    # 创建策略实例
    strategy = EMATrendStrategy(atr_period=14, atr_mult=2, risk_reward_ratio=2)
    
    # 配置参数
    exchange = 'backpack'
    symbol = 'BTCUSDT'
    leverage = 50
    risk_pct = 0.05
    atr_distance = 50  # 止损距离
    risk_reward_ratio = 2
    
    print(f"交易所: {exchange}")
    print(f"交易对: {symbol}")
    print(f"杠杆: {leverage}")
    print(f"风险比例: {risk_pct}")
    print()
    
    try:
        # 获取当前价格
        from utils.order_adapter import get_latest_price
        current_price = get_latest_price(exchange, symbol)
        print(f"当前价格: {current_price}")
        
        # 检查是否有持仓
        ex = get_exchange_instance(exchange)
        positions = ex.get_positions()
        has_position = False
        for pos in positions:
            if (getattr(pos, 'symbol', None) or pos.get('symbol')) == adapt_symbol(symbol, exchange):
                pos_qty = float(getattr(pos, 'netQuantity', 0) or pos.get('netQuantity', 0) or pos.get('positionAmt', 0) or getattr(pos, 'positionAmt', 0) or 0)
                if pos_qty != 0:
                    has_position = True
                    print(f"检测到现有持仓: {pos_qty}")
                    break
        
        if has_position:
            print("已有持仓，先平仓再测试...")
            from utils.order_adapter import close_position
            close_result = close_position(exchange, symbol, 'long')
            print(f"平仓结果: {close_result}")
            time.sleep(3)
            positions = ex.get_positions()
            has_position = False
            for pos in positions:
                if (getattr(pos, 'symbol', None) or pos.get('symbol')) == adapt_symbol(symbol, exchange):
                    pos_qty = float(getattr(pos, 'netQuantity', 0) or pos.get('netQuantity', 0) or pos.get('positionAmt', 0) or getattr(pos, 'positionAmt', 0) or 0)
                    if pos_qty != 0:
                        has_position = True
                        print(f"平仓后仍有持仓: {pos_qty}")
                        break
            if has_position:
                print("平仓失败，跳过开仓测试")
                return
            else:
                print("✅ 平仓成功，继续测试开仓")
        
        # 跳过K线，直接用当前市价和自定义距离
        print("\n=== 跳过K线，直接测试下单与条件单补发 ===")
        stop_price = round(current_price - atr_distance, 2)
        take_profit_price = round(current_price + atr_distance * risk_reward_ratio, 2)
        print(f"开仓价: {current_price}")
        print(f"止损价: {stop_price}")
        print(f"止盈价: {take_profit_price}")
        
        # 计算头寸规模
        position_size = strategy.recommend_position_size_by_account(
            exchange, symbol, leverage, atr_distance, current_price, risk_pct
        )
        print(f"推荐头寸: {position_size}")
        if position_size <= 0:
            print("头寸规模过小，跳过开仓")
            return
        
        # 直接开多
        print("\n=== 市价开多 ===")
        order_result = place_order(
            exchange=exchange,
            symbol=symbol,
            amount=position_size,
            direction='long',
            order_type='MARKET',
            leverage=leverage,
            is_quantity=True
        )
        print(f"市价单下单结果: {order_result}")
        time.sleep(2)
        
        # 获取最新持仓数量
        positions = ex.get_positions()
        pos_qty = None
        for pos in positions:
            if (getattr(pos, 'symbol', None) or pos.get('symbol')) == adapt_symbol(symbol, exchange):
                pos_qty = str(pos.get('netQuantity') or getattr(pos, 'netQuantity', None) or pos.get('positionAmt', None) or getattr(pos, 'positionAmt', None))
        if not pos_qty or float(pos_qty) == 0:
            print('❌ 未获取到持仓数量，测试失败')
            return
        print(f'✅ 持仓数量: {pos_qty}')
        
        # 获取当前标记价格并检查距离安全性
        mark_price = strategy.get_mark_price(ex, adapt_symbol(symbol, exchange))
        if mark_price is None:
            print('❌ 无法获取标记价格，测试失败')
            return
        print(f'✅ 当前标记价格: {mark_price}')
        
        sl_safe, sl_msg = strategy.check_price_distance(mark_price, stop_price, "止损")
        tp_safe, tp_msg = strategy.check_price_distance(mark_price, take_profit_price, "止盈")
        print(f'止损距离检查: {"✅" if sl_safe else "❌"} {sl_msg}')
        print(f'止盈距离检查: {"✅" if tp_safe else "❌"} {tp_msg}')
        if not sl_safe or not tp_safe:
            print('⚠️  警告：价格距离过近，条件单可能被立即触发！')
            print('建议：扩大止损距离或等待价格波动后再补发条件单')
            return
        
        # 补发止损单
        print("\n--- 补发止损单 ---")
        sl_success = strategy.create_trigger_order(
            ex, 
            adapt_symbol(symbol, exchange), 
            'Ask',  # 平多用Ask
            pos_qty, 
            stop_price, 
            "止损"
        )
        
        # 补发止盈单
        print("\n--- 补发止盈单 ---")
        tp_success = strategy.create_trigger_order(
            ex, 
            adapt_symbol(symbol, exchange), 
            'Ask',  # 平多用Ask
            pos_qty, 
            take_profit_price, 
            "止盈"
        )
        
        if sl_success and tp_success:
            print('\n🎉 测试成功！独立的止损单和止盈单已正确挂单，不会被立即触发')
        else:
            print('\n💥 测试失败！请检查错误信息')
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main() 