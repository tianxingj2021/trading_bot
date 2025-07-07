"""
EMA隧道多时间框架交易策略
- 4小时图EMA144/169/576/676趋势排列判断
- 15分钟图EMA13/34金叉/死叉信号
- ATR止损建议
- 便于后续扩展
"""
import pandas as pd
import numpy as np
from exchanges.binance import Binance
import os
from utils.account_adapter import get_account_balance, get_max_leverage
from utils.order_adapter import place_order, close_position, get_exchange_instance
import time
from datetime import datetime
import json

class EMATunnelStrategy:
    binance = Binance(api_key="", api_secret="")
    kline_cache_dir = "kline_cache"
    stats_file = "strategy_stats.json"

    def __init__(self, atr_period=14, atr_mult=2):
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.active_positions = {}  # 记录活跃持仓: {symbol: {'direction': 'long/short', 'entry_price': float, 'stop_price': float, 'quantity': float, 'exchange': str}}
        self.order_history = []  # 新增：订单历史
        self.total_pnl = 0      # 新增：累计盈亏
        self.load_stats()  # 自动加载历史统计

    @staticmethod
    def calc_ema(df, period):
        return df['close'].ewm(span=period, adjust=False).mean()

    @staticmethod
    def calc_atr(df, period=13):
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(window=period, min_periods=1).mean()
        return atr

    def htf_trend(self, df_4h):
        """
        判断4小时趋势排列
        返回: '多头排列'/'空头排列'/'无明显趋势'
        """
        ema144 = self.calc_ema(df_4h, 144)
        ema169 = self.calc_ema(df_4h, 169)
        ema576 = self.calc_ema(df_4h, 576)
        ema676 = self.calc_ema(df_4h, 676)
        last = df_4h.index[-1]
        v144 = ema144.iloc[-1]
        v169 = ema169.iloc[-1]
        v576 = ema576.iloc[-1]
        v676 = ema676.iloc[-1]
        if v144 > v169 > v576 > v676:
            return '多头排列'
        elif v676 > v576 > v169 > v144:
            return '空头排列'
        else:
            return '无明显趋势'

    def ltf_signal_confirmed(self, df_15m):
        """
        检查倒数第二根K线是否刚刚金叉/死叉，
        若是，则当前K线允许入场
        """
        ema13 = self.calc_ema(df_15m, 13)
        ema34 = self.calc_ema(df_15m, 34)
        # 金叉发生在倒数第二根K线
        if ema13.iloc[-3] < ema34.iloc[-3] and ema13.iloc[-2] > ema34.iloc[-2]:
            return '金叉'
        elif ema13.iloc[-3] > ema34.iloc[-3] and ema13.iloc[-2] < ema34.iloc[-2]:
            return '死叉'
        else:
            return None

    def ltf_signal_realtime(self, df_15m):
        """
        实时信号检测：用倒数第二、三根K线判断金叉/死叉，信号出现立即触发
        """
        ema13 = self.calc_ema(df_15m, 13)
        ema34 = self.calc_ema(df_15m, 34)
        # 用倒数第二、三根K线判断（倒数第二根已收盘，价格稳定）
        if ema13.iloc[-3] < ema34.iloc[-3] and ema13.iloc[-2] > ema34.iloc[-2]:
            return '金叉'
        elif ema13.iloc[-3] > ema34.iloc[-3] and ema13.iloc[-2] < ema34.iloc[-2]:
            return '死叉'
        else:
            return None

    def atr_stop(self, df_15m, entry_price, direction):
        """
        计算ATR止损价
        direction: 'long' or 'short'
        """
        atr = self.calc_atr(df_15m, self.atr_period).iloc[-1]
        if direction == 'long':
            stop = entry_price - self.atr_mult * atr
        else:
            stop = entry_price + self.atr_mult * atr
        return stop, atr

    def should_open_long(self, df_4h, df_15m):
        """
        满足4小时多头排列+15分钟金叉（实时信号）
        """
        return self.htf_trend(df_4h) == '多头排列' and self.ltf_signal_realtime(df_15m) == '金叉'

    def should_open_short(self, df_4h, df_15m):
        """
        满足4小时空头排列+15分钟死叉（实时信号）
        """
        return self.htf_trend(df_4h) == '空头排列' and self.ltf_signal_realtime(df_15m) == '死叉'

    def should_close_long(self, df_4h, df_15m):
        """
        多头平仓条件：4小时转为空头排列 或 15分钟死叉（实时信号）
        """
        return self.htf_trend(df_4h) == '空头排列' or self.ltf_signal_realtime(df_15m) == '死叉'

    def should_close_short(self, df_4h, df_15m):
        """
        空头平仓条件：4小时转为多头排列 或 15分钟金叉（实时信号）
        """
        return self.htf_trend(df_4h) == '多头排列' or self.ltf_signal_realtime(df_15m) == '金叉'

    def recommend_position_size(self, account_balance, stop_distance, risk_pct=0.01, point_value=1):
        """
        推荐头寸规模
        """
        risk_amt = account_balance * risk_pct
        if stop_distance * point_value == 0:
            return 0
        size = risk_amt / (stop_distance * point_value)
        return size

    def recommend_position_size_by_account(self, exchange, symbol, user_leverage, stop_distance, entry_price, risk_pct=0.05, point_value=1, asset='USDT'):
        """
        推荐头寸规模（余额*杠杆*风险比例/入场价格，风险比例默认5%）
        :param exchange: 交易所名
        :param symbol: 交易对
        :param user_leverage: 用户设定杠杆
        :param stop_distance: 止损距离（保留参数，实际不再参与计算）
        :param entry_price: 入场价格
        :param risk_pct: 风险百分比，默认0.05
        :param point_value: 每点价值
        :param asset: 计价币种
        :return: 推荐头寸规模
        """
        # 自动判断计价币种：backpack使用USDC，其他使用USDT
        if exchange == 'backpack':
            asset = 'USDC'
        else:
            asset = 'USDT'
        balance = get_account_balance(exchange, asset)
        # Backpack交易所默认使用50倍杠杆，忽略用户设定和API查询的最大杠杆
        if exchange == 'backpack':
            lev = 50.0
        else:
            max_lev = get_max_leverage(exchange, symbol)
            lev = min(float(user_leverage), float(max_lev))
        # 推荐头寸 = 余额 * 杠杆 * 风险比例 / 入场价格
        if entry_price == 0:
            return 0
        size = balance * lev * risk_pct / entry_price
        
        # 根据交易所调整精度
        if exchange == 'backpack':
            # BTC合约5位小数，其他3位
            if symbol.upper().startswith('BTC'):
                size = round(size * 100000) / 100000
            else:
                size = round(size * 1000) / 1000
        elif exchange == 'aster':
            # Aster要求3位小数精度（BTC）
            if symbol == 'BTCUSDT':
                size = round(size * 1000) / 1000
            else:
                size = round(size * 10000) / 10000
        else:
            # 其他交易所默认4位小数
            size = round(size * 10000) / 10000
            
        return size

    def execute_strategy(self, exchange, symbol, leverage=50, risk_pct=0.05, auto_trade=True):
        """
        执行策略：自动检测信号并执行交易
        :param exchange: 交易所名
        :param symbol: 交易对
        :param leverage: 杠杆倍数
        :param risk_pct: 风险比例
        :param auto_trade: 是否自动交易，False时只返回信号
        :return: 策略执行结果
        """
        # === 新增：本地持仓与实际持仓同步，防止止损后卡死 ===
        try:
            ex = get_exchange_instance(exchange)
            positions = ex.get_account().positions if hasattr(ex.get_account(), 'positions') else ex.get_positions()
            has_real_position = any(
                (getattr(pos, 'symbol', None) or pos.get('symbol')) == symbol and float(getattr(pos, 'position_amt', 0) or pos.get('positionAmt', 0) or 0) != 0
                for pos in positions
            )
            if symbol in self.active_positions and not has_real_position:
                print(f'检测到本地持仓但实际已无持仓，自动清空active_positions')
                del self.active_positions[symbol]
        except Exception as e:
            print(f'同步实际持仓异常: {e}')
        # === 原有逻辑 ===
        print(f"\n=== 执行EMA隧道策略 ===")
        print(f"交易所: {exchange}")
        print(f"交易对: {symbol}")
        print(f"杠杆: {leverage}")
        print(f"风险比例: {risk_pct}")
        
        try:
            # 获取K线数据
            df_4h = self.get_binance_klines(symbol, '4h', limit=700)
            df_15m = self.get_binance_klines(symbol, '15m', limit=200)
            
            # 获取当前价格
            current_price = df_15m['close'].iloc[-1]
            print(f"当前价格: {current_price:.2f}")
            
            # 判断趋势和信号
            htf_trend = self.htf_trend(df_4h)
            ltf_signal = self.ltf_signal_confirmed(df_15m)
            
            print(f"4小时趋势: {htf_trend}")
            print(f"15分钟信号: {ltf_signal}")
            
            # 检查是否有活跃持仓
            if symbol in self.active_positions:
                position = self.active_positions[symbol]
                print(f"检测到活跃持仓: {position['direction']} @ {position['entry_price']:.2f}")
                
                # 检查平仓条件
                if position['direction'] == 'long' and self.should_close_long(df_4h, df_15m):
                    print("触发多头平仓信号")
                    if auto_trade:
                        self.close_position(exchange, symbol, 'long')
                        del self.active_positions[symbol]
                    return {'action': 'close_long', 'reason': '止盈信号'}
                    
                elif position['direction'] == 'short' and self.should_close_short(df_4h, df_15m):
                    print("触发空头平仓信号")
                    if auto_trade:
                        self.close_position(exchange, symbol, 'short')
                        del self.active_positions[symbol]
                    return {'action': 'close_short', 'reason': '止盈信号'}
                    
                else:
                    print("持仓中，无平仓信号")
                    return {'action': 'hold', 'reason': '持仓中'}
            
            # 检查开仓条件
            if self.should_open_long(df_4h, df_15m):
                print("触发多头开仓信号")
                if auto_trade:
                    return self.open_position(exchange, symbol, 'long', leverage, risk_pct, current_price, df_15m)
                else:
                    return {'action': 'open_long', 'reason': '多头排列+金叉'}
                    
            elif self.should_open_short(df_4h, df_15m):
                print("触发空头开仓信号")
                if auto_trade:
                    return self.open_position(exchange, symbol, 'short', leverage, risk_pct, current_price, df_15m)
                else:
                    return {'action': 'open_short', 'reason': '空头排列+死叉'}
            
            else:
                print("无开仓信号")
                return {'action': 'wait', 'reason': '等待信号'}
                
        except Exception as e:
            print(f"策略执行异常: {e}")
            import traceback
            traceback.print_exc()
            return {'action': 'error', 'reason': str(e)}

    def open_position(self, exchange, symbol, direction, leverage, risk_pct, entry_price, df_15m):
        """
        开仓并设置止损
        backpack: 开仓时直接带止损参数
        其他交易所: 开仓后单独下止损单
        """
        try:
            print(f"\n--- 开仓 {direction} ---")
            
            # 计算止损价
            stop_price, atr = self.atr_stop(df_15m, entry_price, direction)
            print(f"入场价格: {entry_price:.2f}")
            print(f"止损价格: {stop_price:.2f}")
            print(f"ATR: {atr:.2f}")
            
            # 计算头寸规模
            position_size = self.recommend_position_size_by_account(
                exchange, symbol, leverage, 
                abs(entry_price - stop_price), entry_price, risk_pct
            )
            print(f"推荐头寸: {position_size:.6f}")
            
            if position_size <= 0:
                print("头寸规模过小，跳过开仓")
                return {'action': 'skip', 'reason': '头寸规模过小'}
            
            if exchange == 'backpack':
                # Backpack: 开仓时直接带止损参数
                print("执行开仓（带止损参数）...")
                order_result = place_order(
                    exchange=exchange,
                    symbol=symbol,
                    amount=position_size,
                    direction=direction,
                    order_type='MARKET',
                    leverage=leverage,
                    is_quantity=True,
                    stop_price=stop_price
                )
                stop_order = None
            else:
                # 其他交易所：先开仓，再单独下止损单
                print("执行开仓...")
                order_result = place_order(
                    exchange=exchange,
                    symbol=symbol,
                    amount=position_size,
                    direction=direction,
                    order_type='MARKET',
                    leverage=leverage,
                    is_quantity=True
                )
                # 获取实际成交数量
                if hasattr(order_result, 'executed_qty'):
                    actual_quantity = float(order_result.executed_qty)
                elif hasattr(order_result, 'quantity'):
                    actual_quantity = float(order_result.quantity)
                else:
                    actual_quantity = position_size
                print("设置止损单...")
                stop_order = place_order(
                    exchange=exchange,
                    symbol=symbol,
                    amount=actual_quantity,
                    direction='short' if direction == 'long' else 'long',
                    order_type='STOP_MARKET',
                    stop_price=stop_price,
                    is_quantity=True
                )
            # 获取实际成交数量（Backpack也兼容）
            if hasattr(order_result, 'executed_qty'):
                actual_quantity = float(order_result.executed_qty)
            elif hasattr(order_result, 'quantity'):
                actual_quantity = float(order_result.quantity)
            else:
                actual_quantity = position_size
            print(f"开仓成功，实际数量: {actual_quantity:.6f}")
            # 记录持仓信息
            self.active_positions[symbol] = {
                'direction': direction,
                'entry_price': entry_price,
                'stop_price': stop_price,
                'quantity': actual_quantity,
                'exchange': exchange,
                'open_time': datetime.now()
            }
            # 新增：记录开仓订单
            self.order_history.append({
                'order_id': order_result.order_id if hasattr(order_result, 'order_id') else 'N/A',
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'entry_time': datetime.now().isoformat(),
                'quantity': actual_quantity,
                'close_price': None,
                'close_time': None,
                'close_type': None,
                'pnl': None,
                'result': str(order_result)
            })
            self.save_stats()  # 新增：保存到文件
            return {
                'action': f'opened_{direction}',
                'entry_price': entry_price,
                'stop_price': stop_price,
                'quantity': actual_quantity,
                'order_id': order_result.order_id if hasattr(order_result, 'order_id') else 'N/A',
                'stop_order_id': stop_order.order_id if stop_order and hasattr(stop_order, 'order_id') else None
            }
        except Exception as e:
            print(f"开仓失败: {e}")
            import traceback
            traceback.print_exc()
            return {'action': 'error', 'reason': f'开仓失败: {str(e)}'}

    def close_position(self, exchange, symbol, direction):
        """
        平仓
        """
        try:
            print(f"\n--- 平仓 {direction} ---")
            
            result = close_position(exchange, symbol, direction)
            print(f"平仓成功: {result}")
            
            # 新增：补全订单并统计盈亏
            close_price = None
            if isinstance(result, dict) and 'avgPrice' in result:
                close_price = float(result['avgPrice'])
            elif hasattr(result, 'avg_price'):
                close_price = float(result.avg_price)
            # 查找未平仓订单
            for order in reversed(self.order_history):
                if order['symbol'] == symbol and order['close_price'] is None:
                    order['close_price'] = close_price
                    order['close_time'] = datetime.now().isoformat()
                    order['close_type'] = '止盈/止损'  # 可根据信号细分
                    if close_price is not None:
                        order['pnl'] = (close_price - order['entry_price']) * order['quantity'] * (1 if order['direction']=='long' else -1)
                        self.total_pnl += order['pnl']
                    break
            self.save_stats()  # 新增：保存到文件
            return {'action': f'closed_{direction}', 'result': result}
            
        except Exception as e:
            print(f"平仓失败: {e}")
            import traceback
            traceback.print_exc()
            return {'action': 'error', 'reason': f'平仓失败: {str(e)}'}

    def monitor_positions(self, check_interval=60):
        """
        持续监控持仓，检查止盈信号
        :param check_interval: 检查间隔（秒）
        """
        print(f"开始监控持仓，检查间隔: {check_interval}秒")
        
        while True:
            try:
                for symbol in list(self.active_positions.keys()):
                    position = self.active_positions[symbol]
                    exchange = position['exchange']
                    
                    print(f"\n检查持仓: {symbol} {position['direction']}")
                    
                    # 获取最新K线数据
                    df_4h = self.get_binance_klines(symbol, '4h', limit=700)
                    df_15m = self.get_binance_klines(symbol, '15m', limit=200)
                    
                    # 检查平仓条件
                    if position['direction'] == 'long' and self.should_close_long(df_4h, df_15m):
                        print(f"触发多头平仓信号，执行平仓...")
                        self.close_position(exchange, symbol, 'long')
                        del self.active_positions[symbol]
                        
                    elif position['direction'] == 'short' and self.should_close_short(df_4h, df_15m):
                        print(f"触发空头平仓信号，执行平仓...")
                        self.close_position(exchange, symbol, 'short')
                        del self.active_positions[symbol]
                    
                    else:
                        print("无平仓信号，继续持仓")
                
                if not self.active_positions:
                    print("无活跃持仓，等待新信号...")
                
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                print("\n监控已停止")
                break
            except Exception as e:
                print(f"监控异常: {e}")
                time.sleep(check_interval)

    @staticmethod
    def get_binance_klines(symbol, interval, limit=1500):
        """
        获取币安K线数据，支持本地缓存，自动补齐缺失部分，并每次追加最新K线
        """
        os.makedirs(EMATunnelStrategy.kline_cache_dir, exist_ok=True)
        cache_file = os.path.join(EMATunnelStrategy.kline_cache_dir, f"{symbol}_{interval}.csv")
        interval_map = {'15m': 15*60*1000, '4h': 4*60*60*1000}
        interval_ms = interval_map.get(interval, 15*60*1000)
        now = int(time.time() * 1000)
        # 1. 加载本地缓存
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, index_col='open_time')
            df.index = df.index.astype(int)
        else:
            df = pd.DataFrame()
        # 2. 补全历史（本地数据不足时）
        if df.empty or len(df) < limit:
            klines = EMATunnelStrategy.binance.get_klines(symbol, interval, limit=limit)
            new_df = pd.DataFrame([{ 'open_time': k.open_time, 'open': float(k.open), 'high': float(k.high), 'low': float(k.low), 'close': float(k.close), 'volume': float(k.volume), 'close_time': k.close_time } for k in klines])
            new_df.set_index('open_time', inplace=True)
            df = new_df
        # 3. 检查并补全缺口
        if not df.empty:
            all_times = np.arange(df.index.min(), df.index.max()+interval_ms, interval_ms)
            missing = set(all_times) - set(df.index)
            for t in sorted(missing):
                # 拉取单根K线
                kl = EMATunnelStrategy.binance.get_klines(symbol, interval, startTime=int(t), endTime=int(t+interval_ms))
                if kl:
                    k = kl[0]
                    row = pd.DataFrame([{ 'open_time': k.open_time, 'open': float(k.open), 'high': float(k.high), 'low': float(k.low), 'close': float(k.close), 'volume': float(k.volume), 'close_time': k.close_time }])
                    row.set_index('open_time', inplace=True)
                    df = pd.concat([df, row])
        # 4. 拉取最新一根K线并追加
        latest_kl = EMATunnelStrategy.binance.get_klines(symbol, interval, limit=1)
        if latest_kl:
            k = latest_kl[0]
            if k.open_time not in df.index:
                row = pd.DataFrame([{ 'open_time': k.open_time, 'open': float(k.open), 'high': float(k.high), 'low': float(k.low), 'close': float(k.close), 'volume': float(k.volume), 'close_time': k.close_time }])
                row.set_index('open_time', inplace=True)
                df = pd.concat([df, row])
        # 5. 排序、去重、截断
        df = df[~df.index.duplicated(keep='last')]
        df = df.sort_index()
        if len(df) > limit:
            df = df.iloc[-limit:]
        # 6. 保存最新缓存
        df.to_csv(cache_file)
        return df

    def save_stats(self):
        data = {
            "order_history": self.order_history,
            "total_pnl": self.total_pnl
        }
        with open(self.stats_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_stats(self):
        if os.path.exists(self.stats_file):
            with open(self.stats_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.order_history = data.get("order_history", [])
                self.total_pnl = data.get("total_pnl", 0) 