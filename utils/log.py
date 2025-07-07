"""
日志工具
"""
import os
from datetime import datetime
from typing import List, Dict, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from exchanges.aster import AsterTicker, AsterDepth, AsterOrder

console = Console()


class TradeLogItem:
    """交易日志项"""
    
    def __init__(self, log_type: str, detail: str):
        self.time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.type = log_type
        self.detail = detail


def log_trade(trade_log: List[TradeLogItem], log_type: str, detail: str):
    """
    记录交易日志
    
    Args:
        trade_log: 交易日志列表
        log_type: 日志类型
        detail: 日志详情
    """
    trade_log.append(TradeLogItem(log_type, detail))
    if len(trade_log) > 1000:
        trade_log.pop(0)


def print_status(status_data: Dict):
    """
    打印状态信息
    
    Args:
        status_data: 状态数据字典
    """
    # 清屏
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # 创建布局
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=15)
    )
    
    # 头部
    header = Panel(
        Text("趋势策略机器人", style="bold cyan"),
        style="cyan"
    )
    layout["header"].update(header)
    
    # 主要信息
    ticker = status_data.get("ticker")
    ob = status_data.get("ob")
    sma = status_data.get("sma")
    trend = status_data.get("trend", "无信号")
    pos = status_data.get("pos", {})
    pnl = status_data.get("pnl", 0)
    unrealized = status_data.get("unrealized", 0)
    total_profit = status_data.get("totalProfit", 0)
    total_trades = status_data.get("totalTrades", 0)
    open_orders = status_data.get("openOrders", [])
    
    # 价格信息
    price_info = f"最新价格: {ticker.last_price if ticker else '-'} | SMA30: {sma:.2f if sma else '-'}"
    
    # 盘口信息
    depth_info = ""
    if ob and ob.bids and ob.asks:
        depth_info = f"盘口 买一: {ob.bids[0].price} 卖一: {ob.asks[0].price}"
    
    # 趋势信息
    trend_info = f"当前趋势: {trend}"
    
    # 持仓信息
    position_info = ""
    if pos and abs(pos.get("positionAmt", 0)) > 0.00001:
        direction = "多" if pos["positionAmt"] > 0 else "空"
        position_info = f"持仓: {direction} 开仓价: {pos['entryPrice']} 当前浮盈亏: {pnl:.4f} USDT 账户浮盈亏: {unrealized:.4f}"
    else:
        position_info = "当前无持仓"
    
    # 统计信息
    stats_info = f"累计交易次数: {total_trades}  累计收益: {total_profit:.4f} USDT"
    
    main_content = f"""
{price_info}
{depth_info}
{trend_info}
{position_info}
{stats_info}
"""
    
    main_panel = Panel(main_content, title="状态信息", style="green")
    layout["main"].update(main_panel)
    
    # 底部日志
    trade_log = status_data.get("tradeLog", [])
    log_content = "最近交易/挂单记录：\n"
    
    for log_item in trade_log[-10:]:
        color = "white"
        if log_item.type == "open":
            color = "green"
        elif log_item.type == "close":
            color = "blue"
        elif log_item.type == "stop":
            color = "red"
        elif log_item.type == "order":
            color = "yellow"
        elif log_item.type == "error":
            color = "red"
        
        log_content += f"[{log_item.time}] [{log_item.type}] {log_item.detail}\n"
    
    # 挂单信息
    if open_orders:
        log_content += "\n当前挂单：\n"
        for order in open_orders:
            log_content += f"订单ID: {order.order_id} {order.side} {order.type} @ {order.price} 数量: {order.orig_qty} 状态: {order.status}\n"
    else:
        log_content += "\n无挂单"
    
    log_content += "\n按 Ctrl+C 退出"
    
    footer_panel = Panel(log_content, title="日志", style="blue")
    layout["footer"].update(footer_panel)
    
    # 显示
    console.print(layout)


def print_orderbook(orderbook_data: Dict):
    """
    打印订单簿信息
    
    Args:
        orderbook_data: 订单簿数据
    """
    aster_orderbook = orderbook_data.get("asterOrderbook")
    bitget_orderbook = orderbook_data.get("bitgetOrderbook")
    diff1 = orderbook_data.get("diff1")
    diff2 = orderbook_data.get("diff2")
    
    table = Table(title="订单簿信息")
    table.add_column("平台", style="cyan", justify="center")
    table.add_column("买一价", style="green", justify="right")
    table.add_column("卖一价", style="red", justify="right")
    table.add_column("买一量", style="green", justify="right")
    table.add_column("卖一量", style="red", justify="right")
    
    # Aster数据
    aster_bid = aster_orderbook.bids[0].price if aster_orderbook and aster_orderbook.bids else "-"
    aster_ask = aster_orderbook.asks[0].price if aster_orderbook and aster_orderbook.asks else "-"
    aster_bid_qty = aster_orderbook.bids[0].quantity if aster_orderbook and aster_orderbook.bids else "-"
    aster_ask_qty = aster_orderbook.asks[0].quantity if aster_orderbook and aster_orderbook.asks else "-"
    
    table.add_row("Aster", str(aster_bid), str(aster_ask), str(aster_bid_qty), str(aster_ask_qty))
    
    # Bitget数据
    bitget_bid = bitget_orderbook.bids[0].price if bitget_orderbook and bitget_orderbook.bids else "-"
    bitget_ask = bitget_orderbook.asks[0].price if bitget_orderbook and bitget_orderbook.asks else "-"
    bitget_bid_qty = bitget_orderbook.bids[0].quantity if bitget_orderbook and bitget_orderbook.bids else "-"
    bitget_ask_qty = bitget_orderbook.asks[0].quantity if bitget_orderbook and bitget_orderbook.asks else "-"
    
    table.add_row("Bitget", str(bitget_bid), str(bitget_ask), str(bitget_bid_qty), str(bitget_ask_qty))
    
    console.print(table)
    
    # 价差信息
    diff_info = f"Bitget买一-Aster卖一: {diff1:.2f if diff1 else '-'} USDT    Aster买一-Bitget卖一: {diff2:.2f if diff2 else '-'} USDT"
    console.print(diff_info, style="yellow")


def print_stats(stats: Dict):
    """
    打印统计信息
    
    Args:
        stats: 统计数据
    """
    table = Table(title="统计信息")
    table.add_column("累计交易次数", style="green", justify="center")
    table.add_column("累计交易金额", style="green", justify="center")
    table.add_column("累计收益(估算)USDT", style="green", justify="center")
    
    table.add_row(
        str(stats.get("totalTrades", 0)),
        str(stats.get("totalAmount", 0)),
        f"{stats.get('totalProfit', 0):.2f}"
    )
    
    console.print(table)


def print_trade_log(log: TradeLogItem):
    """
    打印交易日志
    
    Args:
        log: 交易日志项
    """
    color = "white"
    if log.type == "open":
        color = "green"
    elif log.type == "close":
        color = "blue"
    elif log.type == "error":
        color = "red"
    
    console.print(f"[{log.time}] [{log.type}] {log.detail}", style=color) 