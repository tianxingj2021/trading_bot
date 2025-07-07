"""
趋势策略V2 - 基于SMA30均线突破的自动化交易策略
"""
import asyncio
import time
from typing import Dict, List, Optional
from exchanges.aster import Aster
from config import (
    ASTER_API_KEY, ASTER_API_SECRET, TRADE_SYMBOL, TRADE_AMOUNT,
    LOSS_LIMIT, TRAILING_PROFIT
)
from utils.helper import get_position, get_sma30
from utils.log import log_trade, print_status, TradeLogItem
from utils.order import (
    place_market_order, place_stop_loss_order, place_trailing_stop_order,
    market_close, calc_stop_loss_price, calc_trailing_activation_price,
    to_price_1_decimal
)


class TrendStrategyV2:
    """趋势策略V2实现"""
    
    def __init__(self):
        """初始化策略"""
        self.aster = Aster(ASTER_API_KEY, ASTER_API_SECRET)
        
        # 快照数据
        self.account_snapshot = None
        self.open_orders: List = []
        self.depth_snapshot = None
        self.ticker_snapshot = None
        self.kline_snapshot: List = []
        
        # 交易统计
        self.trade_log: List[TradeLogItem] = []
        self.total_profit = 0
        self.total_trades = 0
        
        # 多类型订单锁
        self.order_type_locks: Dict[str, bool] = {}
        self.order_type_pending_order_id: Dict[str, Optional[str]] = {}
        self.order_type_unlock_timer: Dict[str, Optional[asyncio.Task]] = {}
        
        # 设置回调函数
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """设置回调函数"""
        # 账户更新回调
        self.aster.watch_account(self._on_account_update)
        
        # 订单更新回调
        self.aster.watch_order(self._on_order_update)
        
        # 深度更新回调
        self.aster.watch_depth(TRADE_SYMBOL, self._on_depth_update)
        
        # Ticker更新回调
        self.aster.watch_ticker(TRADE_SYMBOL, self._on_ticker_update)
        
        # K线更新回调
        self.aster.watch_kline(TRADE_SYMBOL, "1m", self._on_kline_update)
    
    def _on_account_update(self, data):
        """账户更新回调"""
        self.account_snapshot = data
    
    def _on_order_update(self, orders: List):
        """订单更新回调"""
        # 针对每种类型分别判断pendingOrderId是否需要解锁
        for order_type in list(self.order_type_pending_order_id.keys()):
            pending_order_id = self.order_type_pending_order_id[order_type]
            if pending_order_id:
                pending_order = next((o for o in orders if str(o.order_id) == str(pending_order_id)), None)
                if pending_order:
                    if pending_order.status and pending_order.status != "NEW":
                        self._unlock_operating(order_type)
                else:
                    # orders 里没有 pendingOrderId 对应的订单，说明已成交或撤销
                    self._unlock_operating(order_type)
        
        # 过滤掉 market 类型订单再赋值给 openOrders
        self.open_orders = [o for o in orders if o.type != 'MARKET'] if isinstance(orders, list) else []
    
    def _on_depth_update(self, depth):
        """深度更新回调"""
        self.depth_snapshot = depth
    
    def _on_ticker_update(self, ticker):
        """Ticker更新回调"""
        self.ticker_snapshot = ticker
    
    def _on_kline_update(self, klines: List):
        """K线更新回调"""
        self.kline_snapshot = klines
    
    def _is_ready(self) -> bool:
        """检查是否准备就绪"""
        return (
            self.account_snapshot and 
            self.ticker_snapshot and 
            self.depth_snapshot and 
            len(self.kline_snapshot) > 0
        )
    
    def _is_no_position(self, pos: Dict) -> bool:
        """检查是否无持仓"""
        return abs(pos.get("positionAmt", 0)) < 0.00001
    
    def _is_operating(self, order_type: str) -> bool:
        """检查是否正在操作"""
        return self.order_type_locks.get(order_type, False)
    
    def _lock_operating(self, order_type: str, timeout: int = 3):
        """锁定操作"""
        self.order_type_locks[order_type] = True
        
        # 清除之前的定时器
        if self.order_type_unlock_timer.get(order_type):
            self.order_type_unlock_timer[order_type].cancel()
        
        # 设置新的定时器
        async def unlock_timeout():
            await asyncio.sleep(timeout)
            self._unlock_operating(order_type)
            log_trade(self.trade_log, "error", f"{order_type}操作超时自动解锁")
        
        self.order_type_unlock_timer[order_type] = asyncio.create_task(unlock_timeout())
    
    def _unlock_operating(self, order_type: str):
        """解锁操作"""
        self.order_type_locks[order_type] = False
        self.order_type_pending_order_id[order_type] = None
        
        # 清除定时器
        if self.order_type_unlock_timer.get(order_type):
            self.order_type_unlock_timer[order_type].cancel()
            self.order_type_unlock_timer[order_type] = None
    
    async def _handle_open_position(
        self, 
        last_price: Optional[float], 
        last_sma30: float, 
        price: float,
        last_open_order: Dict
    ):
        """处理开仓逻辑"""
        # 撤销所有普通挂单和止损单
        if self.open_orders:
            self._lock_operating("MARKET")
            await self.aster.cancel_all_orders(TRADE_SYMBOL)
        
        # 仅在价格穿越SMA30时下市价单
        if last_price is not None:
            if last_price > last_sma30 and price < last_sma30:
                self._lock_operating("MARKET")
                await place_market_order(
                    self.aster,
                    self.open_orders,
                    self.order_type_locks,
                    self.order_type_unlock_timer,
                    self.order_type_pending_order_id,
                    "SELL",
                    TRADE_AMOUNT,
                    lambda log_type, detail: log_trade(self.trade_log, log_type, detail)
                )
                log_trade(self.trade_log, "open", f"下穿SMA30，市价开空: SELL @ {price}")
                last_open_order["side"] = "SELL"
                last_open_order["price"] = price
            elif last_price < last_sma30 and price > last_sma30:
                self._lock_operating("MARKET")
                await place_market_order(
                    self.aster,
                    self.open_orders,
                    self.order_type_locks,
                    self.order_type_unlock_timer,
                    self.order_type_pending_order_id,
                    "BUY",
                    TRADE_AMOUNT,
                    lambda log_type, detail: log_trade(self.trade_log, log_type, detail)
                )
                log_trade(self.trade_log, "open", f"上穿SMA30，市价开多: BUY @ {price}")
                last_open_order["side"] = "BUY"
                last_open_order["price"] = price
    
    async def _handle_position_management(
        self, 
        pos: Dict, 
        price: float, 
        last_sma30: float,
        last_close_order: Dict,
        last_stop_order: Dict
    ) -> Dict:
        """处理持仓管理"""
        direction = "long" if pos["positionAmt"] > 0 else "short"
        pnl = (price - pos["entryPrice"] if direction == "long" else pos["entryPrice"] - price) * abs(pos["positionAmt"])
        stop_side = "SELL" if direction == "long" else "BUY"
        
        stop_price = calc_stop_loss_price(pos["entryPrice"], abs(pos["positionAmt"]), direction, LOSS_LIMIT)
        activation_price = calc_trailing_activation_price(pos["entryPrice"], abs(pos["positionAmt"]), direction, TRAILING_PROFIT)
        
        has_stop = any(o.type == "STOP_MARKET" and o.side == stop_side for o in self.open_orders)
        has_trailing = any(o.type == "TRAILING_STOP_MARKET" and o.side == stop_side for o in self.open_orders)
        
        profit_move = 0.05
        profit_move_stop_price = (
            pos["entryPrice"] + profit_move / abs(pos["positionAmt"]) if direction == "long"
            else pos["entryPrice"] - profit_move / abs(pos["positionAmt"])
        )
        profit_move_stop_price = to_price_1_decimal(profit_move_stop_price)
        
        current_stop_order = next((o for o in self.open_orders if o.type == "STOP_MARKET" and o.side == stop_side), None)
        
        if pnl > 0.1 or pos.get("unrealizedProfit", 0) > 0.1:
            if not current_stop_order:
                self._lock_operating("MARKET")
                await place_stop_loss_order(
                    self.aster,
                    self.open_orders,
                    self.order_type_locks,
                    self.order_type_unlock_timer,
                    self.order_type_pending_order_id,
                    self.ticker_snapshot,
                    stop_side,
                    profit_move_stop_price,
                    lambda log_type, detail: log_trade(self.trade_log, log_type, detail)
                )
                has_stop = True
                log_trade(self.trade_log, "stop", f"盈利大于0.1u，挂盈利0.05u止损单: {stop_side} @ {profit_move_stop_price}")
            else:
                cur_stop_price = float(current_stop_order.stop_price)
                if abs(cur_stop_price - profit_move_stop_price) > 0.01:
                    self._lock_operating("MARKET")
                    await self.aster.cancel_order(TRADE_SYMBOL, order_id=current_stop_order.order_id)
                    self._lock_operating("MARKET")
                    await place_stop_loss_order(
                        self.aster,
                        self.open_orders,
                        self.order_type_locks,
                        self.order_type_unlock_timer,
                        self.order_type_pending_order_id,
                        self.ticker_snapshot,
                        stop_side,
                        profit_move_stop_price,
                        lambda log_type, detail: log_trade(self.trade_log, log_type, detail)
                    )
                    log_trade(self.trade_log, "stop", f"盈利大于0.1u，移动止损单到盈利0.05u: {stop_side} @ {profit_move_stop_price}")
                    has_stop = True
        
        if not has_stop:
            self._lock_operating("MARKET")
            await place_stop_loss_order(
                self.aster,
                self.open_orders,
                self.order_type_locks,
                self.order_type_unlock_timer,
                self.order_type_pending_order_id,
                self.ticker_snapshot,
                stop_side,
                to_price_1_decimal(stop_price),
                lambda log_type, detail: log_trade(self.trade_log, log_type, detail)
            )
        
        if not has_trailing:
            self._lock_operating("MARKET")
            await place_trailing_stop_order(
                self.aster,
                self.open_orders,
                self.order_type_locks,
                self.order_type_unlock_timer,
                self.order_type_pending_order_id,
                stop_side,
                to_price_1_decimal(activation_price),
                abs(pos["positionAmt"]),
                lambda log_type, detail: log_trade(self.trade_log, log_type, detail)
            )
        
        if pnl < -LOSS_LIMIT or pos.get("unrealizedProfit", 0) < -LOSS_LIMIT:
            if self.open_orders:
                self._lock_operating("MARKET")
                order_id_list = [o.order_id for o in self.open_orders]
                await self.aster.cancel_orders(TRADE_SYMBOL, order_id_list=order_id_list)
            
            self._lock_operating("MARKET")
            await market_close(
                self.aster,
                self.open_orders,
                self.order_type_locks,
                self.order_type_unlock_timer,
                self.order_type_pending_order_id,
                "SELL" if direction == "long" else "BUY",
                lambda log_type, detail: log_trade(self.trade_log, log_type, detail)
            )
            last_close_order["side"] = None
            last_close_order["price"] = None
            last_stop_order["side"] = None
            last_stop_order["price"] = None
            log_trade(self.trade_log, "close", f"止损平仓: {'SELL' if direction == 'long' else 'BUY'}")
            return {"closed": True, "pnl": pnl}
        
        return {"closed": False, "pnl": pnl}
    
    async def run_strategy(self):
        """运行策略"""
        last_sma30: Optional[float] = None
        last_price: Optional[float] = None
        last_open_order = {"side": None, "price": None}
        last_close_order = {"side": None, "price": None}
        last_stop_order = {"side": None, "price": None}
        
        print("趋势策略V2启动中...")
        
        while True:
            await asyncio.sleep(0.5)
            
            if not self._is_ready():
                continue
            
            last_sma30 = get_sma30(self.kline_snapshot)
            if last_sma30 is None:
                continue
            
            ob = self.depth_snapshot
            ticker = self.ticker_snapshot
            price = float(ticker.last_price)
            pos = get_position(self.account_snapshot, TRADE_SYMBOL)
            
            trend = "无信号"
            if price < last_sma30:
                trend = "做空"
            if price > last_sma30:
                trend = "做多"
            
            pnl = 0
            
            if self._is_no_position(pos):
                await self._handle_open_position(last_price, last_sma30, price, last_open_order)
                last_stop_order["side"] = None
                last_stop_order["price"] = None
            else:
                result = await self._handle_position_management(
                    pos, price, last_sma30, last_close_order, last_stop_order
                )
                pnl = result["pnl"]
                if result["closed"]:
                    self.total_trades += 1
                    self.total_profit += pnl
                    continue
            
            # 打印状态
            print_status({
                "ticker": ticker,
                "ob": ob,
                "sma": last_sma30,
                "trend": trend,
                "openOrder": (
                    {"side": last_open_order["side"], "price": last_open_order["price"], "amount": TRADE_AMOUNT}
                    if self._is_no_position(pos) and last_open_order["side"] and last_open_order["price"]
                    else None
                ),
                "closeOrder": (
                    {"side": last_close_order["side"], "price": last_close_order["price"], "amount": abs(pos["positionAmt"])}
                    if not self._is_no_position(pos) and last_close_order["side"] and last_close_order["price"]
                    else None
                ),
                "stopOrder": (
                    {"side": last_stop_order["side"], "stopPrice": last_stop_order["price"]}
                    if not self._is_no_position(pos) and last_stop_order["side"] and last_stop_order["price"]
                    else None
                ),
                "pos": pos,
                "pnl": pnl,
                "unrealized": pos.get("unrealizedProfit", 0),
                "tradeLog": self.trade_log,
                "totalProfit": self.total_profit,
                "totalTrades": self.total_trades,
                "openOrders": self.open_orders
            })
            
            last_price = price


async def main():
    """主函数"""
    strategy = TrendStrategyV2()
    await strategy.run_strategy()


if __name__ == "__main__":
    asyncio.run(main()) 