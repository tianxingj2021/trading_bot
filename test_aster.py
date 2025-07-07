# #!/usr/bin/env python3
# """
# Aster交易所功能测试脚本
# 测试Aster API的基本功能，包括行情获取、下单、查询订单等
# """

# import asyncio
# import os
# import sys
# from dotenv import load_dotenv
# from rich.console import Console
# from rich.table import Table
# from rich.panel import Panel
# from rich.progress import Progress, SpinnerColumn, TextColumn
# from rich import print as rprint

# # 添加项目根目录到Python路径
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# from exchanges.aster import Aster
# from utils.log import console
# from config import ASTER_API_KEY, ASTER_API_SECRET

# # 加载环境变量
# load_dotenv()

# console = console

# class AsterTester:
#     """Aster交易所测试类"""
    
#     def __init__(self):
#         """初始化测试器"""
#         self.exchange = None
#         self.test_results = []
        
#     def setup_exchange(self):
#         """设置交易所连接"""
#         try:
#             console.print("[yellow]正在初始化Aster交易所连接...[/yellow]")
#             # 创建Aster交易所实例
#             self.exchange = Aster(
#                 api_key=ASTER_API_KEY,
#                 api_secret=ASTER_API_SECRET
#             )
#             console.print("[green]✓ Aster交易所连接成功[/green]")
#             return True
#         except Exception as e:
#             console.print(f"[red]✗ Aster交易所连接失败: {e}[/red]")
#             return False
    
#     async def test_account_info(self):
#         """测试获取账户资产和持仓信息"""
#         try:
#             console.print("\n[blue]测试获取账户资产和持仓信息...[/blue]")
#             account = self.exchange.get_account()
#             if account:
#                 table = Table(title="资产信息")
#                 table.add_column("资产", style="cyan")
#                 table.add_column("余额", style="green")
#                 table.add_column("可用", style="yellow")
#                 for asset in account.assets[:10]:
#                     table.add_row(asset.asset, asset.wallet_balance, asset.available_balance)
#                 console.print(table)
#                 pos_table = Table(title="持仓信息")
#                 pos_table.add_column("合约", style="cyan")
#                 pos_table.add_column("持仓量", style="green")
#                 pos_table.add_column("开仓价", style="yellow")
#                 pos_table.add_column("未实现盈亏", style="magenta")
#                 for pos in account.positions[:10]:
#                     pos_table.add_row(pos.symbol, pos.position_amt, pos.entry_price, pos.unrealized_profit)
#                 console.print(pos_table)
#                 self.test_results.append(("获取账户资产和持仓", "成功", len(account.assets)))
#             else:
#                 console.print("[red]✗ 获取账户信息失败[/red]")
#                 self.test_results.append(("获取账户资产和持仓", "失败", 0))
#         except Exception as e:
#             console.print(f"[red]✗ 测试账户信息失败: {e}[/red]")
#             self.test_results.append(("获取账户资产和持仓", f"异常: {e}", 0))
    
#     async def test_ticker(self):
#         """测试获取行情信息"""
#         try:
#             console.print("\n[blue]测试获取行情信息...[/blue]")
#             ticker = self.exchange.get_ticker('BTCUSDT')
#             if ticker:
#                 table = Table(title="BTCUSDT 行情信息")
#                 table.add_column("字段", style="cyan")
#                 table.add_column("值", style="green")
#                 table.add_row("交易对", ticker.symbol)
#                 table.add_row("最新价格", ticker.last_price)
#                 table.add_row("24h最高", ticker.high_price)
#                 table.add_row("24h最低", ticker.low_price)
#                 table.add_row("24h成交量", ticker.volume)
#                 table.add_row("24h成交额", ticker.quote_volume)
#                 table.add_row("价格变化", ticker.price_change or '-')
#                 table.add_row("价格变化率", ticker.price_change_percent or '-')
#                 console.print(table)
#                 self.test_results.append(("获取行情信息", "成功", 1))
#             else:
#                 console.print("[red]✗ 获取行情信息失败[/red]")
#                 self.test_results.append(("获取行情信息", "失败", 0))
#         except Exception as e:
#             console.print(f"[red]✗ 测试行情信息失败: {e}[/red]")
#             self.test_results.append(("获取行情信息", f"异常: {e}", 0))
    
#     async def test_orderbook(self):
#         """测试获取订单簿"""
#         try:
#             console.print("\n[blue]测试获取订单簿...[/blue]")
#             orderbook = self.exchange.get_depth('BTCUSDT', limit=5)
#             if orderbook and orderbook.bids and orderbook.asks:
#                 table = Table(title="BTCUSDT 订单簿 (前5档)")
#                 table.add_column("类型", style="cyan")
#                 table.add_column("价格", style="green")
#                 table.add_column("数量", style="yellow")
#                 for bid in orderbook.bids:
#                     table.add_row("买单", bid.price, bid.quantity)
#                 for ask in orderbook.asks:
#                     table.add_row("卖单", ask.price, ask.quantity)
#                 console.print(table)
#                 self.test_results.append(("获取订单簿", "成功", len(orderbook.bids) + len(orderbook.asks)))
#             else:
#                 console.print("[red]✗ 获取订单簿失败[/red]")
#                 self.test_results.append(("获取订单簿", "失败", 0))
#         except Exception as e:
#             console.print(f"[red]✗ 测试订单簿失败: {e}[/red]")
#             self.test_results.append(("获取订单簿", f"异常: {e}", 0))
    
#     async def test_balance(self):
#         """测试获取账户余额"""
#         try:
#             console.print("\n[blue]测试获取账户余额...[/blue]")
#             account = self.exchange.get_account()
#             if account and account.assets:
#                 table = Table(title="账户余额")
#                 table.add_column("资产", style="cyan")
#                 table.add_column("余额", style="green")
#                 table.add_column("可用", style="yellow")
#                 for asset in account.assets:
#                     table.add_row(asset.asset, asset.wallet_balance, asset.available_balance)
#                 console.print(table)
#                 self.test_results.append(("获取账户余额", "成功", len(account.assets)))
#             else:
#                 console.print("[red]✗ 获取账户余额失败[/red]")
#                 self.test_results.append(("获取账户余额", "失败", 0))
#         except Exception as e:
#             console.print(f"[red]✗ 测试账户余额失败: {e}[/red]")
#             self.test_results.append(("获取账户余额", f"异常: {e}", 0))
    
#     async def test_leverage_setting(self):
#         """测试杠杆设置"""
#         try:
#             console.print("\n[blue]测试杠杆设置...[/blue]")
#             # 设置杠杆为10倍
#             result = self.exchange.set_leverage('BTCUSDT', 40)
#             if result and 'leverage' in result:
#                 console.print(f"[green]✓ 杠杆设置成功: {result['leverage']}倍[/green]")
#                 self.test_results.append(("杠杆设置", "成功", result['leverage']))
#             else:
#                 console.print("[red]✗ 杠杆设置失败[/red]")
#                 self.test_results.append(("杠杆设置", "失败", 0))
#         except Exception as e:
#             console.print(f"[yellow]⚠ 杠杆设置异常: {e}（可能已设置过或权限不足）[/yellow]")
#             self.test_results.append(("杠杆设置", f"异常: {e}", 0))
    
#     async def test_place_order(self):
#         """测试自动化下单功能（按USDT金额自动换算数量和精度）"""
#         try:
#             console.print("\n[blue]测试自动化下单功能...[/blue]")
#             ticker = self.exchange.get_ticker('BTCUSDT')
#             if ticker and float(ticker.last_price) > 0:
#                 current_price = float(ticker.last_price)
#                 usdt_amount = 110  # 使用110 USDT测试
                
#                 # 测试1: 市价单自动下单
#                 try:
#                     console.print(f"[yellow]测试市价单自动买入 {usdt_amount} USDT的BTC...[/yellow]")
#                     order = self.exchange.create_order_auto(
#                         symbol='BTCUSDT',
#                         side='BUY',
#                         usdt_amount=usdt_amount,
#                         order_type='MARKET'
#                     )
#                     console.print(f"[green]✓ 市价单自动买入成功，订单ID: {order.order_id}[/green]")
#                     self.test_results.append(("市价单自动买入", "成功", 1))
#                 except Exception as e:
#                     console.print(f"[yellow]⚠ 市价单自动买入异常: {e}[/yellow]")
#                     self.test_results.append(("市价单自动买入", f"异常: {e}", 0))
                
#                 # 测试2: 限价单自动下单（用较低价格防止成交）
#                 try:
#                     limit_price = current_price * 0.8  # 80%价格
#                     console.print(f"[yellow]测试限价单自动买入 {usdt_amount} USDT的BTC，价格: {limit_price:.1f}...[/yellow]")
#                     order = self.exchange.create_order_auto(
#                         symbol='BTCUSDT',
#                         side='BUY',
#                         usdt_amount=usdt_amount,
#                         order_type='LIMIT',
#                         price=limit_price
#                     )
#                     console.print(f"[green]✓ 限价单自动买入成功，订单ID: {order.order_id}[/green]")
#                     self.test_results.append(("限价单自动买入", "成功", 1))
#                 except Exception as e:
#                     console.print(f"[yellow]⚠ 限价单自动买入异常: {e}[/yellow]")
#                     self.test_results.append(("限价单自动买入", f"异常: {e}", 0))
                
#             else:
#                 console.print("[red]✗ 无法获取当前价格[/red]")
#                 self.test_results.append(("自动化下单", "失败", 0))
#         except Exception as e:
#             console.print(f"[red]✗ 测试自动化下单功能失败: {e}[/red]")
#             self.test_results.append(("自动化下单", f"异常: {e}", 0))
    
#     async def test_orders(self):
#         """测试获取未成交订单"""
#         try:
#             console.print("\n[blue]测试获取未成交订单...[/blue]")
#             orders = self.exchange.get_open_orders('BTCUSDT')
#             if orders is not None:
#                 if orders:
#                     table = Table(title="未成交订单 (前5个)")
#                     table.add_column("订单ID", style="cyan")
#                     table.add_column("交易对", style="green")
#                     table.add_column("类型", style="yellow")
#                     table.add_column("价格", style="magenta")
#                     table.add_column("数量", style="blue")
#                     table.add_column("状态", style="red")
#                     for order in orders[:5]:
#                         table.add_row(
#                             str(order.order_id),
#                             order.symbol,
#                             order.type,
#                             order.price,
#                             order.quantity,
#                             order.status
#                         )
#                     console.print(table)
#                     self.test_results.append(("获取未成交订单", "成功", len(orders)))
#                 else:
#                     console.print("[yellow]⚠ 没有未成交订单[/yellow]")
#                     self.test_results.append(("获取未成交订单", "成功(空)", 0))
#             else:
#                 console.print("[red]✗ 获取未成交订单失败[/red]")
#                 self.test_results.append(("获取未成交订单", "失败", 0))
#         except Exception as e:
#             console.print(f"[red]✗ 测试未成交订单失败: {e}[/red]")
#             self.test_results.append(("获取未成交订单", f"异常: {e}", 0))
    
#     def print_summary(self):
#         """打印测试总结"""
#         console.print("\n" + "="*60)
#         console.print("[bold blue]测试总结[/bold blue]")
#         console.print("="*60)
        
#         table = Table()
#         table.add_column("测试项目", style="cyan")
#         table.add_column("结果", style="green")
#         table.add_column("详情", style="yellow")
        
#         success_count = 0
#         total_count = len(self.test_results)
        
#         for test_name, result, detail in self.test_results:
#             if "成功" in result:
#                 success_count += 1
#                 status = "[green]✓[/green]"
#             else:
#                 status = "[red]✗[/red]"
            
#             table.add_row(f"{status} {test_name}", result, str(detail))
        
#         console.print(table)
        
#         success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
#         console.print(f"\n[bold]测试结果: {success_count}/{total_count} 通过 ({success_rate:.1f}%)[/bold]")
        
#         if success_rate >= 80:
#             console.print("[bold green]🎉 测试通过！Aster交易所功能正常[/bold green]")
#         elif success_rate >= 60:
#             console.print("[bold yellow]⚠ 测试部分通过，请检查失败的项[/bold yellow]")
#         else:
#             console.print("[bold red]❌ 测试失败较多，请检查配置和网络连接[/bold red]")
    
#     async def run_all_tests(self):
#         """运行所有测试"""
#         console.print(Panel.fit(
#             "[bold blue]Aster交易所功能测试[/bold blue]\n"
#             "测试Aster API的基本功能",
#             border_style="blue"
#         ))
        
#         # 检查环境变量
#         if not ASTER_API_KEY or not ASTER_API_SECRET:
#             console.print("[red]❌ 错误: 未设置ASTER_API_KEY或ASTER_SECRET环境变量[/red]")
#             console.print("请复制env.example为.env并填写正确的API密钥")
#             return False
        
#         # 设置交易所连接
#         if not self.setup_exchange():
#             return False
        
#         # 运行各项测试
#         tests = [
#             self.test_account_info,
#             self.test_ticker,
#             self.test_orderbook,
#             self.test_balance,
#             self.test_leverage_setting,
#             self.test_place_order,
#             self.test_orders
#         ]
        
#         with Progress(
#             SpinnerColumn(),
#             TextColumn("[progress.description]{task.description}"),
#             console=console
#         ) as progress:
#             task = progress.add_task("运行测试中...", total=len(tests))
            
#             for test_func in tests:
#                 progress.update(task, description=f"正在执行: {test_func.__name__}")
#                 await test_func()
#                 progress.advance(task)
        
#         # 打印总结
#         self.print_summary()
        
#         return True

# async def main():
#     """主函数"""
#     tester = AsterTester()
#     await tester.run_all_tests()

# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         console.print("\n[yellow]测试被用户中断[/yellow]")
#     except Exception as e:
#         console.print(f"\n[red]测试过程中发生错误: {e}[/red]")

#!/usr/bin/env python3
"""
Aster交易所最大杠杆测试脚本
"""
from exchanges.aster import Aster
from config import ASTER_API_KEY, ASTER_API_SECRET

if __name__ == "__main__":
    aster = Aster(api_key=ASTER_API_KEY, api_secret=ASTER_API_SECRET)
    symbol = input("请输入要测试的交易对（如DOGEUSDT）: ").strip().upper()
    try:
        max_lev = aster.get_max_leverage(symbol)
        print(f"{symbol} 最大杠杆: {max_lev}")
    except Exception as e:
        print(f"查询失败: {e}") 