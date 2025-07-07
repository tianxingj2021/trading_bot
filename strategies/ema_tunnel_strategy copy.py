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

class EMATunnelStrategy:
    binance = Binance(api_key="", api_secret="")
    kline_cache_dir = "kline_cache"

    def __init__(self, atr_period=14, atr_mult=2):
        self.atr_period = atr_period
        self.atr_mult = atr_mult

    @staticmethod
    def calc_ema(df, period):
        return df['close'].ewm(span=period, adjust=False).mean()

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

    def ltf_signal(self, df_15m):
        """
        判断15分钟金叉/死叉信号
        返回: '金叉'/'死叉'/None
        """
        ema13 = self.calc_ema(df_15m, 13)
        ema34 = self.calc_ema(df_15m, 34)
        if ema13.iloc[-2] < ema34.iloc[-2] and ema13.iloc[-1] > ema34.iloc[-1]:
            return '金叉'
        elif ema13.iloc[-2] > ema34.iloc[-2] and ema13.iloc[-1] < ema34.iloc[-1]:
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
        满足4小时多头排列+15分钟金叉
        """
        return self.htf_trend(df_4h) == '多头排列' and self.ltf_signal(df_15m) == '金叉'

    def should_open_short(self, df_4h, df_15m):
        """
        满足4小时空头排列+15分钟死叉
        """
        return self.htf_trend(df_4h) == '空头排列' and self.ltf_signal(df_15m) == '死叉'

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
        return size

    @staticmethod
    def get_binance_klines(symbol, interval, limit=1500):
        """
        获取币安K线数据，支持本地缓存，自动补齐缺失部分
        """
        os.makedirs(EMATunnelStrategy.kline_cache_dir, exist_ok=True)
        cache_file = os.path.join(EMATunnelStrategy.kline_cache_dir, f"{symbol}_{interval}.csv")
        df = None
        latest_open_time = None
        # 1. 先尝试加载本地缓存
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, index_col='open_time')
            df.index = df.index.astype(int)
            if len(df) > 0:
                latest_open_time = df.index.max()
        # 2. 判断是否需要补充新数据
        if df is None or len(df) < limit:
            # 直接拉取limit根
            klines = EMATunnelStrategy.binance.get_klines(symbol, interval, limit=limit)
            new_df = pd.DataFrame([{ 'open_time': k.open_time, 'open': float(k.open), 'high': float(k.high), 'low': float(k.low), 'close': float(k.close), 'volume': float(k.volume), 'close_time': k.close_time } for k in klines])
            new_df.set_index('open_time', inplace=True)
            df = new_df
        else:
            # 只补充最新部分
            klines = EMATunnelStrategy.binance.get_klines(symbol, interval, limit=500)
            new_df = pd.DataFrame([{ 'open_time': k.open_time, 'open': float(k.open), 'high': float(k.high), 'low': float(k.low), 'close': float(k.close), 'volume': float(k.volume), 'close_time': k.close_time } for k in klines])
            new_df.set_index('open_time', inplace=True)
            # 只保留本地没有的部分
            new_df = new_df[~new_df.index.isin(df.index)]
            if len(new_df) > 0:
                df = pd.concat([df, new_df])
                df = df[~df.index.duplicated(keep='last')]
                df = df.sort_index()
        # 3. 截断为limit根
        if len(df) > limit:
            df = df.iloc[-limit:]
        # 4. 保存最新缓存
        df.to_csv(cache_file)
        return df 