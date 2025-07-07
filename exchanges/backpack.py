"""
Backpack交易所API封装
"""
import time
import base64
import json
import requests
import logging
from typing import Dict, List, Optional, Any
from nacl.signing import SigningKey
from nacl.encoding import Base64Encoder
from config import BACKPACK_API_KEY, BACKPACK_API_SECRET
from utils.helper import adapt_symbol

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Backpack:
    """Backpack交易所API封装"""
    def __init__(self, api_key: str = None, api_secret: str = None, base_url: str = "https://api.backpack.exchange"):
        self.api_key = api_key or BACKPACK_API_KEY
        self.api_secret = api_secret or BACKPACK_API_SECRET
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        logger.info(f"Backpack API初始化完成，base_url: {base_url}")

    def _timestamp(self):
        return int(time.time() * 1000)

    def _sign(self, instruction: str, params: Dict = None, data: Any = None, window: int = 5000, method: str = 'GET') -> Dict[str, str]:
        """生成Backpack签名头"""
        params = params or {}
        # 获取服务器时间并同步本地时间戳
        try:
            server_time_resp = requests.get(self.base_url + "/api/v1/time", timeout=2, proxies={})
            if server_time_resp.status_code == 200:
                resp_json = server_time_resp.json()
                if isinstance(resp_json, dict) and "serverTime" in resp_json:
                    server_time = int(resp_json["serverTime"])
                elif isinstance(resp_json, int):
                    server_time = resp_json
                else:
                    server_time = int(str(resp_json))
                ts = server_time  # 使用服务器时间戳
                print(f"[调试] 本地时间戳: {self._timestamp()}, 服务器时间戳: {server_time}, 差值: {self._timestamp() - server_time} ms")
            else:
                ts = self._timestamp()
                print(f"[调试] 获取服务器时间失败，状态码: {server_time_resp.status_code}，使用本地时间戳: {ts}")
        except Exception as e:
            ts = self._timestamp()
            print(f"[调试] 获取服务器时间异常: {e}，使用本地时间戳: {ts}")
        
        # 构建签名字符串
        sign_str = f"instruction={instruction}"
        
        if method in ['POST', 'DELETE']:
            # POST/DELETE请求：使用查询字符串格式进行签名（按官方文档要求）
            if data is not None:
                # 将data转换为查询字符串格式，确保布尔值格式一致
                param_items = sorted(data.items())
                param_parts = []
                for k, v in param_items:
                    # 确保布尔值格式与JSON一致
                    if isinstance(v, bool):
                        param_parts.append(f"{k}={str(v).lower()}")  # true/false
                    else:
                        param_parts.append(f"{k}={v}")
                param_str = '&'.join(param_parts)
                if param_str:
                    sign_str += f"&{param_str}"
                logger.debug(f"POST/DELETE签名参数: {param_str}")
            # 如果没有data，则不添加任何参数
        elif params:
            # GET请求：参数排序后转为query string
            param_items = sorted(params.items())
            param_str = '&'.join(f"{k}={v}" for k, v in param_items)
            if param_str:
                sign_str += f"&{param_str}"
        
        sign_str += f"&timestamp={ts}&window={window}"
        # logger.info(f"最终签名字符串: {sign_str}")
        
        # 签名
        sk = SigningKey(base64.b64decode(self.api_secret))
        signature = sk.sign(sign_str.encode(), encoder=Base64Encoder).signature.decode()
        
        # 返回头
        headers = {
            'X-API-KEY': self.api_key,
            'X-SIGNATURE': signature,
            'X-TIMESTAMP': str(ts),
            'X-WINDOW': str(window)
        }
        logger.debug(f"生成签名头: {headers}")
        return headers

    def _request(self, method: str, endpoint: str, instruction: str, params: Dict = None, data: Any = None, window: int = 5000) -> Any:
        """通用REST请求"""
        url = self.base_url + endpoint
        
        headers = self._sign(instruction, params or {}, data, window, method)
        
        # 记录请求详情
        # logger.info(f"发送请求: {method} {url}")
        # logger.info(f"指令: {instruction}")
        # logger.info(f"参数: {params}")
        # logger.info(f"请求体: {data}")
        # logger.info(f"时间戳: {headers.get('X-TIMESTAMP')}")
        # logger.info(f"API Key: {self.api_key[:8]}...")
        
        # 确保Content-Type头不被覆盖
        headers['Content-Type'] = 'application/json'
        
        try:
            if method == 'GET':
                resp = requests.get(url, params=params, headers=headers)
            elif method == 'POST':
                # 使用JSON格式发送请求体
                body_json = json.dumps(data) if data is not None else '{}'
                logger.info(f"发送POST请求体: {body_json}")
                resp = requests.post(url, data=body_json, headers=headers)
            elif method == 'DELETE':
                # 使用JSON格式发送请求体
                body_json = json.dumps(data) if data is not None else '{}'
                logger.info(f"发送DELETE请求体: {body_json}")
                resp = requests.delete(url, data=body_json, headers=headers)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            # 记录响应详情
            # logger.info(f"响应状态码: {resp.status_code}")
            # logger.info(f"响应头: {dict(resp.headers)}")
            
            if resp.status_code == 200:
                response_data = resp.json()
                # logger.info(f"响应成功: {response_data}")
                return response_data
            else:
                # 详细记录错误信息
                error_text = resp.text
                logger.error(f"请求失败 - 状态码: {resp.status_code}")
                logger.error(f"错误响应: {error_text}")
                
                # 尝试解析错误JSON
                try:
                    error_json = resp.json()
                    logger.error(f"错误JSON: {error_json}")
                    if 'msg' in error_json:
                        logger.error(f"错误消息: {error_json['msg']}")
                except:
                    logger.error(f"无法解析错误JSON: {error_text}")
                
                resp.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"未知异常: {type(e).__name__}: {e}")
            raise

    # 账户信息
    def get_account(self) -> dict:
        """获取账户信息（资产、余额等）"""
        logger.info("开始获取账户信息")
        try:
            result = self._request('GET', '/api/v1/account', 'accountQueryAll')
            logger.info(f"账户信息获取成功: {result}")
            return result
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")
            raise

    # 获取账户余额
    def get_balances(self) -> dict:
        """获取账户余额（只用balanceQuery指令）"""
        logger.info("开始获取账户余额")
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                balances = self._request('GET', '/api/v1/capital', 'balanceQuery')
                if isinstance(balances, dict):
                    # logger.info(f"余额获取成功: {balances}")
                    return balances
                else:
                    logger.warning(f"余额返回格式异常: {type(balances)} - {balances}")
                    return {}
                    
            except requests.exceptions.HTTPError as e:
                retry_count += 1
                logger.error(f"余额查询HTTP错误 (第{retry_count}次): {e}")
                
                if e.response is not None:
                    status_code = e.response.status_code
                    error_text = e.response.text
                    logger.error(f"错误状态码: {status_code}")
                    logger.error(f"错误响应: {error_text}")
                    
                    # 尝试解析错误JSON
                    try:
                        error_json = e.response.json()
                        logger.error(f"错误JSON: {error_json}")
                        if 'msg' in error_json:
                            error_msg = error_json['msg']
                            logger.error(f"错误消息: {error_msg}")
                            
                            # 分析具体错误类型
                            if 'invalid signature' in error_msg.lower():
                                logger.error("签名无效 - 可能是时间戳问题或API密钥错误")
                            elif 'permission denied' in error_msg.lower():
                                logger.error("权限被拒绝 - 检查API Key权限设置")
                            elif 'rate limit' in error_msg.lower():
                                logger.error("请求频率限制 - 需要降低请求频率")
                            elif 'invalid' in error_msg.lower():
                                logger.error("参数无效 - 检查请求参数")
                    except:
                        logger.error(f"无法解析错误JSON: {error_text}")
                    
                    # 如果是400错误且还有重试次数，则等待后重试
                    if status_code == 400 and retry_count <= max_retries:
                        wait_time = retry_count * 2  # 递增等待时间
                        logger.info(f"等待{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"余额查询失败，已达到最大重试次数或非400错误")
                        return {}
                        
            except requests.exceptions.RequestException as e:
                retry_count += 1
                logger.error(f"余额查询网络异常 (第{retry_count}次): {type(e).__name__}: {e}")
                if retry_count <= max_retries:
                    wait_time = retry_count * 2
                    logger.info(f"等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("余额查询网络异常，已达到最大重试次数")
                    return {}
                    
            except Exception as e:
                logger.error(f"余额查询未知异常: {type(e).__name__}: {e}")
                return {}
        
        logger.error("余额查询失败，已达到最大重试次数")
        return {}

    # 持仓信息（官方文档 /api/v1/position）
    def get_positions(self) -> list:
        """获取所有合约持仓信息（官方规范）"""
        logger.info("开始获取持仓信息")
        try:
            positions = self._request('GET', '/api/v1/position', 'positionQuery')
            logger.info(f"持仓信息获取成功: {positions}")
            return positions
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return []

    # 交易对/合约信息
    def get_all_symbols(self) -> list:
        """获取所有交易对/合约（返回市场字典列表）"""
        logger.info("开始获取所有交易对")
        try:
            symbols = self._request('GET', '/api/v1/markets', 'marketQuery')
            logger.info(f"交易对获取成功，数量: {len(symbols) if isinstance(symbols, list) else '未知'}")
            return symbols
        except Exception as e:
            logger.error(f"获取交易对失败: {e}")
            return []

    # 获取单个交易对最大杠杆（Backpack部分合约支持杠杆，需查markets接口）
    def get_max_leverage(self, symbol: str) -> int:
        logger.info(f"开始获取{symbol}最大杠杆")
        try:
            markets = self._request('GET', '/api/v1/markets', 'marketQuery')
            for m in markets:
                if isinstance(m, dict) and m.get('symbol') == symbol:
                    leverage = int(m.get('maxLeverage', 1))
                    logger.info(f"{symbol}最大杠杆: {leverage}")
                    return leverage
            logger.warning(f"未找到{symbol}的杠杆信息")
            return 1
        except Exception as e:
            logger.error(f"获取杠杆失败: {e}")
            return 1

    # 下单（市价单/限价单）
    def create_order(self, params: dict) -> dict:
        """创建订单，params需包含symbol/side/orderType/quantity/price等"""
        logger.info(f"开始创建订单: {params}")
        # 严格参数映射，避免None，并确保布尔值正确
        order_data = {}
        for k in [
            'symbol', 'side', 'orderType', 'quantity', 'price', 'timeInForce',
            'selfTradePrevention', 'reduceOnly', 'clientId', 'triggerBy', 'triggerPrice', 'triggerQuantity',
            'stopLossTriggerBy', 'stopLossTriggerPrice', 'stopLossLimitPrice',
            'takeProfitTriggerBy', 'takeProfitTriggerPrice', 'takeProfitLimitPrice',
            'postOnly', 'closeOnTrigger', 'quoteQuantity', 'strategyId'
        ]:
            v = params.get(k)
            if v is not None:
                # 确保布尔值正确传递
                if isinstance(v, bool):
                    order_data[k] = v  # json.dumps会自动转为true/false
                else:
                    order_data[k] = v
        
        logger.info(f"订单数据: {order_data}")
        try:
            result = self._request('POST', '/api/v1/order', 'orderExecute', data=order_data)
            logger.info(f"订单创建成功: {result}")
            return result
        except Exception as e:
            logger.error(f"订单创建失败: {e}")
            raise

    # 获取未成交订单
    def get_open_orders(self, symbol: str) -> list:
        logger.info(f"开始获取{symbol}未成交订单")
        params = {"symbol": symbol}
        try:
            orders = self._request('GET', '/api/v1/orders', 'orderQueryAll', params=params)
            logger.info(f"未成交订单获取成功: {orders}")
            return orders
        except Exception as e:
            logger.error(f"获取未成交订单失败: {e}")
            return []

    # 获取单个订单
    def get_order(self, symbol: str, order_id: str = None, client_id: int = None) -> dict:
        logger.info(f"开始获取订单详情: symbol={symbol}, order_id={order_id}, client_id={client_id}")
        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_id:
            params["clientId"] = client_id
        try:
            order = self._request('GET', '/api/v1/order', 'orderQuery', params=params)
            logger.info(f"订单详情获取成功: {order}")
            return order
        except Exception as e:
            logger.error(f"获取订单详情失败: {e}")
            raise

    # 撤销订单
    def cancel_order(self, symbol: str, order_id: str = None, client_id: int = None) -> dict:
        logger.info(f"开始撤销订单: symbol={symbol}, order_id={order_id}, client_id={client_id}")
        payload = {"symbol": symbol}
        if order_id:
            payload["orderId"] = order_id
        if client_id:
            payload["clientId"] = client_id
        try:
            result = self._request('DELETE', '/api/v1/order', 'orderCancel', data=payload)
            logger.info(f"订单撤销成功: {result}")
            return result
        except Exception as e:
            logger.error(f"订单撤销失败: {e}")
            raise

    # 批量撤销
    def cancel_all_orders(self, symbol: str) -> list:
        logger.info(f"开始批量撤销{symbol}所有订单")
        payload = {"symbol": symbol}
        try:
            result = self._request('DELETE', '/api/v1/orders', 'orderCancelAll', data=payload)
            logger.info(f"批量撤销成功: {result}")
            return result
        except Exception as e:
            logger.error(f"批量撤销失败: {e}")
            raise

    # 获取订单历史（修正为 /api/v1/orders/history）
    def get_all_orders(self, symbol: str = None, limit: int = 100) -> list:
        logger.info(f"开始获取订单历史: symbol={symbol}, limit={limit}")
        params = {'limit': limit}
        if symbol:
            params['symbol'] = symbol
        try:
            orders = self._request('GET', '/api/v1/orders/history', 'orderHistoryQueryAll', params=params)
            logger.info(f"订单历史获取成功，数量: {len(orders) if isinstance(orders, list) else '未知'}")
            return orders
        except Exception as e:
            logger.error(f"获取订单历史失败: {e}")
            return []

    # 获取成交历史（修正为 /api/v1/fills），兼容symbol格式
    def get_user_trades(self, symbol: str = None, limit: int = 100) -> list:
        """获取成交历史（fill history）"""
        logger.info(f"开始获取成交历史: symbol={symbol}, limit={limit}")
        if symbol:
            symbol = adapt_symbol(symbol, 'backpack')
        params = {
            'limit': limit
        }
        if symbol:
            params['symbol'] = symbol
        try:
            # 修正接口路径
            fills = self._request('GET', '/wapi/v1/history/fills', 'fillHistoryQueryAll', params=params)
            logger.info(f"成交历史获取成功，数量: {len(fills) if isinstance(fills, list) else '未知'}")
            return fills
        except Exception as e:
            logger.error(f"获取成交历史失败: {e}")
            return []

    # 获取深度（修正为 /api/v1/depth）
    def get_depth(self, symbol: str, limit: int = 5) -> dict:
        logger.info(f"开始获取深度: symbol={symbol}, limit={limit}")
        params = {'symbol': symbol, 'limit': limit}
        try:
            depth = self._request('GET', '/api/v1/depth', 'marketDepthQuery', params=params)
            # 转换为标准格式
            if isinstance(depth, dict):
                result = {
                    'asks': depth.get('asks', []),
                    'bids': depth.get('bids', [])
                }
                logger.info(f"深度获取成功: asks={len(result['asks'])}, bids={len(result['bids'])}")
                return result
            logger.info(f"深度获取成功: {depth}")
            return depth
        except Exception as e:
            logger.error(f"获取深度失败: {e}")
            raise

    # 获取Ticker
    def get_ticker(self, symbol: str) -> dict:
        logger.info(f"开始获取Ticker: symbol={symbol}")
        params = {'symbol': symbol}
        try:
            ticker = self._request('GET', '/api/v1/ticker', 'marketTickerQuery', params=params)
            # 转换为标准格式
            if isinstance(ticker, dict):
                result = {
                    'lastPrice': ticker.get('lastPrice', '0'),
                    'symbol': ticker.get('symbol', symbol)
                }
                logger.info(f"Ticker获取成功: {result}")
                return result
            logger.info(f"Ticker获取成功: {ticker}")
            return ticker
        except Exception as e:
            logger.error(f"获取Ticker失败: {e}")
            raise

    # 获取K线
    def get_klines(self, symbol: str, interval: str, limit: int = 100, start_time: int = None, end_time: int = None, price_type: str = None) -> list:
        """
        获取K线，start_time/end_time为UTC秒，interval如'1m'，limit为K线根数
        若未指定start_time，则自动取最近limit根K线
        """
        logger.info(f"开始获取K线: symbol={symbol}, interval={interval}, limit={limit}")
        import time
        interval_map = {
            '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
            '1h': 3600, '2h': 7200, '4h': 14400, '6h': 21600, '8h': 28800,
            '12h': 43200, '1d': 86400, '3d': 259200, '1w': 604800, '1month': 2592000
        }
        interval_sec = interval_map.get(interval, 60)
        now = int(time.time())
        if end_time is None:
            end_time = now
        if start_time is None:
            start_time = end_time - interval_sec * limit
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': start_time,
            'endTime': end_time
        }
        if price_type:
            params['priceType'] = price_type
        
        logger.info(f"K线参数: {params}")
        try:
            klines = self._request('GET', '/api/v1/klines', 'marketKlineQuery', params=params)
            logger.info(f"K线获取成功，数量: {len(klines) if isinstance(klines, list) else '未知'}")
            return klines
        except Exception as e:
            logger.error(f"获取K线失败: {e}")
            raise

    # 设置杠杆（Backpack不支持动态设置杠杆，默认使用50倍）
    def set_leverage(self, symbol: str, leverage: int) -> dict:
        logger.info(f"Backpack不支持动态设置杠杆，默认使用50倍杠杆: symbol={symbol}, requested_leverage={leverage}")
        # Backpack合约默认使用50倍杠杆，无法动态修改
        return {'message': 'Backpack使用默认50倍杠杆，无法动态设置'}

    def get_order_history(self, symbol: str = None, limit: int = 100, offset: int = 0, sort_direction: str = 'Desc') -> list:
        """获取订单历史"""
        logger.info(f"开始获取订单历史: symbol={symbol}, limit={limit}, offset={offset}")
        params = {
            'limit': limit,
            'offset': offset,
            'sortDirection': sort_direction
        }
        if symbol:
            params['symbol'] = symbol
        try:
            # 修正接口路径
            orders = self._request('GET', '/wapi/v1/history/orders', 'orderHistoryQueryAll', params=params)
            logger.info(f"订单历史获取成功，数量: {len(orders) if isinstance(orders, list) else '未知'}")
            return orders
        except Exception as e:
            logger.error(f"获取订单历史失败: {e}")
            return []

    def get_pnl_history(self, symbol: str = None, limit: int = 100, offset: int = 0, sort_direction: str = 'Desc') -> list:
        """获取盈亏历史"""
        logger.info(f"开始获取盈亏历史: symbol={symbol}, limit={limit}, offset={offset}")
        params = {
            'limit': limit,
            'offset': offset,
            'sortDirection': sort_direction
        }
        if symbol:
            params['symbol'] = symbol
        try:
            pnl = self._request('GET', '/api/v1/history/pnl', 'pnlHistoryQueryAll', params=params)
            logger.info(f"盈亏历史获取成功，数量: {len(pnl) if isinstance(pnl, list) else '未知'}")
            return pnl
        except Exception as e:
            logger.error(f"获取盈亏历史失败: {e}")
            return []

    def get_order_fills(self, symbol: str, direction: str, entry_time: str = None, min_qty: float = 0) -> list:
        """
        获取指定symbol、方向、入场时间之后的所有成交（fills）
        :param symbol: 交易对
        :param direction: 'long' or 'short'
        :param entry_time: ISO格式字符串，订单开仓时间
        :param min_qty: 最小成交数量（可选）
        :return: 成交列表
        """
        from datetime import datetime
        symbol = adapt_symbol(symbol, 'backpack')
        fills = self.get_user_trades(symbol=symbol, limit=200)
        # 方向映射
        if direction == 'long':
            side = 'Bid'
        else:
            side = 'Ask'
        # 时间过滤
        entry_ts = None
        if entry_time:
            try:
                entry_ts = int(datetime.fromisoformat(entry_time).timestamp() * 1000)
            except Exception:
                entry_ts = None
        result = []
        for f in fills:
            # 方向、时间过滤
            if f.get('side') == side:
                if entry_ts is None or int(f.get('time', 0)) >= entry_ts:
                    if min_qty == 0 or float(f.get('quantity', 0)) >= min_qty:
                        result.append(f)
        return result

    def get_position_history(self, symbol: str = None, limit: int = 100, offset: int = 0, state: str = 'Closed') -> list:
        """
        获取合约持仓历史（每一笔完整的开/平仓记录，已平仓/当前持仓均可查）
        :param symbol: 交易对
        :param limit: 返回条数
        :param offset: 分页偏移
        :param state: 'Closed'查历史，'Open'查当前
        :return: 持仓历史列表
        """
        logger.info(f"开始获取持仓历史: symbol={symbol}, limit={limit}, offset={offset}, state={state}")
        params = {'limit': limit, 'offset': offset, 'state': state}
        if symbol:
            from utils.helper import adapt_symbol
            params['symbol'] = adapt_symbol(symbol, 'backpack')
        try:
            positions = self._request('GET', '/wapi/v1/history/position', '', params=params)
            logger.info(f"持仓历史获取成功，数量: {len(positions) if isinstance(positions, list) else '未知'}")
            return positions
        except Exception as e:
            logger.error(f"获取持仓历史失败: {e}")
            return []

# 后续将依次补充账户、行情、下单、持仓等功能方法
