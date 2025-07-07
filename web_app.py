"""
Aster交易所Web管理界面
"""
from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request, jsonify
import asyncio
import json
from datetime import datetime
from exchanges.aster import Aster
from exchanges.backpack import Backpack
from config import ASTER_API_KEY, ASTER_API_SECRET, BACKPACK_API_KEY, BACKPACK_API_SECRET
from log_settings.log import logger
import traceback
import math
import decimal
from decimal import Decimal
import pandas as pd
import numpy as np
from utils.order_adapter import place_order as unified_place_order, close_position as unified_close_position
from strategies.ema_tunnel_strategy import EMATunnelStrategy
import subprocess
import signal
import sys
import os
from flask_socketio import SocketIO, emit
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化Aster交易所实例
aster = Aster(api_key=ASTER_API_KEY, api_secret=ASTER_API_SECRET)
backpack = Backpack(api_key=BACKPACK_API_KEY, api_secret=BACKPACK_API_SECRET)

# 全局策略单例，解决重复下单问题
global_strategy = EMATunnelStrategy()

ema_trend_proc = None

def get_exchange_instance(exchange):
    if exchange == 'backpack':
        return backpack
    return aster

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/account')
def get_account():
    """获取账户信息"""
    exchange = request.args.get('exchange') or (request.json.get('exchange') if request.is_json else None)
    logger.info('收到的exchange参数: %s', exchange)
    ex = get_exchange_instance(exchange)
    logger.info('ex实例类型: %s', type(ex))
    from config import BACKPACK_API_KEY, BACKPACK_API_SECRET
    logger.info('web_app.py用的BACKPACK_API_KEY: %s', BACKPACK_API_KEY[:8] if BACKPACK_API_KEY else '未设置')
    logger.info('web_app.py用的BACKPACK_API_SECRET: %s', BACKPACK_API_SECRET[:8] if BACKPACK_API_SECRET else '未设置')
    try:
        if exchange == 'backpack':
            balances = ex.get_balances()
            assets = []
            for asset, info in balances.items():
                try:
                    if isinstance(info, dict) and 'available' in info:
                        assets.append({'asset': asset, 'walletBalance': info['available']})
                except Exception as e:
                    logger.exception(f'解析资产{asset}失败: {e}')
                    continue
            # 获取持仓信息
            positions = ex.get_positions()
            account_dict = {'assets': assets, 'positions': positions}
        else:
            account = ex.get_account()
            account_dict = json.loads(json.dumps(account, default=lambda o: o.__dict__))
            def to_camel(s):
                parts = s.split('_')
                return parts[0] + ''.join(x.title() for x in parts[1:])
            assets_camel = []
            for asset in account_dict.get('assets', []):
                asset_camel = {to_camel(k): v for k, v in asset.items()}
                assets_camel.append(asset_camel)
            account_dict['assets'] = assets_camel
            positions_camel = []
            for pos in account_dict.get('positions', []):
                pos_camel = {to_camel(k): v for k, v in pos.items()}
                positions_camel.append(pos_camel)
            account_dict['positions'] = positions_camel
        positions = account_dict.get('positions', [])
        return jsonify({'success': True, 'account': account_dict, 'positions': positions})
    except Exception as e:
        logger.exception('接口异常: %s', e)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/orderbook/<symbol>')
def get_orderbook(symbol):
    """获取订单簿"""
    exchange = request.args.get('exchange')
    ex = get_exchange_instance(exchange)
    try:
        orderbook = ex.get_depth(symbol, 10)
        # 兼容AsterDepth对象和dict
        if hasattr(orderbook, "asks") and hasattr(orderbook, "bids"):
            asks = [[float(x.price), float(x.quantity)] for x in orderbook.asks]
            bids = [[float(x.price), float(x.quantity)] for x in orderbook.bids]
        else:
            asks = [[float(x[0]), float(x[1])] for x in orderbook['asks']]
            bids = [[float(x[0]), float(x[1])] for x in orderbook['bids']]
        # Backpack盘口顺序修正：只reverse bids
        if exchange == 'backpack':
            bids = bids[::-1]
        return jsonify({
            'success': True,
            'orderbook': {'asks': asks, 'bids': bids}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/symbols')
def get_symbols():
    """获取交易对列表"""
    try:
        exchange_info = aster.get_exchange_info()
        symbols = []
        for symbol_info in exchange_info.get('symbols', []):
            if symbol_info.get('status') == 'TRADING':
                symbols.append({
                    'symbol': symbol_info['symbol'],
                    'baseAsset': symbol_info['baseAsset'],
                    'quoteAsset': symbol_info['quoteAsset'],
                    'pricePrecision': symbol_info['pricePrecision'],
                    'quantityPrecision': symbol_info['quantityPrecision']
                })
        return jsonify({
            'success': True,
            'symbols': symbols
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/leverage', methods=['POST'])
def set_leverage():
    """设置杠杆"""
    data = request.json
    exchange = data.get('exchange')
    ex = get_exchange_instance(exchange)
    try:
        symbol = data.get('symbol')
        leverage = data.get('leverage')
        
        result = ex.set_leverage(symbol, leverage)
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/order', methods=['POST'])
def place_order():
    """下单"""
    data = request.json
    exchange = data.get('exchange')
    ex = get_exchange_instance(exchange)
    try:
        symbol = data.get('symbol')
        side = data.get('side')
        order_type = data.get('type')
        quantity = data.get('quantity')
        price = data.get('price')
        usdt_amount = data.get('usdt_amount')
        quote_quantity = data.get('quoteQuantity')
        # 定义format_decimal函数（所有交易所通用）
        def format_decimal(val):
            # 先转为Decimal，normalize去掉科学计数法
            d = Decimal(str(val)).normalize()
            s = format(d, 'f')
            return s.rstrip('0').rstrip('.') if '.' in s else s
        
        # Backpack专用参数映射
        if exchange == 'backpack':
            # orderType需首字母大写，side需Bid/Ask
            order_type_enum = None
            if order_type:
                if order_type.upper() == 'MARKET':
                    order_type_enum = 'Market'
                elif order_type.upper() == 'LIMIT':
                    order_type_enum = 'Limit'
                else:
                    order_type_enum = order_type
            side_enum = None
            if side:
                if side.upper() == 'BUY':
                    side_enum = 'Bid'
                elif side.upper() == 'SELL':
                    side_enum = 'Ask'
                else:
                    side_enum = side
            order_params = {
                'symbol': symbol,
                'side': side_enum,
                'orderType': order_type_enum,
            }
            if quantity:
                order_params['quantity'] = format_decimal(quantity)
            if price:
                order_params['price'] = price
            if quote_quantity:
                order_params['quoteQuantity'] = quote_quantity
            logger.info('Backpack下单参数: %s', order_params)
            result = ex.create_order(order_params)
            return jsonify({'success': True, 'result': result})
        # 其他交易所原有逻辑
        # 如果提供了USDT金额，自动调用create_order_by_usdt，自动处理精度
        if usdt_amount and not quantity:
            ticker = ex.get_ticker(symbol)
            logger.info('[下单] ticker.last_price: %s', ticker.last_price)
            # 获取最小下单量和步进
            symbol_info = ex.get_symbol_info(symbol) if hasattr(ex, 'get_symbol_info') else None
            if symbol_info:
                lot_size = [f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'][0]
                min_qty = float(lot_size['minQty'])
                step_size = float(lot_size['stepSize'])
            else:
                min_qty = 0.01
                step_size = 0.01
            # 计算下单数量
            current_price = float(ticker.get('lastPrice', '0')) if isinstance(ticker, dict) else float(ticker.last_price)
            raw_qty = float(usdt_amount) / current_price
            # 修正数量到合法精度
            if raw_qty < min_qty:
                msg = f'金额不足，按当前价格最小下单量为{min_qty}，需至少{min_qty * current_price:.2f} USDT'
                logger.info('[下单] 拒绝下单: %s', msg)
                return jsonify({'success': False, 'error': msg})
            # 向下取整到最接近stepSize
            legal_qty = math.floor(raw_qty / step_size) * step_size
            # 防止浮点误差，保留小数位
            qty_precision = str(step_size)[::-1].find('.')
            legal_qty = round(legal_qty, qty_precision)
            if legal_qty < min_qty:
                legal_qty = min_qty
            logger.info('[下单] usdt_amount: %s, current_price: %s, raw_qty: %s, 修正后quantity: %s, min_qty: %s, step_size: %s', usdt_amount, current_price, raw_qty, legal_qty, min_qty, step_size)
            try:
                order = ex.create_order({
                    'symbol': symbol,
                    'side': side,
                    'type': order_type,
                    'quantity': format_decimal(legal_qty)
                })
                logger.info('[下单] 下单结果: %s', order)
                return jsonify({'success': True, 'result': order})
            except Exception as e:
                logger.exception('[下单] create_order_by_usdt异常: %s', e)
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)})
        order_params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity
        }
        if price:
            order_params['price'] = price
            order_params['timeInForce'] = 'GTC'
        result = ex.create_order(order_params)
        logger.info('[下单] 下单结果: %s', result)
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        logger.exception('[下单] 异常: %s', e)
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/close_position', methods=['POST'])
def close_position():
    """平仓"""
    data = request.json
    exchange = data.get('exchange')
    ex = get_exchange_instance(exchange)
    try:
        symbol = data.get('symbol')
        # 获取当前持仓
        if exchange == 'backpack':
            positions = ex.get_positions()
        else:
            positions = ex.get_account().positions if hasattr(ex.get_account(), 'positions') else ex.get_positions()
        logger.info('[平仓] 当前持仓: %s', positions)
        position = None
        for pos in positions:
            pos_symbol = pos.symbol if hasattr(pos, 'symbol') else pos.get('symbol')
            pos_amt = float(pos.position_amt) if hasattr(pos, 'position_amt') else float(pos.get('netQuantity', 0) or pos.get('positionAmt', 0) or 0)
            if pos_symbol == symbol and pos_amt != 0:
                position = pos
                position_amt = abs(pos_amt)
                break
        if not position:
            return jsonify({'error': 'No position to close'}), 400
        # 定义format_decimal函数（所有交易所通用）
        def format_decimal(val):
            # 先转为Decimal，normalize去掉科学计数法
            d = Decimal(str(val)).normalize()
            s = format(d, 'f')
            return s.rstrip('0').rstrip('.') if '.' in s else s
        
        if exchange == 'backpack':
            side = 'Ask' if pos_amt > 0 else 'Bid'
            order_params = {
                'symbol': symbol,
                'side': side,
                'orderType': 'Market',
                'quantity': format_decimal(position_amt),
                'reduceOnly': True,
                'timeInForce': 'IOC',
                'selfTradePrevention': 'RejectTaker',
            }
            logger.info('Backpack平仓参数: %s', order_params)
            result = ex.create_order(order_params)
            return jsonify({'success': True, 'result': result})
        else:
            if pos_amt > 0:
                side = 'SELL'
            else:
                side = 'BUY'
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': position_amt,
                'reduceOnly': True
            }
            logger.info('[平仓] 下单参数: %s', order_params)
            result = ex.create_order(order_params)
            logger.info('[平仓] 下单结果: %s', result)
            return jsonify({
                'success': True,
                'result': result
            })
    except Exception as e:
        logger.exception('[平仓] 异常: %s', e)
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/orders')
def get_orders():
    """获取账户所有历史订单"""
    try:
        orders = aster.get_all_orders(limit=100)
        return jsonify({
            'success': True,
            'orders': [o.__dict__ for o in orders]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/symbols_with_leverage')
def get_symbols_with_leverage():
    """获取所有合约交易对及其最大杠杆"""
    exchange = request.args.get('exchange')
    ex = get_exchange_instance(exchange)
    try:
        symbols = ex.get_all_symbols()
        result = []
        for symbol in symbols:
            try:
                max_leverage = ex.get_max_leverage(symbol)
            except Exception as e:
                max_leverage = None
            result.append({
                'symbol': symbol,
                'maxLeverage': max_leverage
            })
        return jsonify({'success': True, 'symbols': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user_trades')
def get_user_trades():
    """获取账户成交历史，支持symbol参数"""
    exchange = request.args.get('exchange')
    ex = get_exchange_instance(exchange)
    try:
        symbol = request.args.get('symbol')
        limit = int(request.args.get('limit', 100))
        if not symbol:
            symbol = None
        if exchange == 'backpack':
            trades = ex.get_user_trades(symbol=symbol, limit=limit)
        else:
            if not symbol:
                return jsonify({'success': False, 'error': 'Aster暂不支持全部历史查询，请选择具体交易对'})
            trades = ex.get_user_trades(symbol=symbol, limit=limit)
        # 只返回核心字段，便于前端渲染
        result = []
        for t in trades:
            result.append({
                'price': t.get('price'),
                'qty': t.get('qty'),
                'quoteQty': t.get('quoteQty'),
                'realizedPnl': t.get('realizedPnl') or t.get('realized_pnl'),
                'side': t.get('side'),
                'positionSide': t.get('positionSide'),
                'symbol': t.get('symbol'),
                'time': t.get('time'),
                'commission': t.get('commission'),
                'commissionAsset': t.get('commissionAsset'),
                'orderId': t.get('orderId')
            })
        return jsonify({'success': True, 'trades': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/order_history')
def get_order_history():
    """获取订单历史，支持Aster和Backpack"""
    exchange = request.args.get('exchange')
    symbol = request.args.get('symbol')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    sort_direction = request.args.get('sortDirection', 'Desc')
    ex = get_exchange_instance(exchange)
    try:
        if exchange == 'backpack':
            orders = ex.get_order_history(symbol=symbol, limit=limit, offset=offset, sort_direction=sort_direction)
        else:
            orders = ex.get_all_orders(symbol=symbol, limit=limit)  # 兼容Aster
        return jsonify({'success': True, 'orders': orders})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/pnl_history')
def get_pnl_history():
    """获取盈亏历史，仅Backpack支持"""
    exchange = request.args.get('exchange')
    symbol = request.args.get('symbol')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    sort_direction = request.args.get('sortDirection', 'Desc')
    ex = get_exchange_instance(exchange)
    try:
        if exchange == 'backpack':
            pnl = ex.get_pnl_history(symbol=symbol, limit=limit, offset=offset, sort_direction=sort_direction)
            return jsonify({'success': True, 'pnl': pnl})
        else:
            return jsonify({'success': False, 'error': 'Aster暂不支持盈亏历史'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/hedge_order', methods=['POST'])
def place_hedge_order():
    """对冲下单接口"""
    data = request.json
    exchange = data.get('exchange')
    ex = get_exchange_instance(exchange)
    try:
        symbol = data.get('symbol')
        side = data.get('side')
        usdt_amount = data.get('usdt_amount')
        leverage = data.get('leverage')
        
        # 定义format_decimal函数（所有交易所通用）
        def format_decimal(val):
            # 先转为Decimal，normalize去掉科学计数法
            d = Decimal(str(val)).normalize()
            s = format(d, 'f')
            return s.rstrip('0').rstrip('.') if '.' in s else s
        
        # 设置杠杆（如果提供）
        if leverage and exchange == 'aster':
            try:
                ex.set_leverage(symbol, int(leverage))
                logger.info(f'[对冲下单] 设置杠杆 {leverage} 成功')
            except Exception as e:
                logger.exception(f'[对冲下单] 设置杠杆失败: {e}')
        
        # Backpack symbol格式强制处理
        if exchange == 'backpack':
            symbol = symbol.replace('-', '_').upper()
        
        # 获取当前价格计算数量
        ticker = ex.get_ticker(symbol)
        if not ticker:
            return jsonify({'success': False, 'error': f'获取行情失败，symbol={symbol}无效或无行情数据'})
        current_price = float(ticker.get('lastPrice', '0')) if isinstance(ticker, dict) else float(getattr(ticker, 'last_price', 0) or 0)
        if not current_price or current_price == 0:
            return jsonify({'success': False, 'error': f'获取行情失败，symbol={symbol}价格无效'})
        
        # 计算下单数量
        quantity = float(usdt_amount) / current_price
        
        # 获取最小下单量和步进
        if exchange == 'backpack':
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
        else:
            symbol_info = ex.get_symbol_info(symbol) if hasattr(ex, 'get_symbol_info') else None
            if symbol_info and 'filters' in symbol_info:
                lot_size = [f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE']
                if lot_size:
                    min_qty = float(lot_size[0]['minQty'])
                    step_size = float(lot_size[0]['stepSize'])
                else:
                    min_qty = 0.01
                    step_size = 0.01
            else:
                min_qty = 0.01
                step_size = 0.01
        
        # 修正数量到合法精度
        if exchange != 'backpack' and quantity < min_qty:
            msg = f'金额不足，按当前价格最小下单量为{min_qty}，需至少{min_qty * current_price:.2f} USDT'
            logger.info('[对冲下单] 拒绝下单: %s', msg)
            return jsonify({'success': False, 'error': msg})
        
        # 向下取整到最接近stepSize
        legal_qty = math.floor(quantity / step_size) * step_size
        # 防止浮点误差，保留小数位
        qty_precision = str(step_size)[::-1].find('.')
        legal_qty = round(legal_qty, qty_precision)
        if legal_qty < min_qty:
            legal_qty = min_qty
        
        logger.info(f'[对冲下单] {exchange} - usdt_amount: {usdt_amount}, current_price: {current_price}, quantity: {legal_qty}')
        
        # 根据交易所执行下单
        if exchange == 'backpack':
            # Backpack专用参数映射
            side_enum = 'Bid' if side.upper() == 'BUY' else 'Ask'
            order_params = {
                'symbol': symbol,
                'side': side_enum,
                'orderType': 'Market',
                'quantity': format_decimal(legal_qty),
                'timeInForce': 'IOC',
                'selfTradePrevention': 'RejectTaker',
            }
            logger.info(f'[对冲下单] Backpack参数: %s', order_params)
            result = ex.create_order(order_params)
        else:
            # Aster下单
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': format_decimal(legal_qty)
            }
            logger.info(f'[对冲下单] Aster参数: %s', order_params)
            result = ex.create_order(order_params)
        
        logger.info(f'[对冲下单] {exchange} 下单结果: %s', result)
        return jsonify({'success': True, 'result': result})
        
    except Exception as e:
        logger.exception(f'[对冲下单] {exchange} 异常: %s', e)
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

# 币安相关API接口
from exchanges.binance import Binance

# 初始化币安实例（使用空密钥，只能访问公开接口）
binance = Binance(api_key="", api_secret="")

@app.route('/binance_charts')
def binance_charts():
    """币安K线图表页面"""
    return render_template('binance_charts.html')

@app.route('/api/binance_symbols')
def get_binance_symbols():
    """获取币安U本位合约交易对列表"""
    try:
        symbols = binance.get_all_symbols()
        return jsonify({
            'success': True,
            'symbols': symbols
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/binance_ticker/<symbol>')
def get_binance_ticker(symbol):
    """获取币安交易对Ticker信息"""
    try:
        ticker = binance.get_ticker(symbol)
        # 转换为字典格式
        ticker_dict = {
            'symbol': ticker.symbol,
            'last_price': ticker.last_price,
            'open_price': ticker.open_price,
            'high_price': ticker.high_price,
            'low_price': ticker.low_price,
            'volume': ticker.volume,
            'quote_volume': ticker.quote_volume,
            'price_change': ticker.price_change,
            'price_change_percent': ticker.price_change_percent,
            'event_time': ticker.event_time
        }
        return jsonify({
            'success': True,
            'ticker': ticker_dict
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/binance_klines/<symbol>/<interval>')
def get_binance_klines(symbol, interval):
    """获取币安K线数据"""
    try:
        # 验证interval参数
        valid_intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
        if interval not in valid_intervals:
            return jsonify({
                'success': False,
                'error': f'无效的时间间隔: {interval}。支持的时间间隔: {", ".join(valid_intervals)}'
            })
        
        # 获取K线数据
        klines = binance.get_klines(symbol, interval, limit=1500)  # 1500根保证长周期EMA更准确
        
        # 转换为字典格式
        klines_dict = []
        for kline in klines:
            kline_dict = {
                'open_time': kline.open_time,
                'open': kline.open,
                'high': kline.high,
                'low': kline.low,
                'close': kline.close,
                'volume': kline.volume,
                'close_time': kline.close_time,
                'quote_asset_volume': kline.quote_asset_volume,
                'number_of_trades': kline.number_of_trades,
                'taker_buy_base_asset_volume': kline.taker_buy_base_asset_volume,
                'taker_buy_quote_asset_volume': kline.taker_buy_quote_asset_volume,
                'event_time': kline.event_time
            }
            klines_dict.append(kline_dict)
        
        return jsonify({
            'success': True,
            'klines': klines_dict
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/binance_depth/<symbol>')
def get_binance_depth(symbol):
    """获取币安深度数据"""
    try:
        depth = binance.get_depth(symbol, limit=10)
        
        # 转换为字典格式
        depth_dict = {
            'symbol': depth.symbol,
            'last_update_id': depth.last_update_id,
            'bids': [[level.price, level.quantity] for level in depth.bids],
            'asks': [[level.price, level.quantity] for level in depth.asks],
            'event_time': depth.event_time
        }
        
        return jsonify({
            'success': True,
            'depth': depth_dict
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/ema_signal')
def ema_signal():
    """自动计算EMA并输出信号，支持4小时和15分钟，按策略.md标准"""
    symbol = request.args.get('symbol', 'BTCUSDT')
    interval = request.args.get('interval', '15m')
    try:
        # 1. 获取K线数据
        klines = binance.get_klines(symbol, interval, limit=1500)  # 1500根保证长周期EMA更准确
        closes = [float(k.close) for k in klines]
        times = [k.open_time for k in klines]
        df = pd.DataFrame({'close': closes}, index=times)
        # 2. 计算EMA
        if interval == '4h':
            ema_periods = [144, 169, 576, 676]
        elif interval == '15m':
            ema_periods = [13, 34]
        else:
            return jsonify({'success': False, 'error': '仅支持4h和15m'})
        for period in ema_periods:
            df[f'ema{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        # 3. 输出信号
        signal = {}
        if interval == '4h':
            # 趋势排列判断
            last = df.iloc[-1]
            emalist = [last[f'ema{p}'] for p in ema_periods]
            # 多头排列: ema144 > ema169 > ema576 > ema676
            if emalist[0] > emalist[1] > emalist[2] > emalist[3]:
                signal['trend'] = '多头排列'
            elif emalist[3] > emalist[2] > emalist[1] > emalist[0]:
                signal['trend'] = '空头排列'
            else:
                signal['trend'] = '无明显趋势'
        elif interval == '15m':
            # 金叉/死叉判断
            ema13 = df['ema13']
            ema34 = df['ema34']
            cross = None
            if ema13.iloc[-2] < ema34.iloc[-2] and ema13.iloc[-1] > ema34.iloc[-1]:
                cross = '金叉'
            elif ema13.iloc[-2] > ema34.iloc[-2] and ema13.iloc[-1] < ema34.iloc[-1]:
                cross = '死叉'
            signal['cross'] = cross
            # 新增：联动4h趋势
            # 获取4h趋势
            klines_4h = binance.get_klines(symbol, '4h', limit=700)
            closes_4h = [float(k.close) for k in klines_4h]
            times_4h = [k.open_time for k in klines_4h]
            df_4h = pd.DataFrame({'close': closes_4h}, index=times_4h)
            for period in [144, 169, 576, 676]:
                df_4h[f'ema{period}'] = df_4h['close'].ewm(span=period, adjust=False).mean()
            last_4h = df_4h.iloc[-1]
            emalist_4h = [last_4h[f'ema{p}'] for p in [144, 169, 576, 676]]
            if emalist_4h[0] > emalist_4h[1] > emalist_4h[2] > emalist_4h[3]:
                trend_from_4h = '多头排列'
            elif emalist_4h[3] > emalist_4h[2] > emalist_4h[1] > emalist_4h[0]:
                trend_from_4h = '空头排列'
            else:
                trend_from_4h = '无明显趋势'
        # 4. 返回结果
        # 修正time为毫秒级时间戳，所有数值转为标准Python类型
        last_index = df.index[-1]
        def to_py(v):
            if isinstance(v, (np.integer,)):
                return int(v)
            elif isinstance(v, (np.floating,)):
                return float(v)
            elif hasattr(v, 'item'):
                return v.item()
            else:
                return float(v)
        if hasattr(last_index, 'value'):  # pandas.Timestamp
            ts = int(last_index.value // 10**6)
        elif isinstance(last_index, (int, float, np.integer, np.floating)):
            ts = int(last_index)
            if ts < 10**12:
                ts = ts * 1000
        else:
            ts = None
        result = {
            'success': True,
            'symbol': symbol,
            'interval': interval,
            'ema_periods': [int(p) for p in ema_periods],
            'ema': {f'ema{p}': to_py(df[f'ema{p}'].iloc[-1]) for p in ema_periods},
            'signal': signal,
            'last_close': to_py(df['close'].iloc[-1]),
            'time': ts
        }
        if interval == '15m':
            result['trend_from_4h'] = trend_from_4h
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/max_leverage')
def get_max_leverage():
    symbol = request.args.get('symbol')
    exchange = request.args.get('exchange')
    ex = get_exchange_instance(exchange)
    try:
        max_lev = ex.get_max_leverage(symbol)
        return jsonify({'success': True, 'maxLeverage': max_lev})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/unified_order', methods=['POST'])
def unified_order():
    """统一下单接口，适配所有交易所"""
    data = request.json
    symbol = data.get('symbol')
    exchange = data.get('exchange')
    amount = data.get('amount')
    direction = data.get('direction')
    order_type = data.get('order_type', 'MARKET')
    price = data.get('price')
    leverage = data.get('leverage')
    try:
        result = unified_place_order(exchange, symbol, amount, direction, order_type, price, leverage)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/unified_close_position', methods=['POST'])
def unified_close_position_api():
    """统一平仓接口，适配所有交易所"""
    data = request.json
    symbol = data.get('symbol')
    exchange = data.get('exchange')
    direction = data.get('direction')
    try:
        result = unified_close_position(exchange, symbol, direction)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/strategy_execute', methods=['POST'])
def strategy_execute():
    """自动策略交易接口"""
    data = request.json
    exchange = data.get('exchange')
    symbol = data.get('symbol')
    leverage = int(data.get('leverage', 50))
    try:
        result = global_strategy.execute_strategy(exchange, symbol, leverage=leverage, risk_pct=0.05, auto_trade=True)
        # 确保order_history和total_pnl在result中
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/strategy_status')
def get_strategy_status():
    """获取策略状态信息，包括当前持仓和订单历史"""
    try:
        global_strategy.load_stats()  # 强制刷新，确保order_history为最新
        status = {
            'active_positions': global_strategy.active_positions,
            'total_pnl': global_strategy.total_pnl,
            'order_history': global_strategy.order_history,
            'last_update': datetime.now().isoformat()
        }
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        logger.exception('获取策略状态异常: %s', e)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/strategy_reset', methods=['POST'])
def reset_strategy():
    """重置策略状态（清空持仓和订单历史）"""
    try:
        global_strategy.active_positions = {}
        global_strategy.order_history = []
        global_strategy.total_pnl = 0
        global_strategy.save_stats()  # 保存到文件
        return jsonify({'success': True, 'message': '策略状态已重置'})
    except Exception as e:
        logger.exception('重置策略状态异常: %s', e)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ema_strategy_start', methods=['POST'])
def ema_strategy_start():
    global ema_trend_proc
    if ema_trend_proc and ema_trend_proc.poll() is None:
        return jsonify({'success': True, 'message': '策略已在运行'})
    try:
        venv_python = os.path.join(sys.prefix, 'bin', 'python')
        ema_trend_proc = subprocess.Popen([venv_python, 'ema_trend_backpack_trader.py'])
        return jsonify({'success': True, 'message': '策略已启动'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ema_strategy_stop', methods=['POST'])
def ema_strategy_stop():
    global ema_trend_proc
    if ema_trend_proc and ema_trend_proc.poll() is None:
        try:
            ema_trend_proc.terminate()
            ema_trend_proc.wait(timeout=10)
            ema_trend_proc = None
            return jsonify({'success': True, 'message': '策略已停止'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    else:
        return jsonify({'success': True, 'message': '策略未在运行'})

@app.route('/api/ema_trader_log')
def ema_trader_log():
    log_file = 'backpack_trader.log'
    line_count = int(request.args.get('lines', 50))
    if not os.path.exists(log_file):
        return jsonify({'lines': []})
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()[-line_count:]
    return jsonify({'lines': lines})

def get_last_n_lines(log_file, n=50):
    if not os.path.exists(log_file):
        return []
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        return lines[-n:]

@socketio.on('connect')
def send_initial_log():
    lines = get_last_n_lines('backpack_trader.log', 50)
    emit('ema_log', {'lines': lines})

def tail_log_and_emit(log_file='backpack_trader.log'):
    last_size = os.path.getsize(log_file) if os.path.exists(log_file) else 0
    while True:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                f.seek(last_size)
                lines = f.readlines()
                if lines:
                    all_lines = get_last_n_lines(log_file, 50)
                    socketio.emit('ema_log', {'lines': all_lines})
                last_size = f.tell()
        except Exception as e:
            pass
        time.sleep(1)

threading.Thread(target=tail_log_and_emit, daemon=True).start()

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5001) 