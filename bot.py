"""
套利机器人 - 在Bitget和AsterDex之间进行套利交易
"""
import asyncio
import time
from typing import Dict, List, Optional, Callable
import ccxt.async_support as ccxt
from config import (
    ASTER_API_KEY, ASTER_API_SECRET, BITGET_API_KEY, BITGET_API_SECRET, 
    BITGET_PASSPHRASE, TRADE_SYMBOL, TRADE_AMOUNT, ARB_THRESHOLD, 
    CLOSE_DIFF, PROFIT_DIFF_LIMIT
)


class TradeStats:
    """交易统计"""
    
    def __init__(self):
        self.total_trades = 0
        self.total_amount = 0
        self.total_profit = 0


class TradeLog:
    """交易日志"""
    
    def __init__(self, time: str, log_type: str, detail: str):
        self.time = time
        self.type = log_type
        self.detail = detail


class ArbBot:
    """套利机器人"""
    
    def __init__(self):
        """初始化套利机器人"""
        # 初始化交易所
        self.aster_private = ccxt.binance({
            'apiKey': ASTER_API_KEY,
            'secret': ASTER_API_SECRET,
            'urls': {
                'api': {
                    'fapiPublic': 'https://fapi.asterdex.com/fapi/v1',
                    'fapiPublicV2': 'https://fapi.asterdex.com/fapi/v2',
                    'fapiPublicV3': 'https://fapi.asterdex.com/fapi/v2',
                    'fapiPrivate': 'https://fapi.asterdex.com/fapi/v1',
                    'fapiPrivateV2': 'https://fapi.asterdex.com/fapi/v2',
                    'fapiPrivateV3': 'https://fapi.asterdex.com/fapi/v2',
                    'fapiData': 'https://fapi.asterdex.com/futures/data',
                    'public': 'https://fapi.asterdex.com/fapi/v1',
                    'private': 'https://fapi.asterdex.com/fapi/v2',
                    'v1': 'https://fapi.asterdex.com/fapi/v1',
                    'ws': {
                        'spot': 'wss://fstream.asterdex.com/ws',
                        'margin': 'wss://fstream.asterdex.com/ws',
                        'future': 'wss://fstream.asterdex.com/ws',
                        'ws-api': 'wss://fstream.asterdex.com/ws',
                    },
                },
            },
        })
        
        self.aster = ccxt.binance({
            'id': 'aster',
            'urls': {
                'api': {
                    'fapiPublic': 'https://fapi.asterdex.com/fapi/v1',
                    'fapiPublicV2': 'https://fapi.asterdex.com/fapi/v2',
                    'fapiPublicV3': 'https://fapi.asterdex.com/fapi/v2',
                    'fapiPrivate': 'https://fapi.asterdex.com/fapi/v1',
                    'fapiPrivateV2': 'https://fapi.asterdex.com/fapi/v2',
                    'fapiPrivateV3': 'https://fapi.asterdex.com/fapi/v2',
                    'fapiData': 'https://fapi.asterdex.com/futures/data',
                    'public': 'https://fapi.asterdex.com/fapi/v1',
                    'private': 'https://fapi.asterdex.com/fapi/v2',
                    'v1': 'https://fapi.asterdex.com/fapi/v1',
                    'ws': {
                        'spot': 'wss://fstream.asterdex.com/ws',
                        'margin': 'wss://fstream.asterdex.com/ws',
                        'future': 'wss://fstream.asterdex.com/ws',
                        'ws-api': 'wss://fstream.asterdex.com/ws',
                    },
                },
            },
        })
        
        self.bitget = ccxt.bitget({
            'apiKey': BITGET_API_KEY,
            'secret': BITGET_API_SECRET,
            'password': BITGET_PASSPHRASE,
            'options': {
                'defaultType': 'swap',
            },
        })
        
        self.exchanges = {'aster': self.aster, 'bitget': self.bitget}
        
        # 状态变量
        self.aster_orderbook = None
        self.bitget_orderbook = None
        self.aster_position: str = "none"  # "long", "short", "none"
        self.bitget_position: str = "none"  # "long", "short", "none"
        
        # 统计与日志
        self.stats = TradeStats()
        self.logs: List[TradeLog] = []
        
        # 事件回调
        self.event_handlers: Dict[str, Callable] = {}
    
    def log_event(self, log_type: str, detail: str):
        """记录事件"""
        time_str = time.strftime("%Y-%m-%d %H:%M:%S")
        self.logs.append(TradeLog(time_str, log_type, detail))
        if len(self.logs) > 1000:
            self.logs.pop(0)
    
    def get_stats(self) -> TradeStats:
        """获取统计信息"""
        return self.stats
    
    def get_logs(self) -> List[TradeLog]:
        """获取日志"""
        return self.logs.copy()
    
    def reset_stats(self):
        """重置统计"""
        self.stats = TradeStats()
        self.logs.clear()
    
    async def _watch_orderbook_ws(self, exchange_id: str, symbol: str, on_update: Callable):
        """监听订单簿WebSocket"""
        exchange = self.exchanges[exchange_id]
        
        while True:
            try:
                orderbook = await exchange.watch_order_book(symbol, 10, {
                    'instType': 'USDT-FUTURES' if exchange_id == 'bitget' else None,
                })
                on_update(orderbook)
            except Exception as e:
                print(f"[{exchange_id}] ws orderbook error: {e}")
                await asyncio.sleep(2)
    
    async def _place_aster_order(self, side: str, amount: float, price: Optional[float] = None, reduce_only: bool = False):
        """在Aster下订单"""
        try:
            params = {
                'symbol': TRADE_SYMBOL,
                'side': side,
                'type': 'LIMIT' if price else 'MARKET',
                'quantity': amount,
                'price': price,
                'reduceOnly': reduce_only,
            }
            
            if price:
                params['timeInForce'] = 'FOK'
            
            order = await self.aster_private.fapiPrivatePostOrder(params)
            
            if not reduce_only and order and order.get('orderId'):
                if side == 'BUY':
                    self.aster_position = 'long'
                elif side == 'SELL':
                    self.aster_position = 'short'
            
            if reduce_only and order and order.get('orderId'):
                self.aster_position = 'none'
            
            return order
        except Exception as e:
            print(f"[aster] 下单失败: {e}")
            self.log_event('error', f'[aster] 下单失败: {e}')
            return None
    
    async def _place_bitget_order(self, side: str, amount: float, price: Optional[float] = None, reduce_only: bool = False):
        """在Bitget下订单"""
        try:
            params = {
                'productType': 'USDT-FUTURES',
                'symbol': TRADE_SYMBOL,
                'marginMode': 'crossed',
                'marginCoin': 'USDT',
                'side': side,
                'orderType': 'limit' if price else 'market',
                'size': amount,
                'force': 'fok' if price else 'gtc',
                'price': price,
                'reduceOnly': 'YES' if reduce_only else 'NO',
            }
            
            order = await self.bitget.privateMixPostV2MixOrderPlaceOrder(params)
            
            if not reduce_only and order and order.get('data', {}).get('orderId'):
                if side == 'buy':
                    self.bitget_position = 'long'
                elif side == 'sell':
                    self.bitget_position = 'short'
            
            if reduce_only and order and order.get('data', {}).get('orderId'):
                self.bitget_position = 'none'
            
            return order
        except Exception as e:
            print(f"[bitget] 下单失败: {e}")
            self.log_event('error', f'[bitget] 下单失败: {e}')
            return None
    
    async def _wait_aster_filled(self, order_id: str) -> bool:
        """等待Aster订单成交"""
        for i in range(20):
            try:
                res = await self.aster_private.fapiPrivateGetOrder({
                    'symbol': TRADE_SYMBOL,
                    'orderId': order_id
                })
                if res.get('status') == 'FILLED':
                    return True
                return False
            except:
                pass
            await asyncio.sleep(1)
        return False
    
    async def _wait_bitget_filled(self, order_id: str) -> bool:
        """等待Bitget订单成交"""
        for i in range(20):
            try:
                res = await self.bitget.privateMixGetV2MixOrderDetail({
                    'productType': 'USDT-FUTURES',
                    'symbol': TRADE_SYMBOL,
                    'orderId': order_id
                })
                if res.get('data', {}).get('state') == 'filled':
                    return True
                if res.get('data', {}).get('state') in ['canceled', 'failed']:
                    return False
            except:
                pass
            await asyncio.sleep(1)
        return False
    
    async def _close_all_positions(self):
        """平掉所有仓位"""
        print("[警告] 平掉所有仓位")
        
        if self.aster_position == 'long':
            await self._place_aster_order('SELL', TRADE_AMOUNT, reduce_only=True)
        elif self.aster_position == 'short':
            await self._place_aster_order('BUY', TRADE_AMOUNT, reduce_only=True)
        
        if self.bitget_position == 'long':
            await self._place_bitget_order('sell', TRADE_AMOUNT, reduce_only=True)
        elif self.bitget_position == 'short':
            await self._place_bitget_order('buy', TRADE_AMOUNT, reduce_only=True)
    
    async def start_arb_bot(self, handlers: Dict[str, Callable] = None):
        """启动套利机器人"""
        if handlers is None:
            handlers = {}
        
        holding = False
        last_aster_side: Optional[str] = None
        last_bitget_side: Optional[str] = None
        entry_price_aster = 0
        entry_price_bitget = 0
        
        # 启动WebSocket监听
        asyncio.create_task(self._watch_orderbook_ws('aster', TRADE_SYMBOL, lambda ob: setattr(self, 'aster_orderbook', ob)))
        asyncio.create_task(self._watch_orderbook_ws('bitget', TRADE_SYMBOL, lambda ob: setattr(self, 'bitget_orderbook', ob)))
        
        while True:
            try:
                if not holding:
                    if not self.aster_orderbook or not self.bitget_orderbook:
                        await asyncio.sleep(0.1)
                        continue
                    
                    aster_ask = self.aster_orderbook['asks'][0][0]
                    aster_bid = self.aster_orderbook['bids'][0][0]
                    bitget_ask = self.bitget_orderbook['asks'][0][0]
                    bitget_bid = self.bitget_orderbook['bids'][0][0]
                    
                    diff1 = bitget_bid - aster_ask
                    diff2 = aster_bid - bitget_ask
                    
                    handlers.get('onOrderbook')({
                        'asterOrderbook': self.aster_orderbook,
                        'bitgetOrderbook': self.bitget_orderbook,
                        'diff1': diff1,
                        'diff2': diff2
                    })
                    
                    if diff1 > ARB_THRESHOLD:
                        # Aster买入，Bitget卖出
                        aster_order = await self._place_aster_order('BUY', TRADE_AMOUNT, aster_ask, False)
                        if not aster_order or not aster_order.get('orderId'):
                            await self._close_all_positions()
                            self.log_event('error', 'Aster下单失败，已平仓')
                            continue
                        
                        aster_filled = await self._wait_aster_filled(aster_order['orderId'])
                        if not aster_filled:
                            await self._close_all_positions()
                            self.log_event('error', 'Aster未成交，已平仓')
                            continue
                        
                        bitget_order = await self._place_bitget_order('sell', TRADE_AMOUNT, bitget_bid, False)
                        if not bitget_order or not bitget_order.get('data', {}).get('orderId'):
                            await self._close_all_positions()
                            self.log_event('error', 'Bitget下单失败，已平仓')
                            continue
                        
                        bitget_filled = await self._wait_bitget_filled(bitget_order['data']['orderId'])
                        if not bitget_filled:
                            await self._close_all_positions()
                            self.log_event('error', 'Bitget未成交，已平仓')
                            continue
                        
                        last_aster_side = 'BUY'
                        last_bitget_side = 'sell'
                        holding = True
                        entry_price_aster = aster_ask
                        entry_price_bitget = bitget_bid
                        self.stats.total_trades += 1
                        self.stats.total_amount += TRADE_AMOUNT
                        
                        self.log_event('open', f'Aster买入{TRADE_AMOUNT}@{aster_ask}，Bitget卖出{TRADE_AMOUNT}@{bitget_bid}')
                        handlers.get('onTrade')({
                            'side': 'long',
                            'amount': TRADE_AMOUNT,
                            'price': aster_ask,
                            'exchange': 'aster',
                            'type': 'open'
                        })
                        handlers.get('onTrade')({
                            'side': 'short',
                            'amount': TRADE_AMOUNT,
                            'price': bitget_bid,
                            'exchange': 'bitget',
                            'type': 'open'
                        })
                        handlers.get('onLog')('[套利成功] 已持有仓位，等待平仓机会')
                        handlers.get('onStats')(self.get_stats())
                    
                    elif diff2 > ARB_THRESHOLD:
                        # Aster卖出，Bitget买入
                        aster_order = await self._place_aster_order('SELL', TRADE_AMOUNT, aster_bid, False)
                        if not aster_order or not aster_order.get('orderId'):
                            await self._close_all_positions()
                            self.log_event('error', 'Aster下单失败，已平仓')
                            continue
                        
                        aster_filled = await self._wait_aster_filled(aster_order['orderId'])
                        if not aster_filled:
                            await self._close_all_positions()
                            self.log_event('error', 'Aster未成交，已平仓')
                            continue
                        
                        bitget_order = await self._place_bitget_order('buy', TRADE_AMOUNT, bitget_ask, False)
                        if not bitget_order or not bitget_order.get('data', {}).get('orderId'):
                            await self._close_all_positions()
                            self.log_event('error', 'Bitget下单失败，已平仓')
                            continue
                        
                        bitget_filled = await self._wait_bitget_filled(bitget_order['data']['orderId'])
                        if not bitget_filled:
                            await self._close_all_positions()
                            self.log_event('error', 'Bitget未成交，已平仓')
                            continue
                        
                        last_aster_side = 'SELL'
                        last_bitget_side = 'buy'
                        holding = True
                        entry_price_aster = aster_bid
                        entry_price_bitget = bitget_ask
                        self.stats.total_trades += 1
                        self.stats.total_amount += TRADE_AMOUNT
                        
                        self.log_event('open', f'Aster卖出{TRADE_AMOUNT}@{aster_bid}，Bitget买入{TRADE_AMOUNT}@{bitget_ask}')
                        handlers.get('onTrade')({
                            'side': 'short',
                            'amount': TRADE_AMOUNT,
                            'price': aster_bid,
                            'exchange': 'aster',
                            'type': 'open'
                        })
                        handlers.get('onTrade')({
                            'side': 'long',
                            'amount': TRADE_AMOUNT,
                            'price': bitget_ask,
                            'exchange': 'bitget',
                            'type': 'open'
                        })
                        handlers.get('onLog')('[套利成功] 已持有仓位，等待平仓机会')
                        handlers.get('onStats')(self.get_stats())
                    else:
                        handlers.get('onOrderbook')({
                            'asterOrderbook': self.aster_orderbook,
                            'bitgetOrderbook': self.bitget_orderbook,
                            'diff1': diff1,
                            'diff2': diff2
                        })
                
                else:
                    if not self.aster_orderbook or not self.bitget_orderbook:
                        await asyncio.sleep(0.1)
                        continue
                    
                    handlers.get('onLog')('已持仓，等待平仓，不再开新仓')
                    
                    aster_ask = self.aster_orderbook['asks'][0][0]
                    aster_bid = self.aster_orderbook['bids'][0][0]
                    bitget_ask = self.bitget_orderbook['asks'][0][0]
                    bitget_bid = self.bitget_orderbook['bids'][0][0]
                    
                    diff1 = bitget_bid - aster_ask
                    diff2 = aster_bid - bitget_ask
                    
                    close_diff = 0
                    if last_aster_side == 'BUY' and last_bitget_side == 'sell':
                        close_diff = abs(aster_ask - bitget_bid)
                    elif last_aster_side == 'SELL' and last_bitget_side == 'buy':
                        close_diff = abs(aster_bid - bitget_ask)
                    else:
                        close_diff = abs(bitget_bid - aster_ask)
                    
                    handlers.get('onOrderbook')({
                        'asterOrderbook': self.aster_orderbook,
                        'bitgetOrderbook': self.bitget_orderbook,
                        'diff1': diff1,
                        'diff2': diff2
                    })
                    
                    # 计算两个交易所平仓时的收益
                    profit_aster = 0
                    profit_bitget = 0
                    profit_diff = 0
                    
                    if last_aster_side == 'BUY' and last_bitget_side == 'sell':
                        # Aster买入，Bitget卖出，平仓时Aster卖出，Bitget买入
                        profit_aster = (aster_ask - entry_price_aster) * TRADE_AMOUNT
                        profit_bitget = (entry_price_bitget - bitget_bid) * TRADE_AMOUNT
                    elif last_aster_side == 'SELL' and last_bitget_side == 'buy':
                        # Aster卖出，Bitget买入，平仓时Aster买入，Bitget卖出
                        profit_aster = (entry_price_aster - aster_bid) * TRADE_AMOUNT
                        profit_bitget = (bitget_ask - entry_price_bitget) * TRADE_AMOUNT
                    
                    profit_diff = abs(profit_aster - profit_bitget)
                    
                    if close_diff < CLOSE_DIFF or profit_diff > PROFIT_DIFF_LIMIT:
                        profit = 0
                        if last_aster_side == 'BUY' and last_bitget_side == 'sell':
                            profit = (bitget_bid - entry_price_bitget) * TRADE_AMOUNT - (aster_ask - entry_price_aster) * TRADE_AMOUNT
                        elif last_aster_side == 'SELL' and last_bitget_side == 'buy':
                            profit = (entry_price_bitget - bitget_bid) * TRADE_AMOUNT - (entry_price_aster - aster_ask) * TRADE_AMOUNT
                        
                        self.stats.total_profit += profit
                        
                        if self.aster_position == 'long':
                            await self._place_aster_order('SELL', TRADE_AMOUNT, reduce_only=True)
                            handlers.get('onTrade')({
                                'side': 'long',
                                'amount': TRADE_AMOUNT,
                                'exchange': 'aster',
                                'type': 'close',
                                'profit': profit
                            })
                        elif self.aster_position == 'short':
                            await self._place_aster_order('BUY', TRADE_AMOUNT, reduce_only=True)
                            handlers.get('onTrade')({
                                'side': 'short',
                                'amount': TRADE_AMOUNT,
                                'exchange': 'aster',
                                'type': 'close',
                                'profit': profit
                            })
                        
                        if self.bitget_position == 'long':
                            await self._place_bitget_order('sell', TRADE_AMOUNT, reduce_only=True)
                            handlers.get('onTrade')({
                                'side': 'long',
                                'amount': TRADE_AMOUNT,
                                'exchange': 'bitget',
                                'type': 'close',
                                'profit': profit
                            })
                        elif self.bitget_position == 'short':
                            await self._place_bitget_order('buy', TRADE_AMOUNT, reduce_only=True)
                            handlers.get('onTrade')({
                                'side': 'short',
                                'amount': TRADE_AMOUNT,
                                'exchange': 'bitget',
                                'type': 'close',
                                'profit': profit
                            })
                        
                        self.log_event('close', f'平仓，收益: {profit:.2f} USDT' + (f'（收益差额超阈值，强制平仓）' if profit_diff > PROFIT_DIFF_LIMIT else ''))
                        handlers.get('onLog')(f'[平仓] 已同时平仓，收益: {profit:.2f} USDT' + (f'（收益差额超阈值，强制平仓）' if profit_diff > PROFIT_DIFF_LIMIT else ''))
                        handlers.get('onStats')(self.get_stats())
                        holding = False
                
            except Exception as e:
                self.log_event('error', f'[主循环异常] {e}')
                handlers.get('onLog')(f'[主循环异常] {e}')
                await self._close_all_positions()
                holding = False
            
            await asyncio.sleep(0.1)


async def main():
    """主函数"""
    bot = ArbBot()
    
    # 定义事件处理器
    handlers = {
        'onOrderbook': lambda data: print(f"[订单簿] Aster: {data['asterOrderbook']['asks'][0][0] if data['asterOrderbook'] else 'N/A'}, Bitget: {data['bitgetOrderbook']['asks'][0][0] if data['bitgetOrderbook'] else 'N/A'}, 差价1: {data['diff1']:.4f}, 差价2: {data['diff2']:.4f}"),
        'onTrade': lambda data: print(f"[交易] {data['exchange']} {data['side']} {data['amount']}@{data.get('price', 'N/A')} {data['type']}"),
        'onLog': lambda msg: print(f"[日志] {msg}"),
        'onStats': lambda stats: print(f"[统计] 总交易: {stats.total_trades}, 总金额: {stats.total_amount}, 总收益: {stats.total_profit:.2f}")
    }
    
    await bot.start_arb_bot(handlers)


if __name__ == "__main__":
    asyncio.run(main()) 