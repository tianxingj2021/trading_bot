"""
Binance交易所API封装
"""
import time
import hmac
import hashlib
import json
import websocket
import threading
from typing import Dict, List, Optional, Callable, Any
from urllib.parse import urlencode
import requests
from dataclasses import dataclass
from datetime import datetime

@dataclass
class BinanceDepthLevel:
    price: str
    quantity: str

@dataclass
class BinanceDepth:
    symbol: str
    last_update_id: int
    bids: List[BinanceDepthLevel]
    asks: List[BinanceDepthLevel]
    event_time: Optional[int] = None

@dataclass
class BinanceTicker:
    symbol: str
    last_price: str
    open_price: str
    high_price: str
    low_price: str
    volume: str
    quote_volume: str
    price_change: Optional[str] = None
    price_change_percent: Optional[str] = None
    event_time: Optional[int] = None

@dataclass
class BinanceKline:
    open_time: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    close_time: int
    quote_asset_volume: str
    number_of_trades: int
    taker_buy_base_asset_volume: str
    taker_buy_quote_asset_volume: str
    event_time: Optional[int] = None

@dataclass
class BinanceOrder:
    order_id: int
    client_order_id: str
    symbol: str
    side: str
    type: str
    quantity: str
    price: str
    stop_price: Optional[str] = None
    reduce_only: bool = False
    close_position: bool = False
    status: str = "NEW"
    time_in_force: str = "GTC"
    executed_qty: str = "0"
    cum_quote: str = "0"
    avg_price: str = "0"
    time: int = 0
    update_time: int = 0
    working_type: str = "CONTRACT_PRICE"
    price_protect: bool = False
    activation_price: Optional[str] = None
    price_rate: Optional[str] = None
    realized_pnl: Optional[str] = None

@dataclass
class BinanceAccountPosition:
    symbol: str
    position_amt: str
    entry_price: str
    unrealized_profit: str
    leverage: str
    isolated: bool = False
    position_side: str = "BOTH"
    update_time: int = 0

@dataclass
class BinanceAccountAsset:
    asset: str
    wallet_balance: str
    unrealized_profit: str
    margin_balance: str
    maint_margin: str
    initial_margin: str
    position_initial_margin: str
    open_order_initial_margin: str
    cross_wallet_balance: str
    cross_un_pnl: str
    available_balance: str
    max_withdraw_amount: str
    margin_available: bool = True
    update_time: int = 0

@dataclass
class BinanceAccountSnapshot:
    fee_tier: int
    can_trade: bool
    can_deposit: bool
    can_withdraw: bool
    update_time: int
    total_initial_margin: str
    total_maint_margin: str
    total_wallet_balance: str
    total_unrealized_profit: str
    total_margin_balance: str
    total_position_initial_margin: str
    total_open_order_initial_margin: str
    total_cross_wallet_balance: str
    total_cross_un_pnl: str
    available_balance: str
    max_withdraw_amount: str
    assets: List[BinanceAccountAsset]
    positions: List[BinanceAccountPosition]

class Binance:
    """Binance交易所API封装"""
    _exchange_info_cache = None
    _exchange_info_cache_time = 0
    _exchange_info_cache_ttl = 60 * 60  # 60分钟

    def __init__(self, api_key: str, api_secret: str, default_market: str = "BTCUSDT"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.default_market = default_market
        self.base_url = "https://fapi.binance.com"
        self.ws_url = "wss://fstream.binance.com/ws"
        # WebSocket相关
        self.ws: Optional[websocket.WebSocketApp] = None
        self.listen_key: Optional[str] = None
        self.account_callbacks: List[Callable] = []
        self.order_callbacks: List[Callable] = []
        self.depth_callbacks: List[Callable] = []
        self.ticker_callbacks: List[Callable] = []
        self.kline_callbacks: List[Callable] = []
        # 数据缓存
        self.account_snapshot: Optional[BinanceAccountSnapshot] = None
        self.open_orders: Dict[int, BinanceOrder] = {}
        self.last_depth: Optional[BinanceDepth] = None
        self.last_ticker: Optional[BinanceTicker] = None
        self.last_klines: List[BinanceKline] = []
        # 线程锁
        self.lock = threading.Lock()
        # 这里暂不初始化WebSocket，后续实现
        pass

    def _generate_signature(self, params: Dict) -> str:
        """生成签名"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _signed_request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        """发送签名请求"""
        if params is None:
            params = {}
        params['timestamp'] = int(time.time() * 1000)
        params['recvWindow'] = 5000
        signature = self._generate_signature(params)
        params['signature'] = signature
        headers = {
            'X-MBX-APIKEY': self.api_key
        }
        url = f"{self.base_url}{endpoint}"
        if method == 'GET':
            response = requests.get(url, params=params, headers=headers)
        elif method == 'POST':
            response = requests.post(url, data=params, headers=headers)
        elif method == 'DELETE':
            response = requests.delete(url, params=params, headers=headers)
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")
        if response.status_code != 200:
            raise Exception(f"API请求失败: {response.status_code} - {response.text}")
        return response.json()

    def _public_request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        """发送公开请求"""
        if params is None:
            params = {}
        url = f"{self.base_url}{endpoint}"
        if method == 'GET':
            response = requests.get(url, params=params)
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")
        if response.status_code != 200:
            raise Exception(f"API请求失败: {response.status_code} - {response.text}")
        return response.json()

    def get_depth(self, symbol: str, limit: int = 5) -> BinanceDepth:
        """获取深度数据"""
        params = {'symbol': symbol, 'limit': limit}
        response = self._public_request('GET', '/fapi/v1/depth', params)
        bids = [BinanceDepthLevel(price=level[0], quantity=level[1]) 
                for level in response.get('bids', [])]
        asks = [BinanceDepthLevel(price=level[0], quantity=level[1]) 
                for level in response.get('asks', [])]
        return BinanceDepth(
            symbol=response.get('symbol', symbol),
            last_update_id=response.get('lastUpdateId', 0),
            bids=bids,
            asks=asks
        )

    def get_ticker(self, symbol: str) -> BinanceTicker:
        """获取Ticker数据"""
        params = {'symbol': symbol}
        response = self._public_request('GET', '/fapi/v1/ticker/24hr', params)
        return BinanceTicker(
            symbol=response.get('symbol', symbol),
            last_price=response.get('lastPrice', '0'),
            open_price=response.get('openPrice', '0'),
            high_price=response.get('highPrice', '0'),
            low_price=response.get('lowPrice', '0'),
            volume=response.get('volume', '0'),
            quote_volume=response.get('quoteVolume', '0'),
            price_change=response.get('priceChange', '0'),
            price_change_percent=response.get('priceChangePercent', '0')
        )

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[BinanceKline]:
        """获取K线数据"""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        response = self._public_request('GET', '/fapi/v1/klines', params)
        klines = []
        for k in response:
            klines.append(BinanceKline(
                open_time=int(k[0]),
                open=k[1],
                high=k[2],
                low=k[3],
                close=k[4],
                volume=k[5],
                close_time=int(k[6]),
                quote_asset_volume=k[7],
                number_of_trades=int(k[8]),
                taker_buy_base_asset_volume=k[9],
                taker_buy_quote_asset_volume=k[10]
            ))
        return klines

    def get_klines_with_time(self, symbol, interval, limit=500, startTime=None, endTime=None):
        """
        获取K线数据，支持startTime和endTime参数
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if startTime is not None:
            params['startTime'] = int(startTime)
        if endTime is not None:
            params['endTime'] = int(endTime)
        response = self._public_request('GET', '/fapi/v1/klines', params=params)
        klines = []
        for k in response:
            klines.append(BinanceKline(
                open_time=k[0],
                open=k[1],
                high=k[2],
                low=k[3],
                close=k[4],
                volume=k[5],
                close_time=k[6],
                quote_asset_volume=k[7],
                number_of_trades=k[8],
                taker_buy_base_asset_volume=k[9],
                taker_buy_quote_asset_volume=k[10],
                # ignore=k[11]
            ))
        return klines

    def get_account(self) -> BinanceAccountSnapshot:
        """获取账户信息"""
        response = self._signed_request('GET', '/fapi/v2/account')
        assets = []
        for asset_data in response.get('assets', []):
            assets.append(BinanceAccountAsset(
                asset=asset_data.get('asset', ''),
                wallet_balance=asset_data.get('walletBalance', '0'),
                unrealized_profit=asset_data.get('unrealizedProfit', '0'),
                margin_balance=asset_data.get('marginBalance', '0'),
                maint_margin=asset_data.get('maintMargin', '0'),
                initial_margin=asset_data.get('initialMargin', '0'),
                position_initial_margin=asset_data.get('positionInitialMargin', '0'),
                open_order_initial_margin=asset_data.get('openOrderInitialMargin', '0'),
                cross_wallet_balance=asset_data.get('crossWalletBalance', '0'),
                cross_un_pnl=asset_data.get('crossUnPnl', '0'),
                available_balance=asset_data.get('availableBalance', '0'),
                max_withdraw_amount=asset_data.get('maxWithdrawAmount', '0'),
                margin_available=asset_data.get('marginAvailable', True),
                update_time=int(asset_data.get('updateTime', 0))
            ))
        positions = []
        for pos_data in response.get('positions', []):
            positions.append(BinanceAccountPosition(
                symbol=pos_data.get('symbol', ''),
                position_amt=pos_data.get('positionAmt', '0'),
                entry_price=pos_data.get('entryPrice', '0'),
                unrealized_profit=pos_data.get('unrealizedProfit', '0'),
                leverage=pos_data.get('leverage', '1'),
                isolated=pos_data.get('isolated', False),
                position_side=pos_data.get('positionSide', 'BOTH'),
                update_time=int(pos_data.get('updateTime', 0))
            ))
        self.account_snapshot = BinanceAccountSnapshot(
            fee_tier=response.get('feeTier', 0),
            can_trade=response.get('canTrade', False),
            can_deposit=response.get('canDeposit', False),
            can_withdraw=response.get('canWithdraw', False),
            update_time=int(response.get('updateTime', 0)),
            total_initial_margin=response.get('totalInitialMargin', '0'),
            total_maint_margin=response.get('totalMaintMargin', '0'),
            total_wallet_balance=response.get('totalWalletBalance', '0'),
            total_unrealized_profit=response.get('totalUnrealizedProfit', '0'),
            total_margin_balance=response.get('totalMarginBalance', '0'),
            total_position_initial_margin=response.get('totalPositionInitialMargin', '0'),
            total_open_order_initial_margin=response.get('totalOpenOrderInitialMargin', '0'),
            total_cross_wallet_balance=response.get('totalCrossWalletBalance', '0'),
            total_cross_un_pnl=response.get('totalCrossUnPnl', '0'),
            available_balance=response.get('availableBalance', '0'),
            max_withdraw_amount=response.get('maxWithdrawAmount', '0'),
            assets=assets,
            positions=positions
        )
        return self.account_snapshot

    def get_open_orders(self, symbol: str = None) -> List[BinanceOrder]:
        """获取未成交订单"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        response = self._signed_request('GET', '/fapi/v1/openOrders', params)
        orders = []
        for order_data in response:
            order = BinanceOrder(
                order_id=int(order_data.get('orderId', 0)),
                client_order_id=order_data.get('clientOrderId', ''),
                symbol=order_data.get('symbol', ''),
                side=order_data.get('side', ''),
                type=order_data.get('type', ''),
                quantity=order_data.get('origQty', '0'),
                price=order_data.get('price', '0'),
                stop_price=order_data.get('stopPrice'),
                reduce_only=order_data.get('reduceOnly', False),
                close_position=order_data.get('closePosition', False),
                status=order_data.get('status', 'NEW'),
                time_in_force=order_data.get('timeInForce', 'GTC'),
                executed_qty=order_data.get('executedQty', '0'),
                cum_quote=order_data.get('cumQuote', '0'),
                avg_price=order_data.get('avgPrice', '0'),
                time=int(order_data.get('time', 0)),
                update_time=int(order_data.get('updateTime', 0)),
                working_type=order_data.get('workingType', 'CONTRACT_PRICE'),
                price_protect=order_data.get('priceProtect', False),
                activation_price=order_data.get('activationPrice'),
                price_rate=order_data.get('priceRate'),
                realized_pnl=order_data.get('realizedPnl') or order_data.get('realized_pnl') or None
            )
            orders.append(order)
            with self.lock:
                self.open_orders[order.order_id] = order
        return orders

    def create_order(self, params: Dict) -> BinanceOrder:
        """创建订单"""
        response = self._signed_request('POST', '/fapi/v1/order', params)
        order = BinanceOrder(
            order_id=int(response.get('orderId', 0)),
            client_order_id=response.get('clientOrderId', ''),
            symbol=response.get('symbol', ''),
            side=response.get('side', ''),
            type=response.get('type', ''),
            quantity=response.get('origQty', '0'),
            price=response.get('price', '0'),
            stop_price=response.get('stopPrice'),
            reduce_only=response.get('reduceOnly', False),
            close_position=response.get('closePosition', False),
            status=response.get('status', 'NEW'),
            time_in_force=response.get('timeInForce', 'GTC'),
            executed_qty=response.get('executedQty', '0'),
            cum_quote=response.get('cumQuote', '0'),
            avg_price=response.get('avgPrice', '0'),
            time=int(response.get('time', 0)),
            update_time=int(response.get('updateTime', 0)),
            working_type=response.get('workingType', 'CONTRACT_PRICE'),
            price_protect=response.get('priceProtect', False),
            activation_price=response.get('activationPrice'),
            price_rate=response.get('priceRate'),
            realized_pnl=response.get('realizedPnl') or response.get('realized_pnl') or None
        )
        with self.lock:
            self.open_orders[order.order_id] = order
        return order

    def cancel_order(self, symbol: str, order_id: int = None, client_order_id: str = None) -> BinanceOrder:
        """撤销订单"""
        params = {'symbol': symbol}
        if order_id:
            params['orderId'] = order_id
        if client_order_id:
            params['origClientOrderId'] = client_order_id
        response = self._signed_request('DELETE', '/fapi/v1/order', params)
        order = BinanceOrder(
            order_id=int(response.get('orderId', 0)),
            client_order_id=response.get('clientOrderId', ''),
            symbol=response.get('symbol', ''),
            side=response.get('side', ''),
            type=response.get('type', ''),
            quantity=response.get('origQty', '0'),
            price=response.get('price', '0'),
            stop_price=response.get('stopPrice'),
            reduce_only=response.get('reduceOnly', False),
            close_position=response.get('closePosition', False),
            status=response.get('status', 'CANCELED'),
            time_in_force=response.get('timeInForce', 'GTC'),
            executed_qty=response.get('executedQty', '0'),
            cum_quote=response.get('cumQuote', '0'),
            avg_price=response.get('avgPrice', '0'),
            time=int(response.get('time', 0)),
            update_time=int(response.get('updateTime', 0)),
            working_type=response.get('workingType', 'CONTRACT_PRICE'),
            price_protect=response.get('priceProtect', False),
            activation_price=response.get('activationPrice'),
            price_rate=response.get('priceRate'),
            realized_pnl=response.get('realizedPnl') or response.get('realized_pnl') or None
        )
        with self.lock:
            self.open_orders.pop(order.order_id, None)
        return order

    def _init_websocket(self):
        """初始化WebSocket连接"""
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close
        )
        ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        ws_thread.start()

    def _on_ws_open(self, ws):
        print("[Binance] WebSocket连接已建立")

    def _on_ws_message(self, ws, message):
        try:
            data = json.loads(message)
            self._handle_ws_message(data)
        except Exception as e:
            print(f"[Binance] WebSocket消息处理错误: {e}")

    def _on_ws_error(self, ws, error):
        print(f"[Binance] WebSocket错误: {error}")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        print(f"[Binance] WebSocket连接关闭: {close_status_code} - {close_msg}")
        time.sleep(5)
        self._init_websocket()

    def _handle_ws_message(self, data: Dict):
        if "e" in data:
            event_type = data["e"]
            if event_type == "depthUpdate":
                self._handle_depth_update(data)
            elif event_type == "24hrTicker":
                self._handle_ticker_update(data)
            elif event_type == "kline":
                self._handle_kline_update(data)
            elif event_type == "ACCOUNT_UPDATE":
                self._handle_account_update(data)
            elif event_type == "ORDER_TRADE_UPDATE":
                self._handle_order_update(data)

    def _handle_depth_update(self, data: Dict):
        bids = [BinanceDepthLevel(price=level[0], quantity=level[1]) for level in data.get("b", [])]
        asks = [BinanceDepthLevel(price=level[0], quantity=level[1]) for level in data.get("a", [])]
        depth = BinanceDepth(
            symbol=data.get("s", ""),
            last_update_id=int(data.get("u", 0)),
            bids=bids,
            asks=asks,
            event_time=int(data.get("E", 0))
        )
        self.last_depth = depth
        for callback in self.depth_callbacks:
            try:
                callback(depth)
            except Exception as e:
                print(f"[Binance] 深度回调错误: {e}")

    def _handle_ticker_update(self, data: Dict):
        ticker = BinanceTicker(
            symbol=data.get("s", ""),
            last_price=data.get("c", "0"),
            open_price=data.get("o", "0"),
            high_price=data.get("h", "0"),
            low_price=data.get("l", "0"),
            volume=data.get("v", "0"),
            quote_volume=data.get("q", "0"),
            price_change=data.get("p", "0"),
            price_change_percent=data.get("P", "0"),
            event_time=int(data.get("E", 0))
        )
        self.last_ticker = ticker
        for callback in self.ticker_callbacks:
            try:
                callback(ticker)
            except Exception as e:
                print(f"[Binance] Ticker回调错误: {e}")

    def _handle_kline_update(self, data: Dict):
        k = data.get("k", {})
        kline = BinanceKline(
            open_time=int(k.get("t", 0)),
            open=k.get("o", "0"),
            high=k.get("h", "0"),
            low=k.get("l", "0"),
            close=k.get("c", "0"),
            volume=k.get("v", "0"),
            close_time=int(k.get("T", 0)),
            quote_asset_volume=k.get("q", "0"),
            number_of_trades=int(k.get("n", 0)),
            taker_buy_base_asset_volume=k.get("V", "0"),
            taker_buy_quote_asset_volume=k.get("Q", "0"),
            event_time=int(data.get("E", 0))
        )
        with self.lock:
            if kline.open_time in [k.open_time for k in self.last_klines]:
                for i, existing_kline in enumerate(self.last_klines):
                    if existing_kline.open_time == kline.open_time:
                        self.last_klines[i] = kline
                        break
            else:
                self.last_klines.append(kline)
                if len(self.last_klines) > 1000:
                    self.last_klines = self.last_klines[-1000:]
        for callback in self.kline_callbacks:
            try:
                callback(self.last_klines)
            except Exception as e:
                print(f"[Binance] K线回调错误: {e}")

    def _subscribe_channel(self, channel: str):
        if not self.ws or not self.ws.sock or not self.ws.sock.connected:
            print(f"[Binance] WebSocket未连接，无法订阅频道: {channel}")
            return
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [channel],
            "id": int(time.time() * 1000)
        }
        try:
            self.ws.send(json.dumps(subscribe_msg))
            print(f"[Binance] 订阅频道成功: {channel}")
        except Exception as e:
            print(f"[Binance] 订阅频道失败: {channel}, 错误: {e}")

    def watch_depth(self, symbol: str, callback: Callable[[BinanceDepth], None]):
        self.depth_callbacks.append(callback)
        channel = f"{symbol.lower()}@depth5@100ms"
        def delayed_subscribe():
            time.sleep(2)
            self._subscribe_channel(channel)
        if not self.ws:
            self._init_websocket()
        thread = threading.Thread(target=delayed_subscribe, daemon=True)
        thread.start()

    def watch_ticker(self, symbol: str, callback: Callable[[BinanceTicker], None]):
        self.ticker_callbacks.append(callback)
        channel = f"{symbol.lower()}@ticker"
        def delayed_subscribe():
            time.sleep(2)
            self._subscribe_channel(channel)
        if not self.ws:
            self._init_websocket()
        thread = threading.Thread(target=delayed_subscribe, daemon=True)
        thread.start()

    def watch_kline(self, symbol: str, interval: str, callback: Callable[[List[BinanceKline]], None]):
        self.kline_callbacks.append(callback)
        channel = f"{symbol.lower()}@continuousKline_{interval}_perpetual"
        def delayed_subscribe():
            time.sleep(2)
            self._subscribe_channel(channel)
        if not self.ws:
            self._init_websocket()
        thread = threading.Thread(target=delayed_subscribe, daemon=True)
        thread.start()
        self.last_klines = self.get_klines(symbol, interval, 100)

    def _subscribe_user_data(self):
        try:
            # 获取listenKey
            response = self._signed_request('POST', '/fapi/v1/listenKey')
            self.listen_key = response.get('listenKey')
            if self.listen_key:
                subscribe_msg = {
                    "method": "SUBSCRIBE",
                    "params": [f"{self.listen_key}"],
                    "id": int(time.time() * 1000)
                }
                self.ws.send(json.dumps(subscribe_msg))
                self._start_listen_key_keepalive()
        except Exception as e:
            print(f"[Binance] 订阅用户数据失败: {e}")

    def _start_listen_key_keepalive(self):
        def keepalive():
            while self.listen_key:
                try:
                    time.sleep(30 * 60)
                    self._signed_request('PUT', '/fapi/v1/listenKey', {'listenKey': self.listen_key})
                except Exception as e:
                    print(f"[Binance] Listen key保活失败: {e}")
                    break
        thread = threading.Thread(target=keepalive, daemon=True)
        thread.start()

    def watch_account(self, callback: Callable[[BinanceAccountSnapshot], None]):
        self.account_callbacks.append(callback)
        if not self.ws:
            self._init_websocket()
        def delayed_subscribe():
            time.sleep(2)
            self._subscribe_user_data()
        thread = threading.Thread(target=delayed_subscribe, daemon=True)
        thread.start()

    def watch_order(self, callback: Callable[[List[BinanceOrder]], None]):
        self.order_callbacks.append(callback)
        if not self.ws:
            self._init_websocket()
        def delayed_subscribe():
            time.sleep(2)
            self._subscribe_user_data()
        thread = threading.Thread(target=delayed_subscribe, daemon=True)
        thread.start()

    def _handle_account_update(self, data: Dict):
        # 这里只做简单回调，详细字段可按需补充
        for callback in self.account_callbacks:
            try:
                callback(data)
            except Exception as e:
                print(f"[Binance] 账户推送回调错误: {e}")

    def _handle_order_update(self, data: Dict):
        # 这里只做简单回调，详细字段可按需补充
        for callback in self.order_callbacks:
            try:
                callback([data])
            except Exception as e:
                print(f"[Binance] 订单推送回调错误: {e}")

    def cancel_all_orders(self, symbol: str) -> List[Dict]:
        """撤销所有订单"""
        params = {'symbol': symbol}
        response = self._signed_request('DELETE', '/fapi/v1/allOpenOrders', params)
        with self.lock:
            self.open_orders.clear()
        return response

    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """设置杠杆倍数"""
        params = {
            'symbol': symbol,
            'leverage': leverage
        }
        return self._signed_request('POST', '/fapi/v1/leverage', params)

    def set_margin_type(self, symbol: str, margin_type: str) -> Dict:
        """设置保证金模式"""
        params = {
            'symbol': symbol,
            'marginType': margin_type  # ISOLATED(逐仓) 或 CROSSED(全仓)
        }
        return self._signed_request('POST', '/fapi/v1/marginType', params)

    def get_exchange_info_cached(self):
        now = time.time()
        if (self._exchange_info_cache is not None and 
            now - self._exchange_info_cache_time < self._exchange_info_cache_ttl):
            return self._exchange_info_cache
        info = self._public_request('GET', '/fapi/v1/exchangeInfo')
        self._exchange_info_cache = info
        self._exchange_info_cache_time = now
        return info

    def get_symbol_info(self, symbol: str) -> dict:
        info = self.get_exchange_info_cached()
        for s in info.get('symbols', []):
            if s['symbol'] == symbol:
                return s
        raise ValueError(f"未找到交易对信息: {symbol}")

    def get_all_symbols(self) -> list:
        info = self.get_exchange_info_cached()
        symbols = []
        for s in info.get('symbols', []):
            if s.get('status') == 'TRADING':
                symbols.append(s['symbol'])
        return symbols

    def get_max_leverage(self, symbol: str) -> int:
        """获取指定交易对的最大杠杆倍数"""
        params = {'symbol': symbol}
        result = self._signed_request('GET', '/fapi/v1/leverageBracket', params)
        if isinstance(result, list):
            brackets = result[0]['brackets'] if result and 'brackets' in result[0] else []
        elif isinstance(result, dict):
            brackets = result.get('brackets', [])
        else:
            brackets = []
        max_leverage = 1
        for b in brackets:
            if 'initialLeverage' in b:
                max_leverage = max(max_leverage, int(b['initialLeverage']))
        return max_leverage

    def get_all_orders(self, limit=100):
        """获取账户所有历史订单（不指定symbol）"""
        params = {'limit': limit}
        response = self._signed_request('GET', '/fapi/v1/allOrders', params)
        orders = []
        for order_data in response:
            order = BinanceOrder(
                order_id=int(order_data.get('orderId', 0)),
                client_order_id=order_data.get('clientOrderId', ''),
                symbol=order_data.get('symbol', ''),
                side=order_data.get('side', ''),
                type=order_data.get('type', ''),
                quantity=order_data.get('origQty', '0'),
                price=order_data.get('price', '0'),
                stop_price=order_data.get('stopPrice'),
                reduce_only=order_data.get('reduceOnly', False),
                close_position=order_data.get('closePosition', False),
                status=order_data.get('status', 'NEW'),
                time_in_force=order_data.get('timeInForce', 'GTC'),
                executed_qty=order_data.get('executedQty', '0'),
                cum_quote=order_data.get('cumQuote', '0'),
                avg_price=order_data.get('avgPrice', '0'),
                time=int(order_data.get('time', 0)),
                update_time=int(order_data.get('updateTime', 0)),
                working_type=order_data.get('workingType', 'CONTRACT_PRICE'),
                price_protect=order_data.get('priceProtect', False),
                activation_price=order_data.get('activationPrice'),
                price_rate=order_data.get('priceRate'),
                realized_pnl=order_data.get('realizedPnl') or order_data.get('realized_pnl') or None
            )
            orders.append(order)
        return orders

    def get_user_trades(self, symbol: str, limit: int = 100) -> list:
        """获取账户成交历史"""
        params = {'symbol': symbol, 'limit': limit}
        response = self._signed_request('GET', '/fapi/v1/userTrades', params)
        return response

    def create_order_by_usdt(self, symbol: str, side: str, usdt_amount: float, order_type: str = "MARKET", price: float = None) -> BinanceOrder:
        """按USDT金额下单"""
        ticker = self.get_ticker(symbol)
        if not ticker or float(ticker.last_price) <= 0:
            raise ValueError("无法获取当前价格")
        
        current_price = float(ticker.last_price)
        
        if order_type == "MARKET":
            quantity = usdt_amount / current_price
            if symbol == "BTCUSDT":
                quantity = round(quantity, 2)
            elif symbol == "ETHUSDT":
                quantity = round(quantity, 3)
            else:
                quantity = round(quantity, 4)
            
            params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': str(quantity),
            }
        elif order_type == "LIMIT":
            if price is None:
                raise ValueError("限价单必须指定价格")
            quantity = usdt_amount / float(price)
            if symbol == "BTCUSDT":
                quantity = round(quantity, 2)
            elif symbol == "ETHUSDT":
                quantity = round(quantity, 3)
            else:
                quantity = round(quantity, 4)
            
            if symbol == "BTCUSDT":
                price = round(price, 1)
            elif symbol == "ETHUSDT":
                price = round(price, 2)
            else:
                price = round(price, 4)
            
            params = {
                'symbol': symbol,
                'side': side,
                'type': 'LIMIT',
                'quantity': str(quantity),
                'price': str(price),
                'timeInForce': 'GTC',
            }
        else:
            raise ValueError(f"不支持的订单类型: {order_type}")
        
        return self.create_order(params)

    def create_order_auto(self, symbol, side, usdt_amount, order_type="MARKET", price=None):
        """自动化下单，按USDT金额自动换算数量和精度，支持市价单和限价单"""
        info = self.get_symbol_info(symbol)
        lot_size = [f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'][0]
        min_qty = float(lot_size['minQty'])
        qty_step = float(lot_size['stepSize'])
        price_filter = [f for f in info['filters'] if f['filterType'] == 'PRICE_FILTER'][0]
        price_tick = float(price_filter['tickSize'])

        if order_type == "MARKET":
            ticker = self.get_ticker(symbol)
            price = float(ticker.last_price)
        elif price is None:
            raise ValueError("限价单必须指定价格")

        quantity = usdt_amount / price
        quantity = max(quantity, min_qty)
        quantity = (int(quantity / qty_step)) * qty_step
        quantity = round(quantity, 8)

        if quantity < min_qty:
            raise ValueError(f"下单数量{quantity}低于最小下单量{min_qty}")

        if order_type == "LIMIT":
            price = (int(price / price_tick)) * price_tick
            price = round(price, 8)

        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': str(quantity),
        }
        if order_type == "LIMIT":
            params['price'] = str(price)
            params['timeInForce'] = 'GTC'

        return self.create_order(params)
