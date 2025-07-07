"""
订单工具函数
"""
import time
import threading
from typing import Dict, List, Optional, Callable
from exchanges.aster import Aster, AsterOrder
from config import TRADE_SYMBOL, TRADE_AMOUNT, TRAILING_CALLBACK_RATE
from utils.helper import to_price_1_decimal, to_qty_3_decimal


def is_operating(order_type_locks: Dict[str, bool], order_type: str) -> bool:
    """
    检查是否正在操作
    
    Args:
        order_type_locks: 订单类型锁字典
        order_type: 订单类型
    
    Returns:
        是否正在操作
    """
    return order_type_locks.get(order_type, False)


def lock_operating(
    order_type_locks: Dict[str, bool],
    order_type_unlock_timer: Dict[str, Optional[threading.Timer]],
    order_type_pending_order_id: Dict[str, Optional[str]],
    order_type: str,
    log_trade: Callable[[str, str], None],
    timeout: int = 3
):
    """
    锁定操作
    
    Args:
        order_type_locks: 订单类型锁字典
        order_type_unlock_timer: 订单类型解锁定时器字典
        order_type_pending_order_id: 订单类型待处理订单ID字典
        order_type: 订单类型
        log_trade: 日志记录函数
        timeout: 超时时间（秒）
    """
    order_type_locks[order_type] = True
    
    # 清除之前的定时器
    if order_type_unlock_timer.get(order_type):
        order_type_unlock_timer[order_type].cancel()
    
    # 设置新的定时器
    def unlock_timeout():
        order_type_locks[order_type] = False
        order_type_pending_order_id[order_type] = None
        log_trade("error", f"{order_type}操作超时自动解锁")
    
    timer = threading.Timer(timeout, unlock_timeout)
    order_type_unlock_timer[order_type] = timer
    timer.start()


def unlock_operating(
    order_type_locks: Dict[str, bool],
    order_type_unlock_timer: Dict[str, Optional[threading.Timer]],
    order_type_pending_order_id: Dict[str, Optional[str]],
    order_type: str
):
    """
    解锁操作
    
    Args:
        order_type_locks: 订单类型锁字典
        order_type_unlock_timer: 订单类型解锁定时器字典
        order_type_pending_order_id: 订单类型待处理订单ID字典
        order_type: 订单类型
    """
    order_type_locks[order_type] = False
    order_type_pending_order_id[order_type] = None
    
    # 清除定时器
    if order_type_unlock_timer.get(order_type):
        order_type_unlock_timer[order_type].cancel()
        order_type_unlock_timer[order_type] = None


async def deduplicate_orders(
    aster: Aster,
    open_orders: List[AsterOrder],
    order_type_locks: Dict[str, bool],
    order_type_unlock_timer: Dict[str, Optional[threading.Timer]],
    order_type_pending_order_id: Dict[str, Optional[str]],
    order_type: str,
    side: str,
    log_trade: Callable[[str, str], None]
):
    """
    去重订单
    
    Args:
        aster: Aster交易所实例
        open_orders: 未成交订单列表
        order_type_locks: 订单类型锁字典
        order_type_unlock_timer: 订单类型解锁定时器字典
        order_type_pending_order_id: 订单类型待处理订单ID字典
        order_type: 订单类型
        side: 买卖方向
        log_trade: 日志记录函数
    """
    same_type_orders = [o for o in open_orders if o.type == order_type and o.side == side]
    
    if len(same_type_orders) <= 1:
        return
    
    # 按时间排序，保留最新的
    same_type_orders.sort(key=lambda x: x.update_time or x.time or 0, reverse=True)
    to_cancel = same_type_orders[1:]
    order_id_list = [o.order_id for o in to_cancel]
    
    if order_id_list:
        try:
            lock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, log_trade)
            await aster.cancel_orders(TRADE_SYMBOL, order_id_list=order_id_list)
            log_trade("order", f"去重撤销重复{order_type}单: {','.join(map(str, order_id_list))}")
        except Exception as e:
            log_trade("error", f"去重撤单失败: {e}")
        finally:
            unlock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type)


async def place_order(
    aster: Aster,
    open_orders: List[AsterOrder],
    order_type_locks: Dict[str, bool],
    order_type_unlock_timer: Dict[str, Optional[threading.Timer]],
    order_type_pending_order_id: Dict[str, Optional[str]],
    side: str,
    price: float,
    amount: float,
    log_trade: Callable[[str, str], None],
    reduce_only: bool = False
) -> Optional[AsterOrder]:
    """
    下挂单
    
    Args:
        aster: Aster交易所实例
        open_orders: 未成交订单列表
        order_type_locks: 订单类型锁字典
        order_type_unlock_timer: 订单类型解锁定时器字典
        order_type_pending_order_id: 订单类型待处理订单ID字典
        side: 买卖方向
        price: 价格
        amount: 数量
        log_trade: 日志记录函数
        reduce_only: 是否仅减仓
    
    Returns:
        订单对象
    """
    order_type = "LIMIT"
    
    if is_operating(order_type_locks, order_type):
        return None
    
    params = {
        "symbol": TRADE_SYMBOL,
        "side": side,
        "type": order_type,
        "quantity": to_qty_3_decimal(amount),
        "price": to_price_1_decimal(price),
        "timeInForce": "GTX",
    }
    
    if reduce_only:
        params["reduceOnly"] = "true"
    
    await deduplicate_orders(aster, open_orders, order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, side, log_trade)
    
    lock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, log_trade)
    
    try:
        order = await aster.create_order(params)
        order_type_pending_order_id[order_type] = str(order.order_id)
        log_trade("order", f"挂单: {side} @ {params['price']} 数量: {params['quantity']} reduceOnly: {reduce_only}")
        return order
    except Exception as e:
        unlock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type)
        raise e


async def place_stop_loss_order(
    aster: Aster,
    open_orders: List[AsterOrder],
    order_type_locks: Dict[str, bool],
    order_type_unlock_timer: Dict[str, Optional[threading.Timer]],
    order_type_pending_order_id: Dict[str, Optional[str]],
    ticker_snapshot,
    side: str,
    stop_price: float,
    log_trade: Callable[[str, str], None]
) -> Optional[AsterOrder]:
    """
    下止损单
    
    Args:
        aster: Aster交易所实例
        open_orders: 未成交订单列表
        order_type_locks: 订单类型锁字典
        order_type_unlock_timer: 订单类型解锁定时器字典
        order_type_pending_order_id: 订单类型待处理订单ID字典
        ticker_snapshot: Ticker快照
        side: 买卖方向
        stop_price: 止损价格
        log_trade: 日志记录函数
    
    Returns:
        订单对象
    """
    order_type = "STOP_MARKET"
    
    if is_operating(order_type_locks, order_type):
        return None
    
    if not ticker_snapshot:
        log_trade("error", "止损单挂单失败：无法获取最新价格")
        return None
    
    last_price = float(ticker_snapshot.last_price)
    
    if side == "SELL" and stop_price >= last_price:
        log_trade("error", f"止损单价格({stop_price})高于或等于当前价({last_price})，不挂单")
        return None
    
    if side == "BUY" and stop_price <= last_price:
        log_trade("error", f"止损单价格({stop_price})低于或等于当前价({last_price})，不挂单")
        return None
    
    params = {
        "symbol": TRADE_SYMBOL,
        "side": side,
        "type": order_type,
        "stopPrice": to_price_1_decimal(stop_price),
        "closePosition": "true",
        "timeInForce": "GTC",
        "quantity": to_qty_3_decimal(TRADE_AMOUNT),
    }
    
    await deduplicate_orders(aster, open_orders, order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, side, log_trade)
    
    lock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, log_trade)
    
    try:
        order = await aster.create_order(params)
        order_type_pending_order_id[order_type] = str(order.order_id)
        log_trade("stop", f"挂止损单: {side} STOP_MARKET @ {params['stopPrice']}")
        return order
    except Exception as e:
        unlock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type)
        raise e


async def market_close(
    aster: Aster,
    open_orders: List[AsterOrder],
    order_type_locks: Dict[str, bool],
    order_type_unlock_timer: Dict[str, Optional[threading.Timer]],
    order_type_pending_order_id: Dict[str, Optional[str]],
    side: str,
    log_trade: Callable[[str, str], None]
):
    """
    市价平仓
    
    Args:
        aster: Aster交易所实例
        open_orders: 未成交订单列表
        order_type_locks: 订单类型锁字典
        order_type_unlock_timer: 订单类型解锁定时器字典
        order_type_pending_order_id: 订单类型待处理订单ID字典
        side: 买卖方向
        log_trade: 日志记录函数
    """
    order_type = "MARKET"
    
    if is_operating(order_type_locks, order_type):
        return
    
    params = {
        "symbol": TRADE_SYMBOL,
        "side": side,
        "type": order_type,
        "quantity": to_qty_3_decimal(TRADE_AMOUNT),
        "reduceOnly": "true",
    }
    
    await deduplicate_orders(aster, open_orders, order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, side, log_trade)
    
    lock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, log_trade)
    
    try:
        order = await aster.create_order(params)
        order_type_pending_order_id[order_type] = str(order.order_id)
        log_trade("close", f"市价平仓: {side}")
    except Exception as e:
        unlock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type)
        raise e


def calc_stop_loss_price(entry_price: float, qty: float, side: str, loss: float) -> float:
    """
    计算止损价格
    
    Args:
        entry_price: 开仓价格
        qty: 数量
        side: 方向 (long/short)
        loss: 止损金额
    
    Returns:
        止损价格
    """
    if side == "long":
        return entry_price - loss / qty
    else:
        return entry_price + loss / abs(qty)


def calc_trailing_activation_price(entry_price: float, qty: float, side: str, profit: float) -> float:
    """
    计算动态止盈激活价格
    
    Args:
        entry_price: 开仓价格
        qty: 数量
        side: 方向 (long/short)
        profit: 激活利润
    
    Returns:
        激活价格
    """
    if side == "long":
        return entry_price + profit / qty
    else:
        return entry_price - profit / abs(qty)


async def place_trailing_stop_order(
    aster: Aster,
    open_orders: List[AsterOrder],
    order_type_locks: Dict[str, bool],
    order_type_unlock_timer: Dict[str, Optional[threading.Timer]],
    order_type_pending_order_id: Dict[str, Optional[str]],
    side: str,
    activation_price: float,
    quantity: float,
    log_trade: Callable[[str, str], None]
) -> Optional[AsterOrder]:
    """
    下动态止盈单
    
    Args:
        aster: Aster交易所实例
        open_orders: 未成交订单列表
        order_type_locks: 订单类型锁字典
        order_type_unlock_timer: 订单类型解锁定时器字典
        order_type_pending_order_id: 订单类型待处理订单ID字典
        side: 买卖方向
        activation_price: 激活价格
        quantity: 数量
        log_trade: 日志记录函数
    
    Returns:
        订单对象
    """
    order_type = "TRAILING_STOP_MARKET"
    
    if is_operating(order_type_locks, order_type):
        return None
    
    params = {
        "symbol": TRADE_SYMBOL,
        "side": side,
        "type": order_type,
        "quantity": to_qty_3_decimal(quantity),
        "reduceOnly": "true",
        "activationPrice": to_price_1_decimal(activation_price),
        "callbackRate": TRAILING_CALLBACK_RATE,
        "timeInForce": "GTC",
    }
    
    await deduplicate_orders(aster, open_orders, order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, side, log_trade)
    
    lock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, log_trade)
    
    try:
        order = await aster.create_order(params)
        order_type_pending_order_id[order_type] = str(order.order_id)
        log_trade("order", f"挂动态止盈单: {side} TRAILING_STOP_MARKET activationPrice={params['activationPrice']} callbackRate={TRAILING_CALLBACK_RATE}")
        return order
    except Exception as e:
        unlock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type)
        raise e


async def place_market_order(
    aster: Aster,
    open_orders: List[AsterOrder],
    order_type_locks: Dict[str, bool],
    order_type_unlock_timer: Dict[str, Optional[threading.Timer]],
    order_type_pending_order_id: Dict[str, Optional[str]],
    side: str,
    amount: float,
    log_trade: Callable[[str, str], None],
    reduce_only: bool = False
) -> Optional[AsterOrder]:
    """
    下市价单
    
    Args:
        aster: Aster交易所实例
        open_orders: 未成交订单列表
        order_type_locks: 订单类型锁字典
        order_type_unlock_timer: 订单类型解锁定时器字典
        order_type_pending_order_id: 订单类型待处理订单ID字典
        side: 买卖方向
        amount: 数量
        log_trade: 日志记录函数
        reduce_only: 是否仅减仓
    
    Returns:
        订单对象
    """
    order_type = "MARKET"
    
    if is_operating(order_type_locks, order_type):
        return None
    
    params = {
        "symbol": TRADE_SYMBOL,
        "side": side,
        "type": order_type,
        "quantity": to_qty_3_decimal(amount),
    }
    
    if reduce_only:
        params["reduceOnly"] = "true"
    
    await deduplicate_orders(aster, open_orders, order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, side, log_trade)
    
    lock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type, log_trade)
    
    try:
        order = await aster.create_order(params)
        order_type_pending_order_id[order_type] = str(order.order_id)
        log_trade("order", f"市价单: {side} @ {amount} reduceOnly: {reduce_only}")
        return order
    except Exception as e:
        unlock_operating(order_type_locks, order_type_unlock_timer, order_type_pending_order_id, order_type)
        raise e 