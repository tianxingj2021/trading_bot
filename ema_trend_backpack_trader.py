#!/usr/bin/env python3
"""
EMA趋势策略Backpack实盘交易程序
使用EMA趋势策略在Backpack交易所进行自动交易
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.ema_trend_strategy import EMATrendStrategy
from utils.order_adapter import get_exchange_instance
import time
import signal
import json
from datetime import datetime, timedelta, timezone
import argparse
import ntplib
import subprocess
import traceback
from utils.helper import adapt_symbol
from dateutil import parser as dtparser

class EMATrendBackpackTrader:
    def __init__(self, config_file="backpack_trader_config.json"):
        """
        初始化交易程序
        :param config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self.load_config()
        self.strategy = EMATrendStrategy(
            atr_period=self.config.get('atr_period', 14),
            atr_mult=self.config.get('atr_mult', 2),
            risk_reward_ratio=self.config.get('risk_reward_ratio', 2)
        )
        self.running = False
        self.exchange = 'backpack'
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("EMA趋势策略Backpack实盘交易程序初始化完成")
        print(f"配置: {self.config}")
        
        # 启动时检查时间同步
        self.log_message("启动时检查时间同步...")
        self.check_local_time_offset(threshold_sec=3)  # 降低阈值到3秒，更敏感

    def load_config(self):
        """加载配置文件"""
        default_config = {
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "leverage": 50,
            "risk_pct": 0.05,
            "check_interval": 30,
            "atr_period": 14,
            "atr_mult": 2,
            "risk_reward_ratio": 2,
            "max_positions": 3,
            "enable_logging": True,
            "log_file": "backpack_trader.log"
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                return default_config
        else:
            # 创建默认配置文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            print(f"已创建默认配置文件: {self.config_file}")
            return default_config

    def signal_handler(self, signum, frame):
        """信号处理函数"""
        print(f"\n收到信号 {signum}，正在停止交易程序...")
        self.running = False

    def log_message(self, message):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        
        if self.config.get('enable_logging', True):
            log_file = self.config.get('log_file', 'backpack_trader.log')
            try:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(log_msg + '\n')
            except Exception as e:
                print(f"写入日志失败: {e}")

    def check_account_status(self):
        """检查账户状态"""
        try:
            # 简化账户检查，避免API签名问题
            # 只检查余额，不检查持仓
            from utils.account_adapter import get_account_balance
            balance = get_account_balance(self.exchange, 'USDC')
            self.log_message(f"账户余额: {balance:.2f} USDC")
            
            # 检查本地持仓记录
            if hasattr(self.strategy, 'active_positions') and self.strategy.active_positions:
                self.log_message(f"本地持仓记录: {len(self.strategy.active_positions)}个")
                for symbol, pos in self.strategy.active_positions.items():
                    self.log_message(f"  {symbol}: {pos['direction']} @ {pos['entry_price']:.2f}")
            else:
                self.log_message("当前无本地持仓记录")
                
            return True
            
        except Exception as e:
            self.log_message(f"检查账户状态失败: {e}")
            return True  # 出错时继续运行

    def execute_strategy_for_symbol(self, symbol, positions=None):
        """执行策略，优先用传入的positions缓存"""
        try:
            return self.strategy.execute_strategy(self.exchange, symbol, self.config.get('leverage', 50), self.config.get('risk_pct', 0.05), auto_trade=True, positions=positions)
        except Exception as e:
            return {'action': 'error', 'reason': str(e)}

    def check_position_limits(self, positions=None):
        """检查持仓限制，优先用传入的positions缓存"""
        try:
            active_count = len(self.strategy.active_positions)
            max_positions = self.config.get('max_positions', 3)
            if positions is None:
                positions = self.last_positions if hasattr(self, 'last_positions') else []
            
            # 详细记录本地持仓信息
            self.log_message(f"本地持仓记录: {self.strategy.active_positions}")
            
            # 计算实际持仓数量
            real_active_count = 0
            if positions:
                for pos in positions:
                    symbol = getattr(pos, 'symbol', None) or pos.get('symbol', '')
                    net_qty = float(getattr(pos, 'netQuantity', 0) or pos.get('netQuantity', 0) or 0)
                    if net_qty != 0:
                        real_active_count += 1
                        self.log_message(f"实际持仓: {symbol} = {net_qty}")
            
            self.log_message(f"本地持仓数: {active_count}, 实际持仓数: {real_active_count}, 最大允许: {max_positions}")
            
            # 如果本地记录与实际不符，清空本地记录
            if active_count > 0 and real_active_count == 0:
                self.log_message("检测到本地记录与实际不符，清空本地持仓记录")
                self.strategy.active_positions.clear()
                active_count = 0
            
            # 检查是否超过限制
            if active_count >= max_positions:
                self.log_message(f"本地持仓数已达上限: {active_count}/{max_positions}")
                return False
            
            if real_active_count >= max_positions:
                self.log_message(f"实际持仓数已达上限: {real_active_count}/{max_positions}")
                return False
            
            self.log_message(f"持仓检查通过，可以开仓")
            return True
        except Exception as e:
            self.log_message(f"检查持仓限制失败: {e}")
            return False

    def run(self):
        """运行交易循环"""
        self.running = True
        check_interval = self.config.get('check_interval', 30)
        symbols = self.config.get('symbols', ['BTCUSDT'])
        last_balance_check = 0
        balance_check_interval = 60
        last_time_check = 0
        time_check_interval = 300  # 每5分钟检查一次时间同步
        self.last_positions = None  # 缓存持仓
        self.log_message(f"开始交易循环，策略检查间隔: {check_interval}秒")
        self.log_message(f"余额查询间隔: {balance_check_interval}秒")
        self.log_message(f"时间同步检查间隔: {time_check_interval}秒")
        self.log_message(f"交易对: {symbols}")
        cycle_count = 0
        while self.running:
            try:
                cycle_count += 1
                self.log_message(f"=== 交易循环 #{cycle_count} ===")
                
                # 时间同步检查
                current_time = time.time()
                if current_time - last_time_check >= time_check_interval:
                    self.log_message("执行时间同步检查...")
                    self.check_local_time_offset()
                    last_time_check = current_time
                
                # 余额查询
                if current_time - last_balance_check >= balance_check_interval:
                    self.log_message("执行余额查询...")
                    self.check_account_status()
                    last_balance_check = current_time
                else:
                    remaining_time = balance_check_interval - (current_time - last_balance_check)
                    self.log_message(f"距离下次余额查询还有 {remaining_time:.0f} 秒")
                # 只请求一次持仓API
                try:
                    ex = get_exchange_instance(self.exchange)
                    positions = ex.get_positions()
                    self.last_positions = positions
                    self.log_message(f"实际持仓数: {len(positions)}")
                except Exception as e:
                    self.log_message(f"获取持仓信息失败: {e}")
                    positions = []
                    self.last_positions = []
                # 检查持仓限制（用缓存）
                if not self.check_position_limits(positions):
                    self.log_message("达到最大持仓数量，跳过开仓")
                    time.sleep(check_interval)
                    continue
                # 执行策略（用缓存）
                for symbol in symbols:
                    self.log_message(f"执行策略: {symbol}")
                    result = self.execute_strategy_for_symbol(symbol, positions)
                    action = result.get('action', 'unknown')
                    reason = result.get('reason', '')
                    if reason:
                        self.log_message(f"策略结果: {action} - {reason}")
                    else:
                        self.log_message(f"策略结果: {action} | 详情: {result}")
                self.log_message(f"等待{check_interval}秒后进行下次检查...")
                time.sleep(check_interval)
            except KeyboardInterrupt:
                self.log_message("收到停止信号，正在退出...")
                break
            except Exception as e:
                self.log_message(f"交易循环异常: {e}")
                traceback.print_exc()
                time.sleep(check_interval)
        self.log_message("交易循环已停止")

    def run_single_execution(self, symbol):
        """单次执行策略（用于测试）"""
        self.log_message(f"单次执行策略: {symbol}")
        
        # 检查账户状态
        self.check_account_status()
        
        # 执行策略
        result = self.execute_strategy_for_symbol(symbol)
        
        self.log_message(f"执行完成: {result}")
        return result

    def show_statistics(self):
        """显示交易统计，优先用持仓历史接口补全所有已平仓订单"""
        try:
            print(f"【调试】当前order_history: {self.strategy.order_history}")
            self.log_message("=== 交易统计 ===")
            # 1. 获取API实际持仓
            try:
                ex = get_exchange_instance(self.exchange)
                positions = ex.get_positions()
            except Exception as e:
                self.log_message(f"获取持仓信息失败: {e}")
                positions = []
            from datetime import datetime, timedelta, timezone
            from utils.helper import adapt_symbol
            # 2. 获取持仓历史（position history）
            try:
                # 支持分页，如需全部历史可循环offset
                pos_history = ex.get_position_history(symbol=None, state='Closed', limit=200, offset=0)
            except Exception as e:
                self.log_message(f"获取持仓历史失败: {e}")
                pos_history = []
            # 3. 遍历order_history，优先用持仓历史补全
            for order in self.strategy.order_history:
                print(f"【调试】循环order: {order}")
                symbol = order['symbol']
                api_symbol = adapt_symbol(symbol, 'backpack')
                try:
                    fills = ex.get_user_trades(symbol=api_symbol, limit=500)
                    print(f"【调试】相关fills（全部）:")
                    for f in fills:
                        print(f"  {f}")
                except Exception as e:
                    print(f"【调试】获取fills失败: {e}")
                # 匹配持仓历史：symbol、方向、开仓时间接近、开仓均价接近、数量相等
                matched = None
                for pos in pos_history:
                    pos_symbol = pos.get('symbol')
                    pos_qty = float(pos.get('quantity', 0))
                    pos_open_time = pos.get('openTime')
                    pos_open_price = float(pos.get('openPrice', 0))
                    pos_side = 'long' if pos_qty > 0 else 'short'
                    # 时间容忍1小时，价格容忍0.5%，数量容忍0.5%
                    try:
                        order_ts = int(datetime.fromisoformat(order['entry_time']).timestamp())
                        pos_ts = int(datetime.fromisoformat(pos_open_time).timestamp()) if pos_open_time else 0
                    except Exception:
                        order_ts = 0
                        pos_ts = 0
                    time_close = abs(order_ts - pos_ts) < 3600
                    price_close = abs(pos_open_price - order['entry_price']) / max(1, order['entry_price']) < 0.005
                    qty_close = abs(abs(pos_qty) - abs(float(order['quantity']))) / max(1, abs(float(order['quantity']))) < 0.005
                    if pos_symbol == api_symbol and pos_side == order['direction'] and time_close and price_close and qty_close:
                        matched = pos
                        break
                if matched:
                    order['close_price'] = float(matched.get('closePrice', 0))
                    order['close_time'] = matched.get('closeTime', order['entry_time'])
                    order['close_type'] = '持仓历史自动补全'
                    order['pnl'] = float(matched.get('realizedPnl', 0))
                    self.strategy.total_pnl += order['pnl']
                    self.log_message(f"持仓历史自动补全平仓订单: {symbol} {order['direction']} @ {order['close_price']}")
                    continue  # 已补全，跳过后续逻辑
                # 若未匹配到，再用成交历史逻辑兜底（优化：累计平仓成交，精确补全）
                try:
                    fills = ex.get_user_trades(symbol=api_symbol, limit=500)
                    # 方向映射
                    open_side = 'Bid' if order['direction'] == 'long' else 'Ask'
                    close_side = 'Ask' if order['direction'] == 'long' else 'Bid'
                    # 【调试】打印当前order和所有fills
                    print(f"【调试】order: {order}")
                    print(f"【调试】相关fills（全部）:")
                    for f in fills:
                        print(f"  {f}")
                    
                    # 时间戳格式统一处理
                    try:
                        # 尝试解析entry_time，支持多种格式
                        if isinstance(order['entry_time'], str):
                            # 如果是字符串，尝试多种解析方式
                            try:
                                entry_dt = dtparser.parse(order['entry_time'])
                            except:
                                # 如果解析失败，可能是毫秒时间戳字符串
                                try:
                                    ts_ms = int(order['entry_time'])
                                    if ts_ms > 1e12:  # 毫秒时间戳
                                        entry_dt = datetime.fromtimestamp(ts_ms / 1000)
                                    else:  # 秒时间戳
                                        entry_dt = datetime.fromtimestamp(ts_ms)
                                except:
                                    print(f"【调试】无法解析entry_time: {order['entry_time']}")
                                    continue
                        elif isinstance(order['entry_time'], (int, float)):
                            # 如果是数字，当作时间戳处理
                            if order['entry_time'] > 1e12:  # 毫秒时间戳
                                entry_dt = datetime.fromtimestamp(order['entry_time'] / 1000)
                            else:  # 秒时间戳
                                entry_dt = datetime.fromtimestamp(order['entry_time'])
                        else:
                            entry_dt = order['entry_time']
                        
                        # 确保entry_dt是UTC时区
                        if entry_dt.tzinfo is None:
                            # 如果没有时区信息，假设是UTC+8，转换为UTC
                            entry_dt = entry_dt - timedelta(hours=8)
                        elif entry_dt.tzinfo.utcoffset(entry_dt) != timedelta(hours=8):
                            # 如果不是UTC+8，转换为UTC
                            entry_dt = entry_dt.astimezone(timezone.utc).replace(tzinfo=None)
                        
                        print(f"【调试】entry_time原始值: {order['entry_time']}")
                        print(f"【调试】entry_time解析后(UTC): {entry_dt}")
                        print(f"【调试】entry_time类型: {type(entry_dt)}")
                    except Exception as e:
                        print(f"【调试】时间解析失败: {e}")
                        continue
                    
                    # 解析所有成交时间，确保都是UTC时区
                    fills_with_dt = []
                    for f in fills:
                        try:
                            fill_dt = dtparser.parse(f['timestamp'])
                            # 确保fill_dt是UTC时区
                            if fill_dt.tzinfo is None:
                                # 如果没有时区信息，假设是UTC
                                pass
                            else:
                                # 转换为UTC
                                fill_dt = fill_dt.astimezone(timezone.utc).replace(tzinfo=None)
                            fills_with_dt.append((fill_dt, f))
                        except Exception as e:
                            print(f"【调试】成交时间解析失败: {e}")
                            continue
                    
                    # 按时间排序
                    fills_with_dt.sort(key=lambda x: x[0])
                    
                    if fills_with_dt:
                        earliest_fill = fills_with_dt[0][0]
                        latest_fill = fills_with_dt[-1][0]
                        print(f"【调试】成交时间范围(UTC): {earliest_fill} 到 {latest_fill}")
                        print(f"【调试】开仓时间(UTC): {entry_dt}")
                        
                        # 时间比较
                        if entry_dt > latest_fill:
                            print(f"【调试】时间比较: 开仓时间 > 最新成交时间")
                        elif entry_dt < earliest_fill:
                            print(f"【调试】时间比较: 开仓时间 < 最早成交时间")
                        else:
                            print(f"【调试】时间比较: 开仓时间在成交时间范围内")
                        
                        # 找到开仓成交（方向一致，时间最接近entry_time，数量相等）
                        open_fills = []
                        for fill_dt, f in fills_with_dt:
                            if f.get('side') == open_side:
                                # 放宽时间匹配条件：开仓成交时间在entry_time前后1小时内
                                time_diff = abs((fill_dt - entry_dt).total_seconds())
                                if time_diff <= 3600:  # 1小时内的成交
                                    open_fills.append((fill_dt, f))
                        
                        # 找到平仓成交（方向相反，时间在开仓之后，累计数量等于开仓数量）
                        close_fills = []
                        cum_qty = 0
                        target_qty = float(order['quantity'])
                        
                        # 先找到开仓成交的时间范围
                        if open_fills:
                            open_start = min(fill_dt for fill_dt, _ in open_fills)
                            open_end = max(fill_dt for fill_dt, _ in open_fills)
                            
                            # 在开仓时间之后找平仓成交
                            for fill_dt, f in fills_with_dt:
                                if (f.get('side') == close_side and 
                                    fill_dt > open_end and 
                                    cum_qty < target_qty + 1e-8):  # 允许极小误差
                                    close_fills.append((fill_dt, f))
                                    cum_qty += float(f['quantity'])
                                    print(f"【调试】选中平仓成交: {f['timestamp']} {f['side']} {f['quantity']} @ {f['price']}, 累计: {cum_qty:.6f}")
                        else:
                            # 如果没有找到开仓成交，放宽条件：直接找平仓成交
                            print(f"【调试】未找到开仓成交，放宽条件直接找平仓成交")
                            print(f"【调试】需要的开仓方向: {open_side}")
                            print(f"【调试】需要的平仓方向: {close_side}")
                            print(f"【调试】目标数量: {target_qty}")
                            
                            # 直接找所有Ask方向的成交（假设是long单的平仓）
                            for fill_dt, f in fills_with_dt:
                                if (f.get('side') == close_side and 
                                    cum_qty < target_qty + 1e-8):
                                    close_fills.append((fill_dt, f))
                                    cum_qty += float(f['quantity'])
                                    print(f"【调试】选中平仓成交: {f['timestamp']} {f['side']} {f['quantity']} @ {f['price']}, 累计: {cum_qty:.6f}")
                        
                        print(f"【调试】累计平仓成交: {cum_qty:.6f}, 目标: {target_qty:.6f}")
                        print(f"【调试】选中的平仓成交数量: {len(close_fills)}")
                        
                        # 如果找到了足够的平仓成交，计算补全信息
                        if abs(cum_qty - target_qty) < 1e-8 and close_fills:
                            # 计算加权均价
                            total_value = sum(float(f['quantity']) * float(f['price']) for _, f in close_fills)
                            close_price = total_value / cum_qty
                            
                            # 累计手续费
                            total_fee = sum(float(f['fee']) for _, f in close_fills)
                            
                            # 计算盈亏（只计算平仓手续费，与前端保持一致）
                            if order['direction'] == 'long':
                                pnl = (close_price - order['entry_price']) * target_qty - total_fee
                            else:
                                pnl = (order['entry_price'] - close_price) * target_qty - total_fee
                            
                            # 补全order信息
                            order['close_price'] = close_price
                            order['close_time'] = close_fills[-1][0].isoformat()
                            order['fee'] = total_fee
                            order['pnl'] = pnl
                            order['close_type'] = '成交历史自动补全'
                            
                            print(f"【调试】补全成功: close_price={close_price:.2f}, close_time={order['close_time']}, fee={total_fee:.6f}, pnl={pnl:.6f}")
                        else:
                            print(f"【调试】未找到足够的平仓成交，请人工核查")
                            print(f"【调试】需要的平仓方向: {close_side}")
                            print(f"【调试】开仓时间: {entry_dt}")
                            print(f"【调试】目标数量: {target_qty}")
                            print(f"【调试】实际累计: {cum_qty}")
                            
                            # 打印所有相关成交供人工核查
                            print(f"【调试】所有{close_side}方向成交:")
                            for fill_dt, f in fills_with_dt:
                                if f.get('side') == close_side:
                                    print(f"  {f['timestamp']} {f['side']} {f['quantity']} @ {f['price']}")
                except Exception as e:
                    print(f"【调试】成交历史补全失败: {e}")
                    continue
            self.strategy.save_stats()  # 保存补全后的统计
            # 4. 统计（只统计真实成交订单）
            valid_orders = [
                o for o in self.strategy.order_history
                if (o.get("order_id") != "N/A" and o.get("order_id")) or o.get("close_type") == "成交历史自动补全"
            ]
            if valid_orders:
                total_trades = len(valid_orders)
                closed_trades = len([o for o in valid_orders if o['close_price'] is not None])
                total_pnl = sum([o['pnl'] for o in valid_orders if o.get('pnl') is not None])
                self.log_message(f"总交易次数: {total_trades}")
                self.log_message(f"已平仓次数: {closed_trades}")
                self.log_message(f"累计盈亏: {total_pnl:.2f} USDT")
                if closed_trades > 0:
                    win_trades = len([o for o in valid_orders if o.get('pnl') and o['pnl'] > 0])
                    win_rate = win_trades / closed_trades * 100
                    self.log_message(f"胜率: {win_rate:.1f}%")
                    recent_trades = valid_orders[-5:]
                    self.log_message("最近5笔交易:")
                    for trade in recent_trades:
                        status = "已平仓" if trade['close_price'] else "持仓中"
                        pnl_str = f"盈亏: {trade['pnl']:.2f}" if trade.get('pnl') is not None else "未平仓"
                        self.log_message(f"  {trade['symbol']} {trade['direction']} {status} {pnl_str} order_id: {trade.get('order_id')} close_type: {trade.get('close_type')}")
            else:
                self.log_message("暂无真实成交交易记录")
        except Exception as e:
            self.log_message(f"显示统计信息失败: {e}")

    def check_local_time_offset(self, threshold_sec=5):
        """检测本地时间与NTP北京时间的偏差，超阈值时自动调用校准脚本，并详细日志"""
        try:
            c = ntplib.NTPClient()
            response = c.request('ntp.ntsc.ac.cn', version=3, timeout=3)
            utc_dt = datetime.utcfromtimestamp(response.tx_time).replace(tzinfo=timezone.utc)
            beijing_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
            local_dt = datetime.now(timezone(timedelta(hours=8)))
            diff = abs((local_dt - beijing_dt).total_seconds())
            self.log_message(f"[时间校准] 本地时间: {local_dt}, NTP北京时间: {beijing_dt}, 偏差: {diff:.2f}秒")
            if diff > threshold_sec:
                self.log_message(f"⚠️ 本地时间与北京时间偏差过大: {diff:.2f}秒，自动尝试校准...")
                try:
                    result = subprocess.run(['python3', 'sync_beijing_time.py'], capture_output=True, text=True, check=True)
                    self.log_message(f"校准脚本输出: {result.stdout.strip()}")
                except Exception as e:
                    self.log_message(f"自动校准失败: {e}")
            else:
                self.log_message(f"本地时间与北京时间偏差: {diff:.2f}秒，校准无需执行")
        except Exception as e:
            self.log_message(f"⚠️ 时间同步检查失败，继续执行策略: {e}")
            # 不阻塞程序执行，只记录警告

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='EMA趋势策略Backpack实盘交易程序')
    parser.add_argument('--config', default='backpack_trader_config.json', help='配置文件路径')
    parser.add_argument('--symbol', help='单次执行指定交易对')
    parser.add_argument('--stats', action='store_true', help='显示交易统计')
    parser.add_argument('--test', action='store_true', help='测试模式（不实际交易）')
    
    args = parser.parse_args()
    
    print("EMA趋势策略Backpack实盘交易程序")
    print("=" * 50)
    
    try:
        # 创建交易程序实例
        trader = EMATrendBackpackTrader(args.config)
        
        if args.stats:
            # 显示统计信息
            trader.show_statistics()
        elif args.symbol:
            # 单次执行
            if args.test:
                trader.log_message("测试模式：执行策略但不实际下单")
                # 修改策略为测试模式，执行策略但不下单
                original_execute = trader.strategy.execute_strategy
                def test_execute_strategy(*args, **kwargs):
                    kwargs['auto_trade'] = False  # 设置为不自动交易
                    return original_execute(*args, **kwargs)
                trader.strategy.execute_strategy = test_execute_strategy
            trader.run_single_execution(args.symbol)
        else:
            # 运行交易循环
            if args.test:
                trader.log_message("测试模式：执行策略但不实际下单")
                # 修改策略为测试模式，执行策略但不下单
                original_execute = trader.strategy.execute_strategy
                def test_execute_strategy(*args, **kwargs):
                    kwargs['auto_trade'] = False  # 设置为不自动交易
                    return original_execute(*args, **kwargs)
                trader.strategy.execute_strategy = test_execute_strategy
            trader.run()
            
    except Exception as e:
        print(f"程序执行失败: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 