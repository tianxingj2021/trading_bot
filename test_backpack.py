import pprint
from exchanges.backpack import Backpack

pp = pprint.PrettyPrinter()

bp = Backpack()

# 打印所有symbol字段
symbols = bp.get_all_symbols()
print("Backpack交易所所有symbol:")
for s in symbols:
    print(s.get('symbol'))

# 优先选取带中划线的PERP symbol
SYMBOL = None
for s in symbols:
    sym = s.get('symbol', '')
    if 'PERP' in sym and '-' in sym:
        SYMBOL = sym
        break
if not SYMBOL:
    SYMBOL = symbols[0]['symbol'] if symbols else None
print(f"用于测试的symbol: {SYMBOL}")

def test_account():
    print("账户信息:")
    try:
        account = bp.get_account()
        pp.pprint(account)
    except Exception as e:
        print("获取账户信息异常:", e)

def test_balances():
    print("账户余额:")
    try:
        balances = bp.get_balances()
        pp.pprint(balances)
    except Exception as e:
        print("获取账户余额异常:", e)

def test_symbols():
    print("交易对:")
    pp.pprint(bp.get_all_symbols())

def test_leverage():
    print(f"{SYMBOL}最大杠杆:")
    print(bp.get_max_leverage(SYMBOL))
    
    print("SOL_USDC_PERP最大杠杆:")
    print(bp.get_max_leverage("SOL_USDC_PERP"))
    
    print("BTC_USDC_PERP最大杠杆:")
    print(bp.get_max_leverage("BTC_USDC_PERP"))
    
    print("ETH_USDC_PERP最大杠杆:")
    print(bp.get_max_leverage("ETH_USDC_PERP"))
    
    print("DOGE_USDC_PERP最大杠杆:")
    print(bp.get_max_leverage("DOGE_USDC_PERP"))

def test_depth():
    print(f"{SYMBOL}深度:")
    pp.pprint(bp.get_depth(SYMBOL))

def test_ticker():
    print(f"{SYMBOL} Ticker:")
    pp.pprint(bp.get_ticker(SYMBOL))

def test_klines():
    print(f"{SYMBOL} 1m K线:")
    pp.pprint(bp.get_klines(SYMBOL, "1m", 5))

def test_order():
    print("下市价单测试（使用1 USDC）:")
    try:
        order = bp.create_order({
            'symbol': SYMBOL,
            'side': 'Bid',
            'orderType': 'Market',
            'quoteQuantity': '1',  # 使用1 USDC下单
            'timeInForce': 'IOC',
            'selfTradePrevention': 'RejectTaker'
        })
        pp.pprint(order)
        print("查单:")
        order_id = order.get('id') or order.get('orderId')
        if order_id:
            pp.pprint(bp.get_order(SYMBOL, order_id=order_id))
        print("撤单:")
        bp.cancel_order(SYMBOL, order_id=order_id)
    except Exception as e:
        print("下单/撤单异常:", e)
        if hasattr(e, 'response') and e.response is not None:
            print("错误详情:", e.response.text)

def test_limit_order():
    print("下限价单测试（使用1 USDC）:")
    try:
        # 获取当前价格
        ticker = bp.get_ticker(SYMBOL)
        current_price = float(ticker['lastPrice'])
        # 限价单价格设为当前价格的95%
        limit_price = round(current_price * 0.95, 2)
        order = bp.create_order({
            'symbol': SYMBOL,
            'side': 'Bid',
            'orderType': 'Limit',
            'quoteQuantity': '1',  # 使用1 USDC下单
            'price': str(limit_price),
            'timeInForce': 'GTC',
            'selfTradePrevention': 'RejectTaker'
        })
        pp.pprint(order)
        print("查单:")
        order_id = order.get('id') or order.get('orderId')
        if order_id:
            pp.pprint(bp.get_order(SYMBOL, order_id=order_id))
        print("撤单:")
        bp.cancel_order(SYMBOL, order_id=order_id)
    except Exception as e:
        print("限价单测试异常:", e)
        if hasattr(e, 'response') and e.response is not None:
            print("错误详情:", e.response.text)

def test_orders():
    print("未成交订单:")
    pp.pprint(bp.get_open_orders(SYMBOL))
    print("成交历史:")
    try:
        trades = bp.get_user_trades(SYMBOL)
        pp.pprint(trades)
    except Exception as e:
        print("获取成交历史失败:", e)

def test_set_leverage():
    print("设置杠杆测试:")
    try:
        result = bp.set_leverage(SYMBOL, 5)
        pp.pprint(result)
    except Exception as e:
        print("设置杠杆异常:", e)

def test_symbol_info():
    print("交易对详细信息:")
    try:
        markets = bp.get_all_symbols()
        for market in markets:
            if market.get('symbol') == SYMBOL:
                pp.pprint(market)
                break
    except Exception as e:
        print("获取交易对信息异常:", e)

def test_positions():
    print("合约持仓信息:")
    try:
        positions = bp.get_positions()
        pp.pprint(positions)
    except Exception as e:
        print("获取持仓信息异常:", e)

def test_perp_order():
    print("合约市价单测试（使用SOL_USDC_PERP，1 USDC）:")
    try:
        order = bp.create_order({
            'symbol': 'SOL_USDC_PERP',
            'side': 'Bid',
            'orderType': 'Market',
            'quoteQuantity': '2',  # 使用1 USDC下单
            'timeInForce': 'IOC',
            'selfTradePrevention': 'RejectTaker'
        })
        pp.pprint(order)
        print("查单:")
        order_id = order.get('id') or order.get('orderId')
        if order_id:
            pp.pprint(bp.get_order('SOL_USDC_PERP', order_id=order_id))
        print("撤单:")
        bp.cancel_order('SOL_USDC_PERP', order_id=order_id)
    except Exception as e:
        print("合约下单异常:", e)
        if hasattr(e, 'response') and e.response is not None:
            print("错误详情:", e.response.text)

def test_perp_limit_order():
    print("合约限价单测试（使用SOL_USDC_PERP，1 USDC）:")
    try:
        # 获取当前价格
        ticker = bp.get_ticker('SOL_USDC_PERP')
        current_price = float(ticker['lastPrice'])
        # 限价单价格设为当前价格的95%
        limit_price = round(current_price * 0.95, 2)
        order = bp.create_order({
            'symbol': 'SOL_USDC_PERP',
            'side': 'Bid',
            'orderType': 'Limit',
            'quoteQuantity': '1',  # 使用1 USDC下单
            'price': str(limit_price),
            'timeInForce': 'GTC',
            'selfTradePrevention': 'RejectTaker'
        })
        pp.pprint(order)
        print("查单:")
        order_id = order.get('id') or order.get('orderId')
        if order_id:
            pp.pprint(bp.get_order('SOL_USDC_PERP', order_id=order_id))
        print("撤单:")
        bp.cancel_order('SOL_USDC_PERP', order_id=order_id)
    except Exception as e:
        print("合约限价单测试异常:", e)
        if hasattr(e, 'response') and e.response is not None:
            print("错误详情:", e.response.text)

def test_perp_symbol_info():
    print("合约交易对详细信息:")
    try:
        markets = bp.get_all_symbols()
        for market in markets:
            if market.get('symbol') == 'SOL_USDC_PERP':
                pp.pprint(market)
                break
    except Exception as e:
        print("获取合约交易对信息异常:", e)

def test_perp_close_position():
    print("合约市价平仓测试:")
    try:
        # 先查询当前持仓
        positions = bp.get_positions()
        print("当前持仓:")
        pp.pprint(positions)
        
        # 如果有持仓，进行平仓
        if positions:
            for position in positions:
                symbol = position['symbol']
                quantity = float(position['netQuantity'])
                if quantity != 0:
                    print(f"平仓 {symbol}, 数量: {quantity}")
                    # 市价平仓，使用相反方向
                    side = 'Ask' if quantity > 0 else 'Bid'  # 多头用Ask平仓，空头用Bid平仓
                    order = bp.create_order({
                        'symbol': symbol,
                        'side': side,
                        'orderType': 'Market',
                        'quantity': str(abs(quantity)),
                        'timeInForce': 'IOC',
                        'selfTradePrevention': 'RejectTaker'
                    })
                    print("平仓订单:")
                    pp.pprint(order)
                    
                    # 查询平仓后的持仓
                    print("平仓后持仓:")
                    new_positions = bp.get_positions()
                    pp.pprint(new_positions)
                    break
        else:
            print("当前无持仓")
    except Exception as e:
        print("平仓测试异常:", e)
        if hasattr(e, 'response') and e.response is not None:
            print("错误详情:", e.response.text)

def test_perp_limit_close():
    print("合约限价平仓测试:")
    try:
        # 先查询当前持仓
        positions = bp.get_positions()
        if positions:
            for position in positions:
                symbol = position['symbol']
                quantity = float(position['netQuantity'])
                if quantity != 0:
                    print(f"限价平仓 {symbol}, 数量: {quantity}")
                    # 获取当前价格
                    ticker = bp.get_ticker(symbol)
                    current_price = float(ticker['lastPrice'])
                    
                    # 限价平仓，价格设为当前价格的105%（确保能成交）
                    side = 'Ask' if quantity > 0 else 'Bid'
                    limit_price = round(current_price * 1.05, 2)
                    
                    order = bp.create_order({
                        'symbol': symbol,
                        'side': side,
                        'orderType': 'Limit',
                        'quantity': str(abs(quantity)),
                        'price': str(limit_price),
                        'timeInForce': 'GTC',
                        'selfTradePrevention': 'RejectTaker'
                    })
                    print("限价平仓订单:")
                    pp.pprint(order)
                    
                    # 查询订单状态
                    order_id = order.get('id')
                    if order_id:
                        print("查询平仓订单:")
                        pp.pprint(bp.get_order(symbol, order_id=order_id))
                    
                    break
        else:
            print("当前无持仓")
    except Exception as e:
        print("限价平仓测试异常:", e)
        if hasattr(e, 'response') and e.response is not None:
            print("错误详情:", e.response.text)

if __name__ == "__main__":
    # test_account()  # 测试账户信息
    test_balances()  # 测试账户余额
    # test_positions()  # 测试合约持仓
    # test_perp_symbol_info()  # 测试合约交易对信息
    # test_symbol_info()  # 测试现货交易对信息
    # test_depth()
    # test_ticker()
    # test_klines()
    # test_order()  # 测试现货市价单
    # test_limit_order()  # 测试现货限价单
    test_perp_order()  # 开仓
    # test_perp_limit_close()  # 测试合约限价平仓
    test_perp_close_position()  # 测试合约市价平仓
    # test_orders()
    # test_leverage() 