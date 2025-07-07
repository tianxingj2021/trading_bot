"""
命令行界面 - 套利机器人CLI
"""
import os
import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from bot import ArbBot, TradeLog

console = Console()


def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_orderbook(orderbook_data: dict):
    """打印订单簿信息"""
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
    aster_bid = aster_orderbook['bids'][0][0] if aster_orderbook and aster_orderbook.get('bids') else "-"
    aster_ask = aster_orderbook['asks'][0][0] if aster_orderbook and aster_orderbook.get('asks') else "-"
    aster_bid_qty = aster_orderbook['bids'][0][1] if aster_orderbook and aster_orderbook.get('bids') else "-"
    aster_ask_qty = aster_orderbook['asks'][0][1] if aster_orderbook and aster_orderbook.get('asks') else "-"
    
    table.add_row("Aster", str(aster_bid), str(aster_ask), str(aster_bid_qty), str(aster_ask_qty))
    
    # Bitget数据
    bitget_bid = bitget_orderbook['bids'][0][0] if bitget_orderbook and bitget_orderbook.get('bids') else "-"
    bitget_ask = bitget_orderbook['asks'][0][0] if bitget_orderbook and bitget_orderbook.get('asks') else "-"
    bitget_bid_qty = bitget_orderbook['bids'][0][1] if bitget_orderbook and bitget_orderbook.get('bids') else "-"
    bitget_ask_qty = bitget_orderbook['asks'][0][1] if bitget_orderbook and bitget_orderbook.get('asks') else "-"
    
    table.add_row("Bitget", str(bitget_bid), str(bitget_ask), str(bitget_bid_qty), str(bitget_ask_qty))
    
    console.print(table)
    
    # 价差信息
    diff_info = f"Bitget买一-Aster卖一: {diff1:.2f if diff1 else '-'} USDT    Aster买一-Bitget卖一: {diff2:.2f if diff2 else '-'} USDT"
    console.print(diff_info, style="yellow")


def print_stats(stats):
    """打印统计信息"""
    table = Table(title="统计信息")
    table.add_column("累计交易次数", style="green", justify="center")
    table.add_column("累计交易金额", style="green", justify="center")
    table.add_column("累计收益(估算)USDT", style="green", justify="center")
    
    table.add_row(
        str(stats.total_trades),
        str(stats.total_amount),
        f"{stats.total_profit:.2f}"
    )
    
    console.print(table)


def print_trade_log(log: TradeLog):
    """打印交易日志"""
    color = "white"
    if log.type == "open":
        color = "green"
    elif log.type == "close":
        color = "blue"
    elif log.type == "error":
        color = "red"
    
    console.print(f"[{log.time}] [{log.type}] {log.detail}", style=color)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """专业双平台套利机器人 CLI"""
    pass


@cli.command()
def start():
    """启动套利机器人，实时显示行情、价差、交易记录和统计"""
    clear_screen()
    
    last_orderbook = {}
    bot = ArbBot()
    last_stats = bot.get_stats()
    last_log_len = 0
    logs = bot.get_logs()
    
    console.print("机器人启动中...", style="yellow")
    
    def render():
        """渲染界面"""
        clear_screen()
        
        # 创建布局
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=15)
        )
        
        # 头部
        header = Panel(
            Text("Bitget-Aster 套利机器人", style="bold cyan"),
            style="cyan"
        )
        layout["header"].update(header)
        
        # 主要信息
        if last_orderbook.get("asterOrderbook") and last_orderbook.get("bitgetOrderbook"):
            orderbook_content = f"""
Bitget买一-Aster卖一: {last_orderbook.get('diff1', 0):.2f} USDT
Aster买一-Bitget卖一: {last_orderbook.get('diff2', 0):.2f} USDT
"""
        else:
            orderbook_content = "等待 orderbook 数据..."
        
        main_content = f"""
{orderbook_content}

累计交易次数: {last_stats.total_trades}
累计交易金额: {last_stats.total_amount}
累计收益: {last_stats.total_profit:.2f} USDT
"""
        
        main_panel = Panel(main_content, title="套利信息", style="green")
        layout["main"].update(main_panel)
        
        # 底部日志
        log_content = "最近交易/异常记录：\n"
        for log in logs[-10:]:
            log_content += f"[{log.time}] [{log.type}] {log.detail}\n"
        
        log_content += "\n按 Ctrl+C 退出"
        
        footer_panel = Panel(log_content, title="日志", style="blue")
        layout["footer"].update(footer_panel)
        
        # 显示
        console.print(layout)
    
    # 启动主循环
    async def run_bot():
        await bot.start_arb_bot({
            'onOrderbook': lambda ob: setattr(bot, 'last_orderbook', ob),
            'onTrade': lambda: None,
            'onLog': lambda: None,
            'onStats': lambda s: setattr(bot, 'last_stats', s)
        })
    
    # 定时刷新
    async def refresh_loop():
        while True:
            nonlocal last_orderbook, last_stats, logs
            
            if hasattr(bot, 'last_orderbook'):
                last_orderbook = bot.last_orderbook
            
            if hasattr(bot, 'last_stats'):
                last_stats = bot.last_stats
            
            logs = bot.get_logs()
            
            if len(logs) != last_log_len:
                render()
                last_log_len = len(logs)
            
            await asyncio.sleep(2)
    
    # 启动任务
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(run_bot())
        loop.run_until_complete(refresh_loop())
    except KeyboardInterrupt:
        console.print("\n已终止套利机器人。", style="red")


@cli.command()
def log():
    """查看全部历史下单/平仓/异常记录"""
    bot = ArbBot()
    logs = bot.get_logs()
    
    if not logs:
        console.print("暂无记录", style="gray")
        return
    
    for log_item in logs:
        print_trade_log(log_item)


@cli.command()
def reset():
    """重置统计数据"""
    bot = ArbBot()
    bot.reset_stats()
    console.print("统计数据已重置。", style="yellow")


if __name__ == "__main__":
    cli() 