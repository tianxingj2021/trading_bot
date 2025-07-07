"""
AsterDex交易所API封装
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
class AsterDepthLevel:
    price: str
    quantity: str


@dataclass
class AsterDepth:
    symbol: str
    last_update_id: int
    bids: List[AsterDepthLevel]
    asks: List[AsterDepthLevel]
    event_time: Optional[int] = None


@dataclass
class AsterTicker:
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
class AsterKline:
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
class AsterOrder:
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
class AsterAccountPosition:
    symbol: str
    position_amt: str
    entry_price: str
    unrealized_profit: str
    leverage: str
    isolated: bool = False
    position_side: str = "BOTH"
    update_time: int = 0


@dataclass
class AsterAccountAsset:
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
class AsterAccountSnapshot:
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
    assets: List[AsterAccountAsset]
    positions: List[AsterAccountPosition]


class Aster:
    """AsterDex交易所API封装"""
    
    def __init__(self, api_key: str, api_secret: str, default_market: str = "BTCUSDT"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.default_market = default_market
        self.base_url = "https://fapi.asterdex.com"
        self.ws_url = "wss://fstream.asterdex.com/ws"
        
        # WebSocket相关
        self.ws: Optional[websocket.WebSocketApp] = None
        self.listen_key: Optional[str] = None
        self.account_callbacks: List[Callable] = []
        self.order_callbacks: List[Callable] = []
        self.depth_callbacks: List[Callable] = []
        self.ticker_callbacks: List[Callable] = []
        self.kline_callbacks: List[Callable] = []
        
        # 数据缓存
        self.account_snapshot: Optional[AsterAccountSnapshot] = None
        self.open_orders: Dict[int, AsterOrder] = {}
        self.last_depth: Optional[AsterDepth] = None
        self.last_ticker: Optional[AsterTicker] = None
        self.last_klines: List[AsterKline] = []
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 启动WebSocket连接
        self._init_websocket()
    
    def _init_websocket(self):
        """初始化WebSocket连接"""
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close
        )
        
        # 在后台线程中运行WebSocket
        ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        ws_thread.start()
    
    def _on_ws_open(self, ws):
        """WebSocket连接打开回调"""
        print("[Aster] WebSocket连接已建立")
        self._subscribe_user_data()
    
    def _on_ws_message(self, ws, message):
        """WebSocket消息处理"""
        try:
            data = json.loads(message)
            self._handle_ws_message(data)
        except Exception as e:
            print(f"[Aster] WebSocket消息处理错误: {e}")
    
    def _on_ws_error(self, ws, error):
        """WebSocket错误处理"""
        print(f"[Aster] WebSocket错误: {error}")
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket连接关闭处理"""
        print(f"[Aster] WebSocket连接关闭: {close_status_code} - {close_msg}")
        # 尝试重连
        time.sleep(5)
        self._init_websocket()
    
    def _handle_ws_message(self, data: Dict):
        """处理WebSocket消息"""
        if "e" in data:  # 事件类型
            event_type = data["e"]
            
            if event_type == "outboundAccountPosition":
                self._handle_account_update(data)
            elif event_type == "executionReport":
                self._handle_order_update(data)
            elif event_type == "depthUpdate":
                self._handle_depth_update(data)
            elif event_type == "24hrTicker":
                self._handle_ticker_update(data)
            elif event_type == "kline":
                self._handle_kline_update(data)
    
    def _handle_account_update(self, data: Dict):
        """处理账户更新"""
        with self.lock:
            # 更新账户快照
            if self.account_snapshot:
                # 这里简化处理，实际应该根据推送数据更新具体字段
                pass
            
            # 调用回调函数
            for callback in self.account_callbacks:
                try:
                    callback(self.account_snapshot)
                except Exception as e:
                    print(f"[Aster] 账户更新回调错误: {e}")
    
    def _handle_order_update(self, data: Dict):
        """处理订单更新"""
        order = self._format_order_update(data)
        
        with self.lock:
            if order.order_id in self.open_orders:
                self.open_orders[order.order_id] = order
            elif order.status not in ["FILLED", "CANCELED", "REJECTED", "EXPIRED"]:
                self.open_orders[order.order_id] = order
            else:
                self.open_orders.pop(order.order_id, None)
            
            # 调用回调函数
            for callback in self.order_callbacks:
                try:
                    callback(list(self.open_orders.values()))
                except Exception as e:
                    print(f"[Aster] 订单更新回调错误: {e}")
    
    def _handle_depth_update(self, data: Dict):
        """处理深度更新"""
        depth = self._format_depth_data(data)
        self.last_depth = depth
        
        for callback in self.depth_callbacks:
            try:
                callback(depth)
            except Exception as e:
                print(f"[Aster] 深度更新回调错误: {e}")
    
    def _handle_ticker_update(self, data: Dict):
        """处理Ticker更新"""
        ticker = self._format_ticker_data(data)
        self.last_ticker = ticker
        
        for callback in self.ticker_callbacks:
            try:
                callback(ticker)
            except Exception as e:
                print(f"[Aster] Ticker更新回调错误: {e}")
    
    def _handle_kline_update(self, data: Dict):
        """处理K线更新"""
        kline = self._format_kline_data(data)
        
        with self.lock:
            # 更新K线数据
            if kline.open_time in [k.open_time for k in self.last_klines]:
                # 更新现有K线
                for i, existing_kline in enumerate(self.last_klines):
                    if existing_kline.open_time == kline.open_time:
                        self.last_klines[i] = kline
                        break
            else:
                # 添加新K线
                self.last_klines.append(kline)
                # 保持最多1000根K线
                if len(self.last_klines) > 1000:
                    self.last_klines = self.last_klines[-1000:]
        
        for callback in self.kline_callbacks:
            try:
                callback(self.last_klines)
            except Exception as e:
                print(f"[Aster] K线更新回调错误: {e}")
    
    def _format_order_update(self, data: Dict) -> AsterOrder:
        """格式化订单更新数据"""
        return AsterOrder(
            order_id=int(data.get("i", 0)),
            client_order_id=data.get("c", ""),
            symbol=data.get("s", ""),
            side=data.get("S", ""),
            type=data.get("o", ""),
            quantity=data.get("q", "0"),
            price=data.get("p", "0"),
            stop_price=data.get("sp"),
            reduce_only=data.get("R", False),
            close_position=data.get("cp", False),
            status=data.get("X", "NEW"),
            time_in_force=data.get("f", "GTC"),
            executed_qty=data.get("z", "0"),
            cum_quote=data.get("Z", "0"),
            avg_price=data.get("ap", "0"),
            time=int(data.get("T", 0)),
            update_time=int(data.get("E", 0)),
            working_type=data.get("wt", "CONTRACT_PRICE"),
            price_protect=data.get("pP", False),
            activation_price=data.get("AP"),
            price_rate=data.get("cr"),
            realized_pnl=data.get('realizedPnl') or data.get('realized_pnl') or None
        )
    
    def _format_depth_data(self, data: Dict) -> AsterDepth:
        """格式化深度数据"""
        bids = [AsterDepthLevel(price=level[0], quantity=level[1]) 
                for level in data.get("b", [])]
        asks = [AsterDepthLevel(price=level[0], quantity=level[1]) 
                for level in data.get("a", [])]
        
        return AsterDepth(
            symbol=data.get("s", ""),
            last_update_id=int(data.get("u", 0)),
            bids=bids,
            asks=asks,
            event_time=int(data.get("E", 0))
        )
    
    def _format_ticker_data(self, data: Dict) -> AsterTicker:
        """格式化Ticker数据"""
        return AsterTicker(
            symbol=data.get("s", ""),
            last_price=data.get("c", "0"),
            open_price=data.get("o", "0"),
            high_price=data.get("h", "0"),
            low_price=data.get("l", "0"),
            volume=data.get("v", "0"),
            quote_volume=data.get("q", "0"),
            price_change=data.get("P", "0"),
            price_change_percent=data.get("P", "0"),
            event_time=int(data.get("E", 0))
        )
    
    def _format_kline_data(self, data: Dict) -> AsterKline:
        """格式化K线数据"""
        k = data.get("k", {})
        return AsterKline(
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
        
        # 获取服务器时间并同步本地时间戳
        try:
            server_time_resp = requests.get(f"{self.base_url}/fapi/v1/time", proxies={}, timeout=2)
            if server_time_resp.status_code == 200:
                server_time = int(server_time_resp.json()['serverTime'])
                params['timestamp'] = server_time
                print(f"[调试] Aster本地时间戳: {int(time.time() * 1000)}, 服务器时间戳: {server_time}, 差值: {int(time.time() * 1000) - server_time} ms")
            else:
                params['timestamp'] = int(time.time() * 1000)
                print(f"[调试] 获取Aster服务器时间失败，使用本地时间戳: {params['timestamp']}")
        except Exception as e:
            params['timestamp'] = int(time.time() * 1000)
            print(f"[调试] 获取Aster服务器时间异常: {e}")
        params['recvWindow'] = 5000
        
        signature = self._generate_signature(params)
        params['signature'] = signature
        
        headers = {
            'X-MBX-APIKEY': self.api_key
        }
        
        url = f"{self.base_url}{endpoint}"
        
        if method == 'GET':
            response = requests.get(url, params=params, headers=headers, proxies={})
        elif method == 'POST':
            response = requests.post(url, data=params, headers=headers, proxies={})
        elif method == 'DELETE':
            response = requests.delete(url, params=params, headers=headers, proxies={})
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
            response = requests.get(url, params=params, proxies={})
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")
        
        if response.status_code != 200:
            raise Exception(f"API请求失败: {response.status_code} - {response.text}")
        
        return response.json()
    
    def _subscribe_user_data(self):
        """订阅用户数据流"""
        try:
            # 获取listen key
            response = self._signed_request('POST', '/fapi/v1/listenKey')
            self.listen_key = response.get('listenKey')
            
            if self.listen_key:
                # 订阅用户数据流
                subscribe_msg = {
                    "method": "SUBSCRIBE",
                    "params": [f"{self.listen_key}"],
                    "id": int(time.time() * 1000)
                }
                self.ws.send(json.dumps(subscribe_msg))
                
                # 启动keep-alive
                self._start_listen_key_keepalive()
        except Exception as e:
            print(f"[Aster] 订阅用户数据失败: {e}")
    
    def _start_listen_key_keepalive(self):
        """启动listen key保活"""
        def keepalive():
            while self.listen_key:
                try:
                    time.sleep(30 * 60)  # 30分钟
                    self._signed_request('PUT', '/fapi/v1/listenKey', {'listenKey': self.listen_key})
                except Exception as e:
                    print(f"[Aster] Listen key保活失败: {e}")
                    break
        
        thread = threading.Thread(target=keepalive, daemon=True)
        thread.start()
    
    def _subscribe_channel(self, channel: str):
        """订阅频道"""
        if not self.ws or not self.ws.sock or not self.ws.sock.connected:
            print(f"[Aster] WebSocket未连接，无法订阅频道: {channel}")
            return
            
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [channel],
            "id": int(time.time() * 1000)
        }
        try:
            self.ws.send(json.dumps(subscribe_msg))
            print(f"[Aster] 订阅频道成功: {channel}")
        except Exception as e:
            print(f"[Aster] 订阅频道失败: {channel}, 错误: {e}")
    
    def watch_account(self, callback: Callable[[AsterAccountSnapshot], None]):
        """监听账户更新"""
        self.account_callbacks.append(callback)
    
    def watch_order(self, callback: Callable[[List[AsterOrder]], None]):
        """监听订单更新"""
        self.order_callbacks.append(callback)
    
    def watch_depth(self, symbol: str, callback: Callable[[AsterDepth], None]):
        """监听深度更新"""
        self.depth_callbacks.append(callback)
        channel = f"{symbol.lower()}@depth5@100ms"
        # 延迟订阅，等待WebSocket连接建立
        def delayed_subscribe():
            time.sleep(2)  # 等待2秒确保连接建立
            self._subscribe_channel(channel)
        
        thread = threading.Thread(target=delayed_subscribe, daemon=True)
        thread.start()
    
    def watch_ticker(self, symbol: str, callback: Callable[[AsterTicker], None]):
        """监听Ticker更新"""
        self.ticker_callbacks.append(callback)
        channel = f"{symbol.lower()}@ticker"
        # 延迟订阅，等待WebSocket连接建立
        def delayed_subscribe():
            time.sleep(2)  # 等待2秒确保连接建立
            self._subscribe_channel(channel)
        
        thread = threading.Thread(target=delayed_subscribe, daemon=True)
        thread.start()
    
    def watch_kline(self, symbol: str, interval: str, callback: Callable[[List[AsterKline]], None]):
        """监听K线更新"""
        self.kline_callbacks.append(callback)
        channel = f"{symbol.lower()}@kline_{interval}"
        # 延迟订阅，等待WebSocket连接建立
        def delayed_subscribe():
            time.sleep(2)  # 等待2秒确保连接建立
            self._subscribe_channel(channel)
        
        thread = threading.Thread(target=delayed_subscribe, daemon=True)
        thread.start()
        
        # 初始化K线数据
        self.last_klines = self.get_klines(symbol, interval, 100)
    
    def get_depth(self, symbol: str, limit: int = 5) -> AsterDepth:
        """获取深度数据"""
        params = {'symbol': symbol, 'limit': limit}
        response = self._public_request('GET', '/fapi/v1/depth', params)
        
        bids = [AsterDepthLevel(price=level[0], quantity=level[1]) 
                for level in response.get('bids', [])]
        asks = [AsterDepthLevel(price=level[0], quantity=level[1]) 
                for level in response.get('asks', [])]
        
        return AsterDepth(
            symbol=response.get('symbol', ''),
            last_update_id=response.get('lastUpdateId', 0),
            bids=bids,
            asks=asks
        )
    
    def get_ticker(self, symbol: str) -> AsterTicker:
        """获取Ticker数据"""
        params = {'symbol': symbol}
        response = self._public_request('GET', '/fapi/v1/ticker/24hr', params)
        
        return AsterTicker(
            symbol=response.get('symbol', ''),
            last_price=response.get('lastPrice', '0'),
            open_price=response.get('openPrice', '0'),
            high_price=response.get('highPrice', '0'),
            low_price=response.get('lowPrice', '0'),
            volume=response.get('volume', '0'),
            quote_volume=response.get('quoteVolume', '0'),
            price_change=response.get('priceChange', '0'),
            price_change_percent=response.get('priceChangePercent', '0')
        )
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[AsterKline]:
        """获取K线数据"""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        response = self._public_request('GET', '/fapi/v1/klines', params)
        
        klines = []
        for k in response:
            klines.append(AsterKline(
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
    
    def get_account(self) -> AsterAccountSnapshot:
        """获取账户信息"""
        response = self._signed_request('GET', '/fapi/v2/account')
        
        assets = []
        for asset_data in response.get('assets', []):
            assets.append(AsterAccountAsset(
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
            positions.append(AsterAccountPosition(
                symbol=pos_data.get('symbol', ''),
                position_amt=pos_data.get('positionAmt', '0'),
                entry_price=pos_data.get('entryPrice', '0'),
                unrealized_profit=pos_data.get('unrealizedProfit', '0'),
                leverage=pos_data.get('leverage', '1'),
                isolated=pos_data.get('isolated', False),
                position_side=pos_data.get('positionSide', 'BOTH'),
                update_time=int(pos_data.get('updateTime', 0))
            ))
        
        self.account_snapshot = AsterAccountSnapshot(
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
    
    def get_open_orders(self, symbol: str = None) -> List[AsterOrder]:
        """获取未成交订单"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        response = self._signed_request('GET', '/fapi/v1/openOrders', params)
        
        orders = []
        for order_data in response:
            order = AsterOrder(
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
            
            # 更新缓存
            with self.lock:
                self.open_orders[order.order_id] = order
        
        return orders
    
    def create_order(self, params: Dict) -> AsterOrder:
        """创建订单"""
        response = self._signed_request('POST', '/fapi/v1/order', params)
        
        order = AsterOrder(
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
        
        # 更新缓存
        with self.lock:
            self.open_orders[order.order_id] = order
        
        return order
    
    def cancel_order(self, symbol: str, order_id: int = None, client_order_id: str = None) -> AsterOrder:
        """撤销订单"""
        params = {'symbol': symbol}
        if order_id:
            params['orderId'] = order_id
        if client_order_id:
            params['origClientOrderId'] = client_order_id
        
        response = self._signed_request('DELETE', '/fapi/v1/order', params)
        
        order = AsterOrder(
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
        
        # 从缓存中移除
        with self.lock:
            self.open_orders.pop(order.order_id, None)
        
        return order
    
    def cancel_all_orders(self, symbol: str) -> List[Dict]:
        """撤销所有订单"""
        params = {'symbol': symbol}
        response = self._signed_request('DELETE', '/fapi/v1/allOpenOrders', params)
        
        # 清空缓存
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
    
    def create_order_by_usdt(self, symbol: str, side: str, usdt_amount: float, order_type: str = "MARKET", price: float = None) -> AsterOrder:
        """按USDT金额下单
        
        Args:
            symbol: 交易对，如 'BTCUSDT'
            side: 买卖方向，'BUY' 或 'SELL'
            usdt_amount: USDT金额
            order_type: 订单类型，'MARKET' 或 'LIMIT'
            price: 限价单价格，市价单时可为None
        """
        # 获取当前价格
        ticker = self.get_ticker(symbol)
        if not ticker or float(ticker.last_price) <= 0:
            raise ValueError("无法获取当前价格")
        
        current_price = float(ticker.last_price)
        
        if order_type == "MARKET":
            # 市价单：计算数量 = USDT金额 / 当前价格
            quantity = usdt_amount / current_price
            # 根据交易对精度调整数量
            if symbol == "BTCUSDT":
                quantity = round(quantity, 2)  # BTC精度为0.01
            elif symbol == "ETHUSDT":
                quantity = round(quantity, 3)  # ETH精度为0.001
            else:
                quantity = round(quantity, 4)  # 默认精度
            
            params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': str(quantity),
            }
        elif order_type == "LIMIT":
            if price is None:
                raise ValueError("限价单必须指定价格")
            # 限价单：计算数量 = USDT金额 / 指定价格
            quantity = usdt_amount / float(price)
            # 根据交易对精度调整数量
            if symbol == "BTCUSDT":
                quantity = round(quantity, 2)  # BTC精度为0.01
            elif symbol == "ETHUSDT":
                quantity = round(quantity, 3)  # ETH精度为0.001
            else:
                quantity = round(quantity, 4)  # 默认精度
            
            # 修正价格精度
            if symbol == "BTCUSDT":
                price = round(price, 1)  # BTC价格精度为0.1
            elif symbol == "ETHUSDT":
                price = round(price, 2)  # ETH价格精度为0.01
            else:
                price = round(price, 4)  # 默认价格精度
            
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

    def get_symbol_info(self, symbol: str) -> dict:
        """获取交易对的精度和最小下单量等信息"""
        info = self._public_request('GET', '/fapi/v1/exchangeInfo')
        for s in info.get('symbols', []):
            if s['symbol'] == symbol:
                return s
        raise ValueError(f"未找到交易对信息: {symbol}")

    def create_order_auto(self, symbol, side, usdt_amount, order_type="MARKET", price=None):
        """自动化下单，按USDT金额自动换算数量和精度，支持市价单和限价单"""
        info = self.get_symbol_info(symbol)
        lot_size = [f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'][0]
        min_qty = float(lot_size['minQty'])
        qty_step = float(lot_size['stepSize'])
        price_filter = [f for f in info['filters'] if f['filterType'] == 'PRICE_FILTER'][0]
        price_tick = float(price_filter['tickSize'])

        # 获取价格
        if order_type == "MARKET":
            ticker = self.get_ticker(symbol)
            price = float(ticker.last_price)
        elif price is None:
            raise ValueError("限价单必须指定价格")

        # 计算数量
        quantity = usdt_amount / price
        # 修正到最接近的step
        quantity = max(quantity, min_qty)
        quantity = (int(quantity / qty_step)) * qty_step
        quantity = round(quantity, 8)  # 防止浮点误差

        # 校验最小下单量
        if quantity < min_qty:
            raise ValueError(f"下单数量{quantity}低于最小下单量{min_qty}")

        # 修正价格精度
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

    def get_all_symbols(self) -> list:
        """获取所有支持交易的合约交易对列表"""
        info = self._public_request('GET', '/fapi/v1/exchangeInfo')
        symbols = []
        for s in info.get('symbols', []):
            if s.get('status') == 'TRADING':
                symbols.append(s['symbol'])
        return symbols

    def get_max_leverage(self, symbol: str) -> int:
        """获取指定交易对的最大杠杆倍数"""
        # /fapi/v1/leverageBracket 返回每个symbol的分层杠杆信息
        params = {'symbol': symbol}
        result = self._signed_request('GET', '/fapi/v1/leverageBracket', params)
        # 兼容返回为list或dict
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
            order = AsterOrder(
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