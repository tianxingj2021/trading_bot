#!/usr/bin/env python3
"""
aster-bot Python版本启动脚本
"""
import sys
import argparse
from rich.console import Console
from rich.panel import Panel

console = Console()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="aster-bot Python版本")
    parser.add_argument("strategy", choices=["trend", "maker", "arb"], 
                       help="选择策略: trend(趋势策略), maker(做市策略), arb(套利策略)")
    parser.add_argument("--symbol", default="BTCUSDT", help="交易对符号")
    parser.add_argument("--amount", type=float, default=0.001, help="交易数量")
    parser.add_argument("--test", action="store_true", help="运行测试模式")
    
    args = parser.parse_args()
    
    # 显示启动信息
    console.print(Panel.fit(
        "[bold cyan]aster-bot Python版本[/bold cyan]\n"
        f"策略: [green]{args.strategy}[/green]\n"
        f"交易对: [yellow]{args.symbol}[/yellow]\n"
        f"数量: [yellow]{args.amount}[/yellow]",
        title="启动信息"
    ))
    
    try:
        if args.strategy == "trend":
            console.print("启动趋势策略...", style="green")
            from trend_v2 import main as trend_main
            import asyncio
            asyncio.run(trend_main())
        
        elif args.strategy == "maker":
            console.print("启动做市策略...", style="green")
            from maker import main as maker_main
            import asyncio
            asyncio.run(maker_main())
        
        elif args.strategy == "arb":
            console.print("启动套利策略...", style="green")
            from bot import main as arb_main
            import asyncio
            asyncio.run(arb_main())
    
    except KeyboardInterrupt:
        console.print("\n[red]用户中断，正在退出...[/red]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]启动失败: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main() 