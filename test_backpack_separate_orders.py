#!/usr/bin/env python3
"""
Backpack独立止损止盈单测试
分别创建独立的止损单和止盈单，而不是在一个订单上同时设置两个触发条件
"""

import sys
import os
import time
from utils.order_adapter import place_order, get_latest_price, get_exchange_instance, adapt_symbol

# 配置
symbol = 'BTCUSDT'
exchange = 'backpack'
leverage = 50
order_amount = 10  # USDC
atr_distance = 50  # 止损距离（绝对值）
risk_reward_ratio = 2  # 盈亏比

def get_mark_price(exchange_instance, symbol):
    """获取标记价格"""
    try:
        ticker = exchange_instance.get_ticker(symbol)
        mark_price = None
        for k in ['markPrice', 'mark_price', 'price', 'lastPrice', 'last_price']:
            if isinstance(ticker, dict) and k in ticker:
                mark_price = float(ticker[k])
                break
            elif hasattr(ticker, k):
                mark_price = float(getattr(ticker, k))
                break
        return mark_price
    except Exception as e:
        print(f'获取标记价格异常: {e}')
        return None

def check_price_distance(mark_price, trigger_price, trigger_type):
    """检查触发价与标记价格的距离"""
    if mark_price is None:
        return False, "无法获取标记价格"
    
    distance = abs(mark_price - trigger_price)
    min_safe_distance = 20  # 最小安全距离
    
    if distance < min_safe_distance:
        return False, f"{trigger_type}触发价({trigger_price})与标记价格({mark_price})距离({distance})过近，可能被立即触发！"
    
    return True, f"{trigger_type}触发价({trigger_price})与标记价格({mark_price})距离({distance})安全"

def create_trigger_order(exchange_instance, symbol, side, quantity, trigger_price, order_type="stop_loss"):
    """创建独立的触发单，必须同时传triggerPrice和triggerQuantity"""
    try:
        order_data = {
            'symbol': symbol,
            'side': side,
            'orderType': 'Market',
            'quantity': quantity,
            'reduceOnly': True,
            'triggerPrice': str(trigger_price),
            'triggerQuantity': str(quantity)  # 必须加上
        }
        print(f'{order_type}条件单参数:')
        for key, value in order_data.items():
            print(f'  {key}: {value}')
        print(f'\n发送{order_type}条件单...')
        order_result = exchange_instance.create_order(order_data)
        print(f'✅ {order_type}条件单下单成功:', order_result)
        if isinstance(order_result, dict):
            order_id = order_result.get('id')
            status = order_result.get('status')
            print(f'订单ID: {order_id}')
            print(f'订单状态: {status}')
            if status == 'Filled':
                print(f'❌ {order_type}条件单被立即执行了！')
                return False
            elif status in ['New', 'PartiallyFilled', 'TriggerPending']:
                print(f'✅ {order_type}条件单已挂单，等待触发')
                return True
            else:
                print(f'⚠️  {order_type}订单状态异常: {status}')
                return False
        else:
            print(f'✅ {order_type}条件单创建成功')
            return True
    except Exception as e:
        print(f'❌ {order_type}条件单下单异常: {e}')
        return False

def main():
    print('=== Backpack独立止损止盈单测试 ===')
    print(f'交易对: {symbol}')
    print(f'交易所: {exchange}')
    print(f'杠杆: {leverage}')
    print(f'下单金额: {order_amount} USDC')
    print(f'止损距离: {atr_distance}')
    print(f'盈亏比: {risk_reward_ratio}')
    print()

    # 步骤1：下市价单开仓
    print('=== 步骤1：下市价单开仓 ===')
    try:
        order_result = place_order(
            exchange=exchange,
            symbol=symbol,
            amount=order_amount,
            direction='long',
            order_type='MARKET',
            leverage=leverage,
            is_quantity=False
        )
        print('市价单下单结果:', order_result)
        
        # 获取实际成交价
        executed_price = None
        if isinstance(order_result, dict):
            executed_price = float(order_result.get('avgPrice') or order_result.get('executedPrice') or order_result.get('price') or 0)
            if not executed_price and 'fills' in order_result and order_result['fills']:
                executed_price = float(order_result['fills'][0].get('price', 0))
            if (not executed_price or executed_price == 0) and order_result.get('executedQuantity') and order_result.get('executedQuoteQuantity'):
                try:
                    executed_qty = float(order_result['executedQuantity'])
                    executed_quote = float(order_result['executedQuoteQuantity'])
                    if executed_qty:
                        executed_price = executed_quote / executed_qty
                except Exception as e:
                    print('计算成交价异常:', e)
        
        if not executed_price or executed_price == 0:
            print('❌ 未获取到实际成交价，测试失败')
            return False
        
        print(f'✅ 实际成交价: {executed_price}')
        
    except Exception as e:
        print(f'❌ 市价单下单异常: {e}')
        return False

    # 等待一下确保订单处理完成
    time.sleep(2)

    # 步骤2：获取最新持仓
    print('\n=== 步骤2：获取持仓信息 ===')
    ex = get_exchange_instance(exchange)
    positions = ex.get_positions()
    pos_qty = None
    for pos in positions:
        if (getattr(pos, 'symbol', None) or pos.get('symbol')) == adapt_symbol(symbol, exchange):
            pos_qty = str(pos.get('netQuantity') or getattr(pos, 'netQuantity', None) or pos.get('positionAmt', None) or getattr(pos, 'positionAmt', None))
    
    if not pos_qty or float(pos_qty) == 0:
        print('❌ 未获取到持仓数量，测试失败')
        return False
    
    print(f'✅ 持仓数量: {pos_qty}')

    # 步骤3：获取当前标记价格
    print('\n=== 步骤3：获取标记价格 ===')
    mark_price = get_mark_price(ex, adapt_symbol(symbol, exchange))
    if mark_price is None:
        print('❌ 无法获取标记价格，测试失败')
        return False
    
    print(f'✅ 当前标记价格: {mark_price}')

    # 步骤4：计算止盈止损价格
    print('\n=== 步骤4：计算止盈止损价格 ===')
    stop_loss_price = round(executed_price - atr_distance, 2)
    take_profit_price = round(executed_price + atr_distance * risk_reward_ratio, 2)
    
    print(f'开仓价: {executed_price}')
    print(f'止损价: {stop_loss_price}')
    print(f'止盈价: {take_profit_price}')

    # 步骤5：检查价格距离安全性
    print('\n=== 步骤5：检查价格距离安全性 ===')
    sl_safe, sl_msg = check_price_distance(mark_price, stop_loss_price, "止损")
    tp_safe, tp_msg = check_price_distance(mark_price, take_profit_price, "止盈")
    
    print(f'止损距离检查: {"✅" if sl_safe else "❌"} {sl_msg}')
    print(f'止盈距离检查: {"✅" if tp_safe else "❌"} {tp_msg}')
    
    if not sl_safe or not tp_safe:
        print('⚠️  警告：价格距离过近，条件单可能被立即触发！')
        print('建议：扩大止损距离或等待价格波动后再测试')
        return False

    # 步骤6：分别创建独立的止损单和止盈单
    print('\n=== 步骤6：分别创建独立的止损单和止盈单 ===')
    
    # 创建止损单
    print('\n--- 创建止损单 ---')
    sl_success = create_trigger_order(
        ex, 
        adapt_symbol(symbol, exchange), 
        'Ask',  # 平多用Ask
        pos_qty, 
        stop_loss_price, 
        "止损"
    )
    
    if not sl_success:
        print('❌ 止损单创建失败')
        return False
    
    # 创建止盈单
    print('\n--- 创建止盈单 ---')
    tp_success = create_trigger_order(
        ex, 
        adapt_symbol(symbol, exchange), 
        'Ask',  # 平多用Ask
        pos_qty, 
        take_profit_price, 
        "止盈"
    )
    
    if not tp_success:
        print('❌ 止盈单创建失败')
        return False
    
    return True

if __name__ == '__main__':
    success = main()
    if success:
        print('\n🎉 测试成功！独立的止损单和止盈单已正确挂单，不会被立即触发')
    else:
        print('\n💥 测试失败！请检查错误信息')
        sys.exit(1) 