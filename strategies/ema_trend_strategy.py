"""
EMA趋势多时间框架交易策略
- 1小时图EMA200趋势过滤：价格位于EMA200上方只做多，下方只做空
- 15分钟图EMA13/21/55金叉/死叉信号
- 2ATR倍数止损
- 5:1盈亏比固定止盈（仅使用固定止盈，不使用信号平仓）
- 便于后续扩展
"""
import pandas as pd
import numpy as np
from exchanges.binance import Binance
import os
from utils.account_adapter import get_account_balance, get_max_leverage
from utils.order_adapter import place_order, close_position, get_exchange_instance, get_latest_price, adapt_symbol
import time
from datetime import datetime
import json

class EMATrendStrategy:
    binance = Binance(api_key="", api_secret="")
    kline_cache_dir = "kline_cache"
    stats_file = "strategy_stats_ema_trend.json"

    def __init__(self, atr_period=14, atr_mult=2, risk_reward_ratio=5):
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.risk_reward_ratio = risk_reward_ratio  # 盈亏比
        self.active_positions = {}  # 记录活跃持仓: {symbol: {'direction': 'long/short', 'entry_price': float, 'stop_price': float, 'take_profit_price': float, 'quantity': float, 'exchange': str}}
        self.order_history = []  # 新增：订单历史
        self.total_pnl = 0      # 新增：累计盈亏
        self.load_stats()  # 自动加载历史统计

    @staticmethod
    def calc_ema(df, period):
        # TradingView/币安兼容EMA算法，首值用SMA初始化
        close = df['close']
        sma = close.rolling(window=period, min_periods=period).mean()
        ema = close.ewm(span=period, adjust=False).mean().copy()
        # 用SMA初始化首值
        if len(close) >= period:
            ema.iloc[period-1] = sma.iloc[period-1]
            alpha = 2 / (period + 1)
            for i in range(period, len(ema)):
                ema.iloc[i] = (close.iloc[i] - ema.iloc[i-1]) * alpha + ema.iloc[i-1]
        return ema

    @staticmethod
    def calc_atr(df, period=14):
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

    def htf_trend_filter(self, df_1h):
        """
        1小时趋势过滤：价格位于EMA200上方只做多，下方只做空
        返回: '多头趋势'/'空头趋势'/'无明显趋势'
        """
        ema200 = self.calc_ema(df_1h, 200)
        current_price = df_1h['close'].iloc[-1]
        ema200_value = ema200.iloc[-1]
        
        if current_price > ema200_value:
            return '多头趋势'
        elif current_price < ema200_value:
            return '空头趋势'
        else:
            return '无明显趋势'

    def ltf_signal_realtime(self, df_15m):
        """
        15分钟实时信号检测：三线金叉/死叉 + 二次金叉/死叉
        金叉：当前EMA13 > EMA21 > EMA55，且前一根EMA13 > EMA21，EMA21刚刚上穿EMA55
        死叉：当前EMA13 < EMA21 < EMA55，且前一根EMA13 < EMA21，EMA21刚刚下穿EMA55
        二次金叉：当前EMA13 > EMA21 > EMA55，且前一根EMA13 <= EMA21，EMA21 > EMA55
        二次死叉：当前EMA13 < EMA21 < EMA55，且前一根EMA13 >= EMA21，EMA21 < EMA55
        """
        ema13 = self.calc_ema(df_15m, 13)
        ema21 = self.calc_ema(df_15m, 21)
        ema55 = self.calc_ema(df_15m, 55)
        ema13_val, ema21_val, ema55_val = ema13.iloc[-1], ema21.iloc[-1], ema55.iloc[-1]
        ema13_prev, ema21_prev, ema55_prev = ema13.iloc[-2], ema21.iloc[-2], ema55.iloc[-2]

        # 区分金叉/二次金叉、死叉/二次死叉
        if (ema13_val > ema21_val > ema55_val):
            if (ema13_prev > ema21_prev and ema21_prev <= ema55_prev):
                return '金叉'
            elif (ema13_prev <= ema21_prev and ema21_prev > ema55_prev):
                return '二次金叉'
        elif (ema13_val < ema21_val < ema55_val):
            if (ema13_prev < ema21_prev and ema21_prev >= ema55_prev):
                return '死叉'
            elif (ema13_prev >= ema21_prev and ema21_prev < ema55_prev):
                return '二次死叉'
        return None

    def atr_stop_and_take_profit(self, df_15m, entry_price, direction, signal_type=None):
        """
        计算ATR止损价和止盈价，根据信号类型设置不同参数
        direction: 'long' or 'short'
        signal_type: '金叉'/'死叉'/'二次金叉'/'二次死叉'
        """
        atr = self.calc_atr(df_15m, self.atr_period).iloc[-1]
        
        # 根据信号类型设置不同参数
        if signal_type in ['二次金叉', '二次死叉']:
            # 二次信号：1.5倍ATR止损，3:1盈亏比
            atr_mult = 1.5
            risk_reward_ratio = 3.0
        else:
            # 金叉/死叉：使用默认参数
            atr_mult = self.atr_mult
            risk_reward_ratio = self.risk_reward_ratio
        
        stop_distance = atr_mult * atr
        take_profit_distance = stop_distance * risk_reward_ratio
        
        if direction == 'long':
            stop_price = entry_price - stop_distance
            take_profit_price = entry_price + take_profit_distance
        else:
            stop_price = entry_price + stop_distance
            take_profit_price = entry_price - take_profit_distance
        
        # 调试打印
        print(f"[调试] 入场价: {entry_price}")
        print(f"[调试] 信号类型: {signal_type}")
        print(f"[调试] ATR: {atr}")
        print(f"[调试] 止损倍数: {atr_mult}")
        print(f"[调试] 盈亏比: {risk_reward_ratio}")
        print(f"[调试] 止损距离: {stop_distance}")
        print(f"[调试] 止盈距离: {take_profit_distance}")
        print(f"[调试] 止损价: {stop_price}")
        print(f"[调试] 止盈价: {take_profit_price}")
        
        return stop_price, take_profit_price, atr

    def should_open_long(self, df_1h, df_15m):
        """
        满足1小时多头趋势+15分钟金叉或二次金叉
        """
        htf_trend = self.htf_trend_filter(df_1h)
        ltf_signal = self.ltf_signal_realtime(df_15m)
        return htf_trend == '多头趋势' and ltf_signal in ['金叉', '二次金叉']

    def should_open_short(self, df_1h, df_15m):
        """
        满足1小时空头趋势+15分钟死叉或二次死叉
        """
        htf_trend = self.htf_trend_filter(df_1h)
        ltf_signal = self.ltf_signal_realtime(df_15m)
        return htf_trend == '空头趋势' and ltf_signal in ['死叉', '二次死叉']

    def should_close_long(self, df_1h, df_15m):
        """
        多头平仓条件：仅使用固定止盈，不使用信号平仓
        """
        return False  # 不使用信号平仓，只使用固定止盈

    def should_close_short(self, df_1h, df_15m):
        """
        空头平仓条件：仅使用固定止盈，不使用信号平仓
        """
        return False  # 不使用信号平仓，只使用固定止盈

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

    def execute_strategy(self, exchange, symbol, leverage=50, risk_pct=0.05, auto_trade=True, positions=None):
        """
        执行策略：自动检测信号并执行交易
        :param exchange: 交易所名
        :param symbol: 交易对
        :param leverage: 杠杆倍数
        :param risk_pct: 风险比例
        :param auto_trade: 是否自动交易，False时只返回信号
        :param positions: 外部传入的持仓列表，None时自动查API
        :return: 策略执行结果
        """
        # === 持仓同步，优先用外部传入的positions ===
        try:
            if positions is None:
                ex = get_exchange_instance(exchange)
                positions = ex.get_positions()  # 只用get_positions，避免签名复杂
            has_real_position = any(
                (getattr(pos, 'symbol', None) or pos.get('symbol')) == symbol and float(getattr(pos, 'netQuantity', 0) or pos.get('netQuantity', 0) or getattr(pos, 'position_amt', 0) or pos.get('positionAmt', 0) or 0) != 0
                for pos in positions
            )
            if symbol in self.active_positions and not has_real_position:
                print(f'检测到本地持仓但实际已无持仓，自动清空active_positions')
                del self.active_positions[symbol]
        except Exception as e:
            print(f'同步实际持仓异常: {e}')
        # === 原有逻辑 ===
        print(f"\n=== 执行EMA趋势策略 ===")
        print(f"交易所: {exchange}")
        print(f"交易对: {symbol}")
        print(f"杠杆: {leverage}")
        print(f"风险比例: {risk_pct}")
        
        try:
            # 获取K线数据
            try:
                df_1h = self.get_binance_klines(symbol, '1h', limit=1500)
                df_15m = self.get_binance_klines(symbol, '15m', limit=3000)
                
                # 检查K线数据是否有效
                if df_1h.empty or df_15m.empty:
                    print(f"K线数据为空，无法执行策略")
                    return {'action': 'error', 'reason': 'K线数据为空'}
                
                if len(df_1h) < 200 or len(df_15m) < 55:
                    print(f"K线数据不足，1h: {len(df_1h)}, 15m: {len(df_15m)}")
                    return {'action': 'error', 'reason': 'K线数据不足'}
                    
            except Exception as e:
                print(f"获取K线数据失败: {e}")
                return {'action': 'error', 'reason': f'获取K线数据失败: {str(e)}'}
            
            # 仅用于展示，不再作为下单依据
            try:
                current_price = get_latest_price(exchange, symbol)
                print(f"当前价格: {current_price:.2f}")
            except Exception as e:
                print(f"获取当前价格异常: {e}")
            
            # 判断趋势和信号
            htf_trend = self.htf_trend_filter(df_1h)
            ltf_signal = self.ltf_signal_realtime(df_15m)
            
            print(f"1小时趋势: {htf_trend}")
            print(f"15分钟信号: {ltf_signal}")
            
            # 检查是否有活跃持仓
            if symbol in self.active_positions:
                position = self.active_positions[symbol]
                print(f"检测到活跃持仓: {position['direction']} @ {position['entry_price']:.2f}")
                
                # 检查平仓条件（仅使用固定止盈，不使用信号平仓）
                print("持仓中，仅使用固定止盈，不使用信号平仓")
                return {'action': 'hold', 'reason': '持仓中，仅使用固定止盈'}
            
            # 检查开仓条件
            if self.should_open_long(df_1h, df_15m):
                print("触发多头开仓信号")
                if auto_trade:
                    return self.open_position(exchange, symbol, 'long', leverage, risk_pct, df_15m=df_15m)
                else:
                    return {'action': 'open_long', 'reason': '多头趋势+金叉'}
                    
            elif self.should_open_short(df_1h, df_15m):
                print("触发空头开仓信号")
                if auto_trade:
                    return self.open_position(exchange, symbol, 'short', leverage, risk_pct, df_15m=df_15m)
                else:
                    return {'action': 'open_short', 'reason': '空头趋势+死叉'}
            
            else:
                print("无开仓信号")
                return {'action': 'wait', 'reason': '等待信号'}
                
        except Exception as e:
            print(f"策略执行异常: {e}")
            import traceback
            traceback.print_exc()
            return {'action': 'error', 'reason': str(e)}

    def get_mark_price(self, exchange_instance, symbol):
        """获取标记价格"""
        try:
            ticker = exchange_instance.get_ticker(symbol)
            mark_price = None
            for k in ['markPrice', 'mark_price', 'price', 'lastPrice', 'last_price']:
                if isinstance(ticker, dict) and k in ticker:
                    mark_price = float(ticker[k])
                    break
                elif hasattr(ticker, k):
                    mark_price = float(getattr(ticker, k))
                    break
            return mark_price
        except Exception as e:
            print(f'获取标记价格异常: {e}')
            return None

    def check_price_distance(self, mark_price, trigger_price, trigger_type):
        """检查触发价与标记价格的距离"""
        if mark_price is None:
            return False, "无法获取标记价格"
        
        distance = abs(mark_price - trigger_price)
        min_safe_distance = 20  # 最小安全距离
        
        if distance < min_safe_distance:
            return False, f"{trigger_type}触发价({trigger_price})与标记价格({mark_price})距离({distance})过近，可能被立即触发！"
        
        return True, f"{trigger_type}触发价({trigger_price})与标记价格({mark_price})距离({distance})安全"

    def create_trigger_order(self, exchange_instance, symbol, side, quantity, trigger_price, order_type="stop_loss"):
        """创建独立的触发单，必须同时传triggerPrice和triggerQuantity"""
        try:
            order_data = {
                'symbol': symbol,
                'side': side,
                'orderType': 'Market',
                'quantity': quantity,
                'reduceOnly': True,
                'triggerPrice': f"{float(trigger_price):.2f}",  # Backpack要求价格最多2位小数
                'triggerQuantity': str(quantity)  # 必须加上
            }
            print(f'{order_type}条件单参数:')
            for key, value in order_data.items():
                print(f'  {key}: {value}')
            print(f'\n发送{order_type}条件单...')
            order_result = exchange_instance.create_order(order_data)
            print(f'✅ {order_type}条件单下单成功:', order_result)
            if isinstance(order_result, dict):
                order_id = order_result.get('id')
                status = order_result.get('status')
                print(f'订单ID: {order_id}')
                print(f'订单状态: {status}')
                if status == 'Filled':
                    print(f'❌ {order_type}条件单被立即执行了！')
                    return False
                elif status in ['New', 'PartiallyFilled', 'TriggerPending']:
                    print(f'✅ {order_type}条件单已挂单，等待触发')
                    return True
                else:
                    print(f'⚠️  {order_type}订单状态异常: {status}')
                    return False
            else:
                print(f'✅ {order_type}条件单创建成功')
                return True
        except Exception as e:
            print(f'❌ {order_type}条件单下单异常: {e}')
            return False

    def open_position(self, exchange, symbol, direction, leverage, risk_pct, entry_price=None, df_15m=None):
        """
        开仓并设置止损和止盈，全部用实际成交价计算
        """
        try:
            print(f"\n--- 开仓 {direction} ---")
            # 计算头寸规模（用当前K线ATR等参数）
            if df_15m is None:
                raise ValueError('df_15m不能为空')
            
            # 获取当前信号类型
            ltf_signal = self.ltf_signal_realtime(df_15m)
            print(f"当前信号类型: {ltf_signal}")
            
            # 先用当前K线估算止损距离，实际止损价/止盈价用成交价再算
            atr = self.calc_atr(df_15m, self.atr_period).iloc[-1]
            stop_distance = self.atr_mult * atr
            print(f"ATR: {atr:.2f}，止损距离: {stop_distance:.2f}")
            # 推荐头寸
            # 这里entry_price参数只用于头寸估算，实际成交价后面会打印
            position_size = self.recommend_position_size_by_account(
                exchange, symbol, leverage, stop_distance, entry_price or 1, risk_pct
            )
            print(f"推荐头寸: {position_size:.6f}")
            if position_size <= 0:
                print("头寸规模过小，跳过开仓")
                return {'action': 'skip', 'reason': '头寸规模过小'}
            # 市价单开仓
            order_result = place_order(
                exchange=exchange,
                symbol=symbol,
                amount=position_size,
                direction=direction,
                order_type='MARKET',
                leverage=leverage,
                is_quantity=False  # 传递的是USDC金额，不是数量
            )
            # 获取实际成交价
            executed_price = None
            if isinstance(order_result, dict):
                executed_price = float(order_result.get('avgPrice') or order_result.get('executedPrice') or order_result.get('price') or 0)
                if not executed_price and 'fills' in order_result and order_result['fills']:
                    executed_price = float(order_result['fills'][0].get('price', 0))
                if (not executed_price or executed_price == 0) and order_result.get('executedQuantity') and order_result.get('executedQuoteQuantity'):
                    try:
                        executed_qty = float(order_result['executedQuantity'])
                        executed_quote = float(order_result['executedQuoteQuantity'])
                        if executed_qty:
                            executed_price = executed_quote / executed_qty
                    except Exception as e:
                        print('计算成交价异常:', e)
            if not executed_price or executed_price == 0:
                print('❌ 未获取到实际成交价，无法补发止损止盈')
                return {'action': 'error', 'reason': '未获取到实际成交价'}
            print(f"✅ 实际成交价: {executed_price}")
            # 用实际成交价计算止损止盈，传入信号类型
            stop_price, take_profit_price, atr = self.atr_stop_and_take_profit(df_15m, executed_price, direction, ltf_signal)
            stop_price = round(stop_price, 1)
            take_profit_price = round(take_profit_price, 1)
            print(f"止损价格: {stop_price:.1f}")
            print(f"止盈价格: {take_profit_price:.1f}")
            # 后续流程与原来一致...
            # 获取最新持仓数量
            ex = get_exchange_instance(exchange)
            import time
            time.sleep(2)
            positions = ex.get_positions()
            pos_qty = None
            # 使用adapt_symbol适配symbol，确保与交易所返回的symbol格式一致
            adapted_symbol = adapt_symbol(symbol, exchange)
            for pos in positions:
                if (getattr(pos, 'symbol', None) or pos.get('symbol')) == adapted_symbol:
                    pos_qty = str(pos.get('netQuantity') or getattr(pos, 'netQuantity', None) or pos.get('positionAmt', None) or getattr(pos, 'positionAmt', None))
            if not pos_qty or float(pos_qty) == 0:
                print('❌ 未获取到持仓数量，测试失败')
                return {'action': 'error', 'reason': '未获取到持仓数量'}
            print(f'✅ 持仓数量: {pos_qty}')
            # 获取当前标记价格并检查距离安全性
            mark_price = self.get_mark_price(ex, adapted_symbol)
            if mark_price is None:
                print('❌ 无法获取标记价格，测试失败')
                return {'action': 'error', 'reason': '无法获取标记价格'}
            print(f'✅ 当前标记价格: {mark_price}')
            sl_safe, sl_msg = self.check_price_distance(mark_price, stop_price, "止损")
            tp_safe, tp_msg = self.check_price_distance(mark_price, take_profit_price, "止盈")
            print(f'止损距离检查: {"✅" if sl_safe else "❌"} {sl_msg}')
            print(f'止盈距离检查: {"✅" if tp_safe else "❌"} {tp_msg}')
            if not sl_safe or not tp_safe:
                print('⚠️  警告：价格距离过近，条件单可能被立即触发！')
                print('建议：扩大止损距离或等待价格波动后再补发条件单')
                return {'action': 'error', 'reason': '价格距离过近，条件单可能被立即触发'}
            # 补发止损单
            print("\n--- 补发止损单 ---")
            sl_success = self.create_trigger_order(
                ex, 
                adapted_symbol,  # 使用适配后的symbol
                'Ask' if direction == 'long' else 'Bid',  # 平多用Ask，平空用Bid
                pos_qty, 
                stop_price, 
                "止损"
            )
            # 补发止盈单
            print("\n--- 补发止盈单 ---")
            tp_success = self.create_trigger_order(
                ex, 
                adapted_symbol,  # 使用适配后的symbol
                'Ask' if direction == 'long' else 'Bid',  # 平多用Ask，平空用Bid
                pos_qty, 
                take_profit_price, 
                "止盈"
            )
            if not sl_success or not tp_success:
                print("❌ 条件单补发失败")
                return {'action': 'error', 'reason': '条件单补发失败'}
            # 记录持仓信息
            self.active_positions[symbol] = {
                'direction': direction,
                'entry_price': executed_price,
                'stop_price': stop_price,
                'take_profit_price': take_profit_price,
                'quantity': float(pos_qty),
                'exchange': exchange,
                'open_time': datetime.now()
            }
            # 新增：记录开仓订单
            self.order_history.append({
                'order_id': order_result.get('order_id', order_result.get('id', 'N/A')) if isinstance(order_result, dict) else 'N/A',
                'symbol': symbol,
                'direction': direction,
                'entry_price': executed_price,
                'entry_time': datetime.now().isoformat(),
                'quantity': float(pos_qty),
                'stop_price': stop_price,
                'take_profit_price': take_profit_price,
                'close_price': None,
                'close_time': None,
                'close_type': None,
                'pnl': None,
                'result': str(order_result)
            })
            self.save_stats()  # 新增：保存到文件
            return {
                'action': f'opened_{direction}',
                'entry_price': executed_price,
                'stop_price': stop_price,
                'take_profit_price': take_profit_price,
                'quantity': float(pos_qty),
                'order_id': order_result.get('order_id', order_result.get('id', 'N/A')) if isinstance(order_result, dict) else 'N/A',
                'stop_order_id': None,
                'take_profit_order_id': None
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
                    df_1h = self.get_binance_klines(symbol, '1h', limit=1500)
                    df_15m = self.get_binance_klines(symbol, '15m', limit=3000)
                    
                    # 检查平仓条件（仅使用固定止盈，不使用信号平仓）
                    print("持仓中，仅使用固定止盈，不使用信号平仓")
                
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
        获取币安K线数据，支持本地缓存，自动补齐缺失部分，并每次追加最新K线。
        本地缓存文件始终保留全部历史数据，只在返回时截断。
        """
        os.makedirs(EMATrendStrategy.kline_cache_dir, exist_ok=True)
        cache_file = os.path.join(EMATrendStrategy.kline_cache_dir, f"{symbol}_{interval}.csv")
        interval_map = {'15m': 15*60*1000, '1h': 1*60*60*1000, '4h': 4*60*60*1000}
        interval_ms = interval_map.get(interval, 1*60*1000)
        now = int(time.time() * 1000)
        
        # 1. 加载本地缓存
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, index_col='open_time')
            df.index = df.index.astype(int)
        else:
            df = pd.DataFrame()
        
        # 2. 补全历史（本地数据不足时）
        if df.empty or len(df) < limit:
            try:
                klines = EMATrendStrategy.binance.get_klines(symbol, interval, limit=limit)
                new_df = pd.DataFrame([{ 'open_time': k.open_time, 'open': float(k.open), 'high': float(k.high), 'low': float(k.low), 'close': float(k.close), 'volume': float(k.volume), 'close_time': k.close_time } for k in klines])
                new_df.set_index('open_time', inplace=True)
                df = new_df if df.empty else pd.concat([df, new_df])
            except Exception as e:
                print(f"获取K线历史数据失败: {e}")
                if df.empty:
                    return pd.DataFrame()  # 如果没有缓存数据，返回空DataFrame
        
        # 3. 检查并补全缺口
        if not df.empty:
            all_times = np.arange(df.index.min(), df.index.max()+interval_ms, interval_ms)
            missing = set(all_times) - set(df.index)
            for t in sorted(missing):
                try:
                    kl = EMATrendStrategy.binance.get_klines_with_time(symbol, interval, startTime=int(t), endTime=int(t+interval_ms))
                    if kl:
                        k = kl[0]
                        row = pd.DataFrame([{ 'open_time': k.open_time, 'open': float(k.open), 'high': float(k.high), 'low': float(k.low), 'close': float(k.close), 'volume': float(k.volume), 'close_time': k.close_time }])
                        row.set_index('open_time', inplace=True)
                        df = pd.concat([df, row])
                except Exception as e:
                    print(f"补全K线失败: {e}")
                    continue
        
        # 4. 拉取最新一根K线并追加
        try:
            latest_kl = EMATrendStrategy.binance.get_klines(symbol, interval, limit=1)
            if latest_kl:
                k = latest_kl[0]
                if k.open_time not in df.index:
                    row = pd.DataFrame([{ 'open_time': k.open_time, 'open': float(k.open), 'high': float(k.high), 'low': float(k.low), 'close': float(k.close), 'volume': float(k.volume), 'close_time': k.close_time }])
                    row.set_index('open_time', inplace=True)
                    df = pd.concat([df, row])
        except Exception as e:
            print(f"获取最新K线失败: {e}")
            # 如果获取最新K线失败，使用缓存数据
        
        # 5. 排序、去重（不再截断）
        df = df[~df.index.duplicated(keep='last')]
        df = df.sort_index()
        
        # 6. 保存全部历史缓存
        try:
            df.to_csv(cache_file)
        except Exception as e:
            print(f"保存K线缓存失败: {e}")
        
        # 7. 返回最新limit根
        return df.tail(limit)

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

    @staticmethod
    def print_ema_debug():
        import pandas as pd
        df = pd.read_csv('kline_cache/BTCUSDT_1m.csv', index_col='open_time')
        # 新算法
        ema13 = EMATrendStrategy.calc_ema(df, 13)
        ema21 = EMATrendStrategy.calc_ema(df, 21)
        ema55 = EMATrendStrategy.calc_ema(df, 55)
        # pandas原生算法
        ema13_pd = df['close'].ewm(span=13, adjust=False).mean()
        ema21_pd = df['close'].ewm(span=21, adjust=False).mean()
        ema55_pd = df['close'].ewm(span=55, adjust=False).mean()
        for ts in [1751703180000, 1751703240000, 1751703300000]:
            close = df.loc[ts, 'close'] if ts in df.index else 'N/A'
            e13 = ema13.loc[ts] if ts in ema13.index else 'N/A'
            e21 = ema21.loc[ts] if ts in ema21.index else 'N/A'
            e55 = ema55.loc[ts] if ts in ema55.index else 'N/A'
            e13_pd = ema13_pd.loc[ts] if ts in ema13_pd.index else 'N/A'
            e21_pd = ema21_pd.loc[ts] if ts in ema21_pd.index else 'N/A'
            e55_pd = ema55_pd.loc[ts] if ts in ema55_pd.index else 'N/A'
            print(f"Time: {ts}, Close: {close}, EMA13: {e13}, EMA21: {e21}, EMA55: {e55} | pandas原生: {e13_pd}, {e21_pd}, {e55_pd}") 