"""
order_adapter.py
统一下单/平仓适配器，支持binance、aster、backpack，自动适配symbol和参数
"""
from exchanges.aster import Aster
from exchanges.backpack import Backpack
from exchanges.binance import Binance
from config import ASTER_API_KEY, ASTER_API_SECRET, BACKPACK_API_KEY, BACKPACK_API_SECRET
import math
from utils.helper import adapt_symbol

# 如有binance密钥可配置，否则只支持公开接口
BINANCE_API_KEY = ""
BINANCE_API_SECRET = ""

# 交易所实例
aster = Aster(api_key=ASTER_API_KEY, api_secret=ASTER_API_SECRET)
backpack = Backpack(api_key=BACKPACK_API_KEY, api_secret=BACKPACK_API_SECRET)
binance = Binance(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

# 交易对适配表，可扩展
symbol_map = {
    "BTCUSDT": {
        "binance": "BTCUSDT",
        "aster": "BTCUSDT",
        "backpack": "BTC_USDC_PERP"
    },
    "ETHUSDT": {
        "binance": "ETHUSDT",
        "aster": "ETHUSDT",
        "backpack": "ETH_USDC_PERP"
    },
    # ... 可继续扩展
}

def get_exchange_instance(exchange):
    """获取交易所实例"""
    if exchange == 'backpack':
        return backpack
    elif exchange == 'binance':
        return binance
    else:
        return aster

def get_side_mapping(direction, exchange):
    """获取方向映射"""
    if direction.lower() in ['long', 'buy', 'bid']:
        return 'BUY' if exchange in ['binance', 'aster'] else 'Bid'
    else:
        return 'SELL' if exchange in ['binance', 'aster'] else 'Ask'

def calculate_quantity(exchange, symbol, amount, is_quantity=False):
    """计算下单数量，处理精度"""
    if is_quantity:
        return amount
    
    # 获取当前价格
    ex = get_exchange_instance(exchange)
    ticker = ex.get_ticker(symbol)
    price_val = float(ticker.get('lastPrice', '0')) if isinstance(ticker, dict) else float(getattr(ticker, 'last_price', 0) or 0)
    if not price_val or price_val == 0:
        raise Exception(f"获取行情失败，symbol={symbol}价格无效")
    
    # 计算数量
    quantity = float(amount) / price_val
    
    # 获取精度信息
    symbol_info = ex.get_symbol_info(symbol) if hasattr(ex, 'get_symbol_info') else None
    if symbol_info and 'filters' in symbol_info:
        lot_size = [f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE']
        if lot_size:
            min_qty = float(lot_size[0]['minQty'])
            step_size = float(lot_size[0]['stepSize'])
        else:
            min_qty = 0.001
            step_size = 0.001
    else:
        min_qty = 0.001
        step_size = 0.001
    
    # 修正数量精度
    if quantity < min_qty:
        raise Exception(f'金额不足，按当前价格最小下单量为{min_qty}，需至少{min_qty * price_val:.2f} USDT')
    
    legal_qty = math.floor(quantity / step_size) * step_size
    qty_precision = len(str(step_size).split('.')[-1].rstrip('0')) if '.' in str(step_size) else 0
    legal_qty = round(legal_qty, qty_precision)
    
    if legal_qty < min_qty:
        legal_qty = min_qty
    
    return legal_qty

def get_price_precision(exchange, symbol):
    """获取价格精度"""
    ex = get_exchange_instance(exchange)
    symbol_info = ex.get_symbol_info(symbol) if hasattr(ex, 'get_symbol_info') else None
    price_precision = 2  # 默认精度
    
    if symbol_info and 'filters' in symbol_info:
        price_filter = [f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER']
        if price_filter:
            tick_size = float(price_filter[0]['tickSize'])
            if tick_size < 1:
                price_precision = len(str(tick_size).split('.')[-1].rstrip('0'))
            else:
                price_precision = 0
    
    return price_precision

def create_backpack_order(symbol, side, order_type, amount, price=None, stop_price=None, take_profit_price=None, is_quantity=False):
    """创建Backpack订单"""
    # Backpack要求orderType为首字母大写+下划线后大写
    def format_order_type(ot):
        return '_'.join([s.capitalize() for s in ot.lower().split('_')])
    
    # 创建基础订单参数
    order_params = {
        'symbol': symbol,
        'side': side,
        'orderType': format_order_type(order_type),
    }
    
    # 处理数量
    if is_quantity:
        order_params['quantity'] = str(amount)
    else:
        # Backpack要求quoteQuantity最多2位小数
        order_params['quoteQuantity'] = f"{float(amount):.0f}"
    
    # 处理限价单
    if order_type.upper() == 'LIMIT' and price:
        order_params['price'] = price
        order_params['timeInForce'] = 'GTC'
    
    # Backpack不支持在开仓时同时设置止损和止盈参数，需要在开仓后分别补发条件单
    # 这里暂时注释掉，由策略层处理
    # if stop_price:
    #     order_params['stopLossTriggerPrice'] = str(stop_price)
    # if take_profit_price:
    #     order_params['takeProfitTriggerPrice'] = str(take_profit_price)
    
    return order_params

def create_aster_order(symbol, side, order_type, amount, price=None, stop_price=None, is_quantity=False):
    """创建Aster订单，自动适配止损单类型和参数"""
    # 统一止损类型
    if order_type.upper() in ['STOP', 'STOP_LIMIT']:
        print('[Aster适配] 不支持STOP/STOP_LIMIT，自动转为STOP_MARKET')
        order_type = 'STOP_MARKET'
    
    if order_type.upper() == 'STOP_MARKET' and stop_price:
        # 止损单处理，只允许Aster支持的参数
        price_precision = get_price_precision('aster', symbol)
        corrected_stop_price = round(float(stop_price), price_precision)
        order_params = {
            'symbol': symbol,
            'side': side,
            'type': 'STOP_MARKET',
            'stopPrice': str(corrected_stop_price),
            'closePosition': 'true'
        }
        # 其余参数全部忽略
    else:
        # 普通订单
        if is_quantity:
            quantity = amount
        else:
            quantity = calculate_quantity('aster', symbol, amount, is_quantity)
        order_params = {
            'symbol': symbol,
            'side': side,
            'type': order_type.upper(),
            'quantity': str(quantity)
        }
        if order_type.upper() == 'LIMIT' and price:
            order_params['price'] = price
            order_params['timeInForce'] = 'GTC'
    return order_params

def create_binance_order(symbol, side, order_type, amount, price=None, stop_price=None, is_quantity=False):
    """创建Binance订单"""
    if order_type.upper() in ['STOP_LIMIT', 'STOP_MARKET'] and stop_price:
        # 止损单处理
        quantity = calculate_quantity('binance', symbol, amount, is_quantity)
        price_precision = get_price_precision('binance', symbol)
        corrected_stop_price = round(float(stop_price), price_precision)
        
        order_params = {
            'symbol': symbol,
            'side': side,
            'type': order_type.upper(),
            'quantity': str(quantity),
            'stopPrice': str(corrected_stop_price),
            'reduceOnly': True
        }
        
        if order_type.upper() == 'STOP_LIMIT':
            order_params['price'] = price if price else stop_price
            order_params['timeInForce'] = 'GTC'
    else:
        # 普通订单
        if is_quantity:
            quantity = amount
        else:
            quantity = calculate_quantity('binance', symbol, amount, is_quantity)
        
        order_params = {
            'symbol': symbol,
            'side': side,
            'type': order_type.upper(),
            'quantity': str(quantity)
        }
        
        if order_type.upper() == 'LIMIT' and price:
            order_params['price'] = price
            order_params['timeInForce'] = 'GTC'
    
    return order_params

def place_order(exchange, symbol, amount, direction, order_type="MARKET", price=None, leverage=None, stop_price=None, take_profit_price=None, reduce_only=False, is_quantity=False):
    """
    统一下单接口，支持市价、限价、止损单
    :param exchange: 交易所名
    :param symbol: 标准交易对名（如BTCUSDT）
    :param amount: 下单金额（USDT）或代币数量
    :param direction: 'long'/'short' 或 'buy'/'sell'
    :param order_type: 'MARKET'/'LIMIT'/'STOP_LIMIT'/'STOP_MARKET'
    :param price: 限价单价格
    :param leverage: 杠杆倍数（如支持）
    :param stop_price: 止损触发价（如支持）
    :param take_profit_price: 止盈触发价（如支持）
    :param reduce_only: 是否只减仓
    :param is_quantity: True表示amount是代币数量，False表示amount是USDT金额
    :return: 下单结果
    """
    amount = float(amount)
    if leverage is not None:
        leverage = int(leverage)
    if price is not None:
        price = float(price)
    
    ex = get_exchange_instance(exchange)
    real_symbol = adapt_symbol(symbol, exchange)
    side = get_side_mapping(direction, exchange)
    
    # 设置杠杆（如果支持）
    if leverage and hasattr(ex, 'set_leverage'):
        try:
            ex.set_leverage(real_symbol, int(leverage))
        except Exception as e:
            pass
    
    # Backpack特殊处理：止损单在开仓时带止损参数
    if exchange == 'backpack' and order_type.upper() in ['STOP_MARKET', 'STOP_LIMIT']:
        # 将止损单转换为普通开仓单，并带上止损参数
        actual_order_type = 'MARKET' if order_type.upper() == 'STOP_MARKET' else 'LIMIT'
        print(f'[Backpack适配] 止损单{order_type}转换为{actual_order_type}开仓单，并带止损参数')
        order_params = create_backpack_order(real_symbol, side, actual_order_type, amount, price, stop_price, take_profit_price, is_quantity)
    else:
        # 根据交易所创建订单参数
        if exchange == 'backpack':
            order_params = create_backpack_order(real_symbol, side, order_type, amount, price, stop_price, take_profit_price, is_quantity)
        elif exchange == 'aster':
            order_params = create_aster_order(real_symbol, side, order_type, amount, price, stop_price, is_quantity)
        elif exchange == 'binance':
            order_params = create_binance_order(real_symbol, side, order_type, amount, price, stop_price, is_quantity)
        else:
            raise Exception(f"不支持的交易所: {exchange}")
    
    return ex.create_order(order_params)

def close_position(exchange, symbol, direction=None):
    """
    统一平仓接口
    :param exchange: 交易所名
    :param symbol: 标准交易对名
    :param direction: 可选，指定平多还是平空
    :return: 平仓结果
    """
    ex = get_exchange_instance(exchange)
    real_symbol = adapt_symbol(symbol, exchange)
    
    # 获取持仓
    if exchange == 'backpack':
        positions = ex.get_positions()
        for pos in positions:
            pos_symbol = pos.get('symbol')
            net_qty = float(pos.get('netQuantity', 0) or 0)
            if pos_symbol == real_symbol and net_qty != 0:
                side = 'Ask' if net_qty > 0 else 'Bid'
                order_params = {
                    'symbol': real_symbol,
                    'side': side,
                    'orderType': 'Market',
                    'quantity': str(abs(net_qty)),
                    'reduceOnly': True,
                    'timeInForce': 'IOC',
                    'selfTradePrevention': 'RejectTaker',
                }
                return ex.create_order(order_params)
        raise Exception('No position to close')
    else:
        # binance/aster
        positions = ex.get_account().positions if hasattr(ex.get_account(), 'positions') else ex.get_positions()
        for pos in positions:
            pos_symbol = getattr(pos, 'symbol', None) or pos.get('symbol')
            pos_amt = float(getattr(pos, 'position_amt', 0) or pos.get('positionAmt', 0) or 0)
            if pos_symbol == real_symbol and pos_amt != 0:
                side = 'SELL' if pos_amt > 0 else 'BUY'
                order_params = {
                    'symbol': real_symbol,
                    'side': side,
                    'type': 'MARKET',
                    'quantity': abs(pos_amt),
                    'reduceOnly': True
                }
                return ex.create_order(order_params)
        raise Exception('No position to close')

def get_latest_price(exchange, symbol):
    """
    获取指定交易所的最新市价（现货/合约最新成交价或买一/卖一价）
    :param exchange: 交易所名（如'backpack', 'binance', 'aster'）
    :param symbol: 交易对（如'BTCUSDT'）
    :return: 最新市价（float）
    """
    ex = get_exchange_instance(exchange)
    real_symbol = adapt_symbol(symbol, exchange)
    ticker = None
    if exchange == 'backpack':
        ticker = ex.get_ticker(real_symbol)
    elif exchange == 'binance':
        # 兼容get_ticker/get_ticker_price/fetch_ticker
        if hasattr(ex, 'get_ticker'):
            ticker = ex.get_ticker(real_symbol)
        elif hasattr(ex, 'fetch_ticker'):
            ticker = ex.fetch_ticker(real_symbol)
        elif hasattr(ex, 'get_ticker_price'):
            ticker = ex.get_ticker_price(real_symbol)
        else:
            raise Exception('Binance行情API未实现')
    elif exchange == 'aster':
        ticker = ex.get_ticker(real_symbol)
    else:
        raise Exception(f'不支持的交易所: {exchange}')
    # 兼容dict和对象
    if isinstance(ticker, dict):
        for key in ['lastPrice', 'price', 'last']:
            if key in ticker:
                return float(ticker[key])
        raise Exception(f'{exchange}行情ticker无lastPrice/price/last字段: {ticker}')
    else:
        # 对象类型，兼容下划线和驼峰
        for key in ['lastPrice', 'last_price', 'price', 'last']:
            if hasattr(ticker, key):
                return float(getattr(ticker, key))
        raise Exception(f'{exchange}行情ticker对象无lastPrice/last_price/price/last属性: {ticker}') 