"""
EMA隧道多时间框架交易策略 - 实时WebSocket版本
- 4小时图EMA144/169/576/676趋势排列判断
- 15分钟图EMA13/34金叉/死叉信号
- ATR止损建议
- 使用WebSocket实时数据推送，毫秒级响应
"""
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime
import json
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

# 导入交易所和工具类
from exchanges.aster import Aster, AsterKline, AsterOrder, AsterAccountSnapshot
from utils.account_adapter import get_account_balance, get_max_leverage
from utils.order_adapter import place_order, close_position, get_exchange_instance

@dataclass
class StrategySignal:
    """策略信号数据类"""
    timestamp: int
    symbol: str
    htf_trend: str  # 4小时趋势
    ltf_signal: str  # 15分钟信号
    current_price: float
    action: str  # 'open_long', 'open_short', 'close_long', 'close_short', 'hold', 'wait'
    reason: str
    confidence: float  # 信号置信度 0-1

class EMATunnelStrategyRealtime:
    """实时EMA隧道策略 - WebSocket版本"""
    
    def __init__(self, exchange_name: str, api_key: str, api_secret: str, 
                 symbol: str = "BTCUSDT", atr_period: int = 14, atr_mult: float = 2.0):
        """
        初始化实时策略
        :param exchange_name: 交易所名称 ('aster', 'backpack', 'binance')
        :param api_key: API密钥
        :param api_secret: API密钥
        :param symbol: 交易对
        :param atr_period: ATR周期
        :param atr_mult: ATR倍数
        """
        self.exchange_name = exchange_name
        self.symbol = symbol
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        
        # 初始化交易所连接
        if exchange_name == 'aster':
            self.exchange = Aster(api_key, api_secret)
        else:
            # 其他交易所的初始化
            self.exchange = get_exchange_instance(exchange_name)
        
        # 实时数据缓存
        self.kline_4h: List[AsterKline] = []
        self.kline_15m: List[AsterKline] = []
        self.account_snapshot: Optional[AsterAccountSnapshot] = None
        self.open_orders: List[AsterOrder] = []
        self.ticker_snapshot = None
        self.depth_snapshot = None
        
        # 策略状态
        self.active_positions: Dict[str, Dict] = {}
        self.order_history: List[Dict] = []
        self.total_pnl = 0.0
        self.signal_history: List[StrategySignal] = []
        
        # 控制标志
        self.is_running = False
        self.is_ready = False
        
        # 回调函数
        self.signal_callbacks: List[Callable[[StrategySignal], None]] = []
        self.trade_callbacks: List[Callable[[Dict], None]] = []
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 加载历史数据
        self.load_stats()
        
    def setup_websocket_callbacks(self):
        """设置WebSocket回调函数"""
        # 账户更新回调
        self.exchange.watch_account(self._on_account_update)
        
        # 订单更新回调
        self.exchange.watch_order(self._on_order_update)
        
        # 4小时K线更新回调
        self.exchange.watch_kline(self.symbol, "4h", self._on_kline_4h_update)
        
        # 15分钟K线更新回调
        self.exchange.watch_kline(self.symbol, "15m", self._on_kline_15m_update)
        
        # Ticker更新回调
        self.exchange.watch_ticker(self.symbol, self._on_ticker_update)
        
        # 深度更新回调
        self.exchange.watch_depth(self.symbol, self._on_depth_update)
    
    def _on_account_update(self, data: AsterAccountSnapshot):
        """账户更新回调"""
        with self.lock:
            self.account_snapshot = data
            self._check_ready_state()
    
    def _on_order_update(self, orders: List[AsterOrder]):
        """订单更新回调"""
        with self.lock:
            self.open_orders = [o for o in orders if o.type != 'MARKET']
            self._check_ready_state()
    
    def _on_kline_4h_update(self, klines: List[AsterKline]):
        """4小时K线更新回调"""
        with self.lock:
            self.kline_4h = klines
            self._check_ready_state()
            self._process_strategy_signals()
    
    def _on_kline_15m_update(self, klines: List[AsterKline]):
        """15分钟K线更新回调"""
        with self.lock:
            self.kline_15m = klines
            self._check_ready_state()
            self._process_strategy_signals()
    
    def _on_ticker_update(self, ticker):
        """Ticker更新回调"""
        with self.lock:
            self.ticker_snapshot = ticker
            self._check_ready_state()
    
    def _on_depth_update(self, depth):
        """深度更新回调"""
        with self.lock:
            self.depth_snapshot = depth
            self._check_ready_state()
    
    def _check_ready_state(self):
        """检查是否所有数据都已就绪"""
        if (self.account_snapshot and self.kline_4h and self.kline_15m and 
            self.ticker_snapshot and self.depth_snapshot):
            self.is_ready = True
        else:
            self.is_ready = False
    
    def _process_strategy_signals(self):
        """处理策略信号"""
        if not self.is_ready:
            return
        
        # 转换为DataFrame进行计算
        df_4h = self._klines_to_dataframe(self.kline_4h)
        df_15m = self._klines_to_dataframe(self.kline_15m)
        
        if len(df_4h) < 700 or len(df_15m) < 200:
            return  # 数据不足
        
        # 获取当前价格
        current_price = float(self.ticker_snapshot.last_price)
        
        # 计算信号
        signal = self._calculate_signal(df_4h, df_15m, current_price)
        
        if signal:
            # 记录信号
            self.signal_history.append(signal)
            
            # 调用信号回调
            for callback in self.signal_callbacks:
                try:
                    callback(signal)
                except Exception as e:
                    print(f"信号回调错误: {e}")
            
            # 自动执行交易
            if self.is_running:
                self._execute_signal(signal)
    
    def _klines_to_dataframe(self, klines: List[AsterKline]) -> pd.DataFrame:
        """将K线数据转换为DataFrame"""
        if not klines:
            return pd.DataFrame()
        
        data = []
        for k in klines:
            data.append({
                'open_time': k.open_time,
                'open': float(k.open),
                'high': float(k.high),
                'low': float(k.low),
                'close': float(k.close),
                'volume': float(k.volume),
                'close_time': k.close_time
            })
        
        df = pd.DataFrame(data)
        df.set_index('open_time', inplace=True)
        df.sort_index(inplace=True)
        return df
    
    @staticmethod
    def calc_ema(df: pd.DataFrame, period: int) -> pd.Series:
        """计算EMA"""
        return df['close'].ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算ATR"""
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
    
    def htf_trend(self, df_4h: pd.DataFrame) -> str:
        """判断4小时趋势排列"""
        if len(df_4h) < 676:
            return '无明显趋势'
        
        ema144 = self.calc_ema(df_4h, 144)
        ema169 = self.calc_ema(df_4h, 169)
        ema576 = self.calc_ema(df_4h, 576)
        ema676 = self.calc_ema(df_4h, 676)
        
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
    
    def ltf_signal_realtime(self, df_15m: pd.DataFrame) -> Optional[str]:
        """实时15分钟信号检测"""
        if len(df_15m) < 34:
            return None
        
        ema13 = self.calc_ema(df_15m, 13)
        ema34 = self.calc_ema(df_15m, 34)
        
        # 用倒数第二、三根K线判断（倒数第二根已收盘，价格稳定）
        if ema13.iloc[-3] < ema34.iloc[-3] and ema13.iloc[-2] > ema34.iloc[-2]:
            return '金叉'
        elif ema13.iloc[-3] > ema34.iloc[-3] and ema13.iloc[-2] < ema34.iloc[-2]:
            return '死叉'
        else:
            return None
    
    def atr_stop(self, df_15m: pd.DataFrame, entry_price: float, direction: str) -> tuple:
        """计算ATR止损价"""
        atr = self.calc_atr(df_15m, self.atr_period).iloc[-1]
        if direction == 'long':
            stop = entry_price - self.atr_mult * atr
        else:
            stop = entry_price + self.atr_mult * atr
        return stop, atr
    
    def _calculate_signal(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame, current_price: float) -> Optional[StrategySignal]:
        """计算策略信号"""
        htf_trend = self.htf_trend(df_4h)
        ltf_signal = self.ltf_signal_realtime(df_15m)
        
        # 检查是否有活跃持仓
        if self.symbol in self.active_positions:
            position = self.active_positions[self.symbol]
            
            # 检查平仓条件
            if position['direction'] == 'long' and self._should_close_long(htf_trend, ltf_signal):
                return StrategySignal(
                    timestamp=int(time.time() * 1000),
                    symbol=self.symbol,
                    htf_trend=htf_trend,
                    ltf_signal=ltf_signal or '无信号',
                    current_price=current_price,
                    action='close_long',
                    reason='止盈信号',
                    confidence=0.8
                )
            elif position['direction'] == 'short' and self._should_close_short(htf_trend, ltf_signal):
                return StrategySignal(
                    timestamp=int(time.time() * 1000),
                    symbol=self.symbol,
                    htf_trend=htf_trend,
                    ltf_signal=ltf_signal or '无信号',
                    current_price=current_price,
                    action='close_short',
                    reason='止盈信号',
                    confidence=0.8
                )
            else:
                return StrategySignal(
                    timestamp=int(time.time() * 1000),
                    symbol=self.symbol,
                    htf_trend=htf_trend,
                    ltf_signal=ltf_signal or '无信号',
                    current_price=current_price,
                    action='hold',
                    reason='持仓中',
                    confidence=0.5
                )
        
        # 检查开仓条件
        if self._should_open_long(htf_trend, ltf_signal):
            return StrategySignal(
                timestamp=int(time.time() * 1000),
                symbol=self.symbol,
                htf_trend=htf_trend,
                ltf_signal=ltf_signal,
                current_price=current_price,
                action='open_long',
                reason='多头排列+金叉',
                confidence=0.9
            )
        elif self._should_open_short(htf_trend, ltf_signal):
            return StrategySignal(
                timestamp=int(time.time() * 1000),
                symbol=self.symbol,
                htf_trend=htf_trend,
                ltf_signal=ltf_signal,
                current_price=current_price,
                action='open_short',
                reason='空头排列+死叉',
                confidence=0.9
            )
        
        return StrategySignal(
            timestamp=int(time.time() * 1000),
            symbol=self.symbol,
            htf_trend=htf_trend,
            ltf_signal=ltf_signal or '无信号',
            current_price=current_price,
            action='wait',
            reason='等待信号',
            confidence=0.3
        )
    
    def _should_open_long(self, htf_trend: str, ltf_signal: Optional[str]) -> bool:
        """是否应该开多"""
        return htf_trend == '多头排列' and ltf_signal == '金叉'
    
    def _should_open_short(self, htf_trend: str, ltf_signal: Optional[str]) -> bool:
        """是否应该开空"""
        return htf_trend == '空头排列' and ltf_signal == '死叉'
    
    def _should_close_long(self, htf_trend: str, ltf_signal: Optional[str]) -> bool:
        """是否应该平多"""
        return htf_trend == '空头排列' or ltf_signal == '死叉'
    
    def _should_close_short(self, htf_trend: str, ltf_signal: Optional[str]) -> bool:
        """是否应该平空"""
        return htf_trend == '多头排列' or ltf_signal == '金叉'
    
    def _execute_signal(self, signal: StrategySignal):
        """执行策略信号"""
        try:
            if signal.action == 'open_long':
                self._open_position('long', signal.current_price)
            elif signal.action == 'open_short':
                self._open_position('short', signal.current_price)
            elif signal.action == 'close_long':
                self._close_position('long')
            elif signal.action == 'close_short':
                self._close_position('short')
        except Exception as e:
            print(f"执行信号错误: {e}")
    
    def _open_position(self, direction: str, entry_price: float):
        """开仓"""
        try:
            print(f"\n=== 开仓 {direction} ===")
            print(f"入场价格: {entry_price:.2f}")
            
            # 计算头寸规模
            position_size = self._calculate_position_size(entry_price)
            if position_size <= 0:
                print("头寸规模过小，跳过开仓")
                return
            
            # 计算止损价
            df_15m = self._klines_to_dataframe(self.kline_15m)
            stop_price, atr = self.atr_stop(df_15m, entry_price, direction)
            print(f"止损价格: {stop_price:.2f}")
            print(f"ATR: {atr:.2f}")
            print(f"头寸规模: {position_size:.6f}")
            
            # 执行开仓
            order_result = place_order(
                exchange=self.exchange_name,
                symbol=self.symbol,
                amount=position_size,
                direction=direction,
                order_type='MARKET',
                leverage=50,
                is_quantity=True
            )
            
            # 记录持仓信息
            self.active_positions[self.symbol] = {
                'direction': direction,
                'entry_price': entry_price,
                'stop_price': stop_price,
                'quantity': position_size,
                'exchange': self.exchange_name,
                'open_time': datetime.now()
            }
            
            # 记录订单历史
            self.order_history.append({
                'order_id': getattr(order_result, 'order_id', 'N/A'),
                'symbol': self.symbol,
                'direction': direction,
                'entry_price': entry_price,
                'entry_time': datetime.now().isoformat(),
                'quantity': position_size,
                'close_price': None,
                'close_time': None,
                'close_type': None,
                'pnl': None
            })
            
            print(f"开仓成功: {direction} @ {entry_price:.2f}")
            self.save_stats()
            
        except Exception as e:
            print(f"开仓失败: {e}")
    
    def _close_position(self, direction: str):
        """平仓"""
        try:
            print(f"\n=== 平仓 {direction} ===")
            
            result = close_position(self.exchange_name, self.symbol, direction)
            print(f"平仓成功: {result}")
            
            # 更新订单历史
            close_price = None
            if isinstance(result, dict) and 'avgPrice' in result:
                close_price = float(result['avgPrice'])
            elif hasattr(result, 'avg_price'):
                close_price = float(result.avg_price)
            
            # 查找未平仓订单
            for order in reversed(self.order_history):
                if order['symbol'] == self.symbol and order['close_price'] is None:
                    order['close_price'] = close_price
                    order['close_time'] = datetime.now().isoformat()
                    order['close_type'] = '止盈/止损'
                    if close_price is not None:
                        order['pnl'] = (close_price - order['entry_price']) * order['quantity'] * (1 if order['direction']=='long' else -1)
                        self.total_pnl += order['pnl']
                    break
            
            # 清除活跃持仓
            if self.symbol in self.active_positions:
                del self.active_positions[self.symbol]
            
            self.save_stats()
            
        except Exception as e:
            print(f"平仓失败: {e}")
    
    def _calculate_position_size(self, entry_price: float) -> float:
        """计算头寸规模"""
        try:
            balance = get_account_balance(self.exchange_name, 'USDT')
            risk_pct = 0.05  # 5%风险
            
            # 计算止损距离
            df_15m = self._klines_to_dataframe(self.kline_15m)
            stop_price, _ = self.atr_stop(df_15m, entry_price, 'long')
            stop_distance = abs(entry_price - stop_price)
            
            # 计算头寸规模
            size = balance * 50 * risk_pct / entry_price  # 50倍杠杆
            
            # 根据交易所调整精度
            if self.exchange_name == 'aster':
                size = round(size * 1000) / 1000
            else:
                size = round(size * 10000) / 10000
            
            return size
        except Exception as e:
            print(f"计算头寸规模错误: {e}")
            return 0
    
    def add_signal_callback(self, callback: Callable[[StrategySignal], None]):
        """添加信号回调函数"""
        self.signal_callbacks.append(callback)
    
    def add_trade_callback(self, callback: Callable[[Dict], None]):
        """添加交易回调函数"""
        self.trade_callbacks.append(callback)
    
    def start(self):
        """启动策略"""
        print("启动EMA隧道实时策略...")
        self.setup_websocket_callbacks()
        self.is_running = True
        
        # 等待数据就绪
        while not self.is_ready:
            print("等待数据就绪...")
            time.sleep(1)
        
        print("策略已启动，开始实时监控...")
    
    def stop(self):
        """停止策略"""
        print("停止EMA隧道实时策略...")
        self.is_running = False
        self.save_stats()
    
    def get_status(self) -> Dict:
        """获取策略状态"""
        return {
            'is_running': self.is_running,
            'is_ready': self.is_ready,
            'active_positions': self.active_positions,
            'total_pnl': self.total_pnl,
            'signal_count': len(self.signal_history),
            'order_count': len(self.order_history)
        }
    
    def save_stats(self):
        """保存统计数据"""
        data = {
            "order_history": self.order_history,
            "total_pnl": self.total_pnl,
            "signal_history": [
                {
                    'timestamp': s.timestamp,
                    'symbol': s.symbol,
                    'htf_trend': s.htf_trend,
                    'ltf_signal': s.ltf_signal,
                    'current_price': s.current_price,
                    'action': s.action,
                    'reason': s.reason,
                    'confidence': s.confidence
                }
                for s in self.signal_history
            ]
        }
        
        with open("strategy_stats_realtime.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_stats(self):
        """加载统计数据"""
        try:
            if os.path.exists("strategy_stats_realtime.json"):
                with open("strategy_stats_realtime.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.order_history = data.get("order_history", [])
                    self.total_pnl = data.get("total_pnl", 0)
                    
                    # 加载信号历史
                    signal_data = data.get("signal_history", [])
                    self.signal_history = [
                        StrategySignal(**s) for s in signal_data
                    ]
        except Exception as e:
            print(f"加载统计数据错误: {e}")


# 使用示例
def main():
    """主函数示例"""
    import os
    
    # 从环境变量获取API密钥
    api_key = os.getenv("ASTER_API_KEY", "")
    api_secret = os.getenv("ASTER_API_SECRET", "")
    
    if not api_key or not api_secret:
        print("请设置ASTER_API_KEY和ASTER_API_SECRET环境变量")
        return
    
    # 创建策略实例
    strategy = EMATunnelStrategyRealtime(
        exchange_name='aster',
        api_key=api_key,
        api_secret=api_secret,
        symbol='BTCUSDT',
        atr_period=14,
        atr_mult=2.0
    )
    
    # 添加信号回调
    def on_signal(signal: StrategySignal):
        print(f"信号: {signal.action} - {signal.reason}")
        print(f"4H趋势: {signal.htf_trend}, 15M信号: {signal.ltf_signal}")
        print(f"当前价格: {signal.current_price:.2f}")
        print("---")
    
    strategy.add_signal_callback(on_signal)
    
    # 启动策略
    try:
        strategy.start()
        
        # 保持运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n收到停止信号...")
        strategy.stop()
        print("策略已停止")


if __name__ == "__main__":
    main() 