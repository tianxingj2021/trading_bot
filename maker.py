"""
做市策略 - 自动在盘口挂双边单，成交后只挂平仓方向单
"""
import asyncio
import time
from typing import Dict, List, Optional
from exchanges.aster import Aster
from config import ASTER_API_KEY, ASTER_API_SECRET, TRADE_SYMBOL, TRADE_AMOUNT, LOSS_LIMIT


class MakerStrategy:
    """做市策略实现"""
    
    def __init__(self):
        """初始化策略"""
        self.aster = Aster(ASTER_API_KEY, ASTER_API_SECRET)
        
        # 状态变量
        self.position: str = "none"  # "long", "short", "none"
        self.entry_price = 0
        self.order_buy = None
        self.order_sell = None
        self.ws_orderbook = None
        self.recent_unrealized_profit = 0
        self.last_position_amt = 0
        self.last_entry_price = 0
        
        # 全局订单状态监听队列
        self.pending_orders: List[Dict] = []
        
        # 启动订单状态监听
        asyncio.create_task(self._order_status_watcher())
        
        # 启动WebSocket订阅
        self._watch_orderbook_ws()
    
    async def _order_status_watcher(self):
        """异步订单状态监听器"""
        while True:
            if not self.pending_orders:
                await asyncio.sleep(0.5)
                continue
            
            for i in range(len(self.pending_orders) - 1, -1, -1):
                order_info = self.pending_orders[i]
                order_id = order_info["orderId"]
                last_status = order_info.get("lastStatus")
                
                try:
                    order = await self.aster.get_order(TRADE_SYMBOL, order_id=order_id)
                    if order:
                        if order.status != last_status:
                            print(f"[订单状态变化] 订单ID: {order_id}，新状态: {order.status}")
                            self.pending_orders[i]["lastStatus"] = order.status
                        
                        if order.status in ["FILLED", "CANCELED", "REJECTED", "EXPIRED"]:
                            self.pending_orders.pop(i)  # 移除已终结订单
                except Exception as e:
                    # 网络异常等，忽略
                    pass
            
            await asyncio.sleep(1)
    
    def _watch_orderbook_ws(self):
        """启动WebSocket订单簿订阅"""
        async def watch_loop():
            while True:
                try:
                    self.ws_orderbook = await self.aster.get_depth(TRADE_SYMBOL, 5)
                except Exception as e:
                    print(f"WS orderbook error: {e}")
                    await asyncio.sleep(2)
        
        asyncio.create_task(watch_loop())
    
    async def _place_order(self, side: str, price: float, amount: float, reduce_only: bool = False) -> Optional[Dict]:
        """
        下挂单
        
        Args:
            side: 买卖方向 ("BUY" | "SELL")
            price: 价格
            amount: 数量
            reduce_only: 是否仅减仓
        
        Returns:
            订单对象
        """
        try:
            params = {
                "symbol": TRADE_SYMBOL,
                "side": side,
                "type": "LIMIT",
                "quantity": amount,
                "price": price,
                "timeInForce": "GTX",
            }
            
            if reduce_only:
                params["reduceOnly"] = "true"
            
            order = await self.aster.create_order(params)
            
            if order and order.order_id:
                print(f"[下单成功] {side} {amount} @ {price} reduceOnly={reduce_only}，订单ID: {order.order_id}")
                self.pending_orders.append({"orderId": order.order_id})  # 加入监听队列
                return order
            else:
                print(f"[下单失败] {side} {amount} @ {price} reduceOnly={reduce_only}")
                return None
        except Exception as e:
            print(f"[下单异常] {side} {amount} @ {price} reduceOnly={reduce_only}: {e}")
            return None
    
    async def _get_position(self) -> Dict:
        """
        获取持仓信息
        
        Returns:
            持仓信息字典
        """
        try:
            account = await self.aster.get_account()
            if account and hasattr(account, 'total_unrealized_profit'):
                self.recent_unrealized_profit = float(account.total_unrealized_profit)
            
            if not account or not account.positions:
                return {"positionAmt": 0, "entryPrice": 0, "unrealizedProfit": 0}
            
            pos = next((p for p in account.positions if p.symbol == TRADE_SYMBOL), None)
            if not pos:
                return {"positionAmt": 0, "entryPrice": 0, "unrealizedProfit": 0}
            
            position_amt = float(pos.position_amt)
            entry_price = float(pos.entry_price)
            
            if position_amt != self.last_position_amt or entry_price != self.last_entry_price:
                print(f"[仓位变化] 持仓数量: {self.last_position_amt} => {position_amt}，开仓价: {self.last_entry_price} => {entry_price}")
                self.last_position_amt = position_amt
                self.last_entry_price = entry_price
            
            return {
                "positionAmt": position_amt,
                "entryPrice": entry_price,
                "unrealizedProfit": float(pos.unrealized_profit)
            }
        except Exception as e:
            return {"positionAmt": 0, "entryPrice": 0, "unrealizedProfit": 0}
    
    async def _market_close(self, side: str):
        """
        市价平仓
        
        Args:
            side: 买卖方向 ("SELL" | "BUY")
        """
        try:
            await self.aster.create_order({
                "symbol": TRADE_SYMBOL,
                "side": side,
                "type": "MARKET",
                "quantity": TRADE_AMOUNT,
                "reduceOnly": "true"
            })
        except Exception as e:
            print(f"市价平仓失败: {e}")
    
    async def _ensure_no_pending_reduce_only(self, side: str, price: float) -> bool:
        """
        检查当前是否有未成交的reduceOnly单
        
        Args:
            side: 买卖方向
            price: 价格
        
        Returns:
            是否有未成交的reduceOnly单
        """
        try:
            open_orders = await self.aster.get_open_orders(TRADE_SYMBOL)
            return not any(
                o.side == side and o.reduce_only and float(o.price) == price
                for o in open_orders
            )
        except Exception:
            return True
    
    async def _cancel_all_orders(self):
        """撤销所有订单"""
        try:
            await self.aster.cancel_all_orders(TRADE_SYMBOL)
        except Exception as e:
            print(f"撤销订单失败: {e}")
    
    async def run_strategy(self):
        """运行做市策略"""
        print("做市策略启动中...")
        
        while True:
            try:
                # 1. 获取盘口
                ob = self.ws_orderbook
                if not ob:
                    await asyncio.sleep(0.2)
                    continue
                
                buy1 = float(ob.bids[0].price) if ob.bids else None
                sell1 = float(ob.asks[0].price) if ob.asks else None
                
                if buy1 is None or sell1 is None:
                    await asyncio.sleep(0.2)
                    continue
                
                # 2. 检查当前持仓
                pos = await self._get_position()
                
                # 3. 获取当前挂单
                open_orders = await self.aster.get_open_orders(TRADE_SYMBOL)
                
                # 4. 无持仓时，保证双边挂单都成功且未被取消
                if abs(pos["positionAmt"]) < 0.00001:
                    # 撤销所有订单，重新挂双边单
                    await self._cancel_all_orders()
                    
                    order_buy = await self._place_order("BUY", buy1, TRADE_AMOUNT, False)
                    order_sell = await self._place_order("SELL", sell1, TRADE_AMOUNT, False)
                    
                    filled = False
                    last_buy1 = buy1
                    last_sell1 = sell1
                    
                    while not filled:
                        await asyncio.sleep(1)
                        
                        # 检查盘口是否变化
                        ob2 = self.ws_orderbook
                        if not ob2:
                            continue
                        
                        new_buy1 = float(ob2.bids[0].price) if ob2.bids else None
                        new_sell1 = float(ob2.asks[0].price) if ob2.asks else None
                        
                        if new_buy1 is None or new_sell1 is None:
                            continue
                        
                        need_replace = False
                        if new_buy1 != last_buy1 or new_sell1 != last_sell1:
                            need_replace = True
                        
                        # 检查订单状态
                        buy_order_status = None
                        sell_order_status = None
                        
                        if order_buy:
                            try:
                                buy_order_status = await self.aster.get_order(TRADE_SYMBOL, order_id=order_buy.order_id)
                            except:
                                pass
                        
                        if order_sell:
                            try:
                                sell_order_status = await self.aster.get_order(TRADE_SYMBOL, order_id=order_sell.order_id)
                            except:
                                pass
                        
                        if (not buy_order_status or not sell_order_status or
                            buy_order_status.status not in ["NEW", "PARTIALLY_FILLED"] or
                            sell_order_status.status not in ["NEW", "PARTIALLY_FILLED"]):
                            need_replace = True
                        
                        if need_replace:
                            await self._cancel_all_orders()
                            
                            # 重新获取盘口
                            ob3 = self.ws_orderbook
                            if not ob3:
                                continue
                            
                            buy1 = float(ob3.bids[0].price) if ob3.bids else None
                            sell1 = float(ob3.asks[0].price) if ob3.asks else None
                            
                            if buy1 is None or sell1 is None:
                                continue
                            
                            last_buy1 = buy1
                            last_sell1 = sell1
                            order_buy = await self._place_order("BUY", buy1, TRADE_AMOUNT, False)
                            order_sell = await self._place_order("SELL", sell1, TRADE_AMOUNT, False)
                            continue
                        
                        # 查询成交
                        pos2 = await self._get_position()
                        if pos2["positionAmt"] > 0.00001:
                            # 买单成交，持有多头
                            self.position = "long"
                            self.entry_price = pos2["entryPrice"]
                            filled = True
                            print(f"[开仓] 买单成交，持有多头 {TRADE_AMOUNT} @ {self.entry_price}")
                            break
                        elif pos2["positionAmt"] < -0.00001:
                            # 卖单成交，持有空头
                            self.position = "short"
                            self.entry_price = pos2["entryPrice"]
                            filled = True
                            print(f"[开仓] 卖单成交，持有空头 {TRADE_AMOUNT} @ {self.entry_price}")
                            break
                
                else:
                    # 有持仓时，只挂平仓方向的单，撤销所有不符的挂单
                    close_side = "SELL" if pos["positionAmt"] > 0 else "BUY"
                    close_price = sell1 if pos["positionAmt"] > 0 else buy1
                    
                    # 先撤销所有不是平仓方向的挂单
                    for order in open_orders:
                        if (order.side != close_side or 
                            not order.reduce_only or 
                            abs(float(order.price) - close_price) > 0.001):
                            try:
                                await self.aster.cancel_order(TRADE_SYMBOL, order_id=order.order_id)
                                print(f"[撤销非平仓方向挂单] 订单ID: {order.order_id} side: {order.side} price: {order.price}")
                            except:
                                pass
                    
                    # 检查是否已挂平仓方向的单
                    still_open_orders = await self.aster.get_open_orders(TRADE_SYMBOL)
                    has_close_order = any(
                        o.side == close_side and o.reduce_only and abs(float(o.price) - close_price) < 0.001
                        for o in still_open_orders
                    )
                    
                    if not has_close_order and abs(pos["positionAmt"]) > 0.00001:
                        # 只在没有未成交reduceOnly单且持仓未平时才下单
                        if await self._ensure_no_pending_reduce_only(close_side, close_price):
                            await self._place_order(close_side, close_price, TRADE_AMOUNT, True)
                    
                    # 平仓止损逻辑
                    pnl = 0
                    if self.position == "long":
                        pnl = (buy1 - self.entry_price) * TRADE_AMOUNT
                    elif self.position == "short":
                        pnl = (self.entry_price - sell1) * TRADE_AMOUNT
                    
                    if (pnl < -LOSS_LIMIT or 
                        self.recent_unrealized_profit < -LOSS_LIMIT or 
                        pos["unrealizedProfit"] < -LOSS_LIMIT):
                        
                        await self._cancel_all_orders()
                        await self._market_close(close_side)
                        
                        wait_count = 0
                        while True:
                            pos_check = await self._get_position()
                            if ((self.position == "long" and pos_check["positionAmt"] < 0.00001) or 
                                (self.position == "short" and pos_check["positionAmt"] > -0.00001)):
                                break
                            
                            await asyncio.sleep(0.5)
                            wait_count += 1
                            if wait_count > 20:
                                break
                        
                        print(f"[强制平仓] 亏损超限，方向: {self.position}，开仓价: {self.entry_price}，现价: {buy1 if self.position == 'long' else sell1}，估算亏损: {pnl:.4f} USDT，账户浮亏: {self.recent_unrealized_profit:.4f} USDT，持仓浮亏: {pos['unrealizedProfit']:.4f} USDT")
                        self.position = "none"
                    
                    # 检查是否已平仓
                    pos2 = await self._get_position()
                    if self.position == "long" and pos2["positionAmt"] < 0.00001:
                        print(f"[平仓] 多头平仓，开仓价: {self.entry_price}，平仓价: {sell1}，盈亏: {(sell1 - self.entry_price) * TRADE_AMOUNT} USDT")
                        self.position = "none"
                    elif self.position == "short" and pos2["positionAmt"] > -0.00001:
                        print(f"[平仓] 空头平仓，开仓价: {self.entry_price}，平仓价: {buy1}，盈亏: {(self.entry_price - buy1) * TRADE_AMOUNT} USDT")
                        self.position = "none"
                
                # 下一轮
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"策略异常: {e}")
                await self._cancel_all_orders()
                self.position = "none"
                await asyncio.sleep(2)


async def main():
    """主函数"""
    strategy = MakerStrategy()
    await strategy.run_strategy()


if __name__ == "__main__":
    asyncio.run(main()) 