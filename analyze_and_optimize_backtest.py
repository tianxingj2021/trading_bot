#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from strategies.ema_tunnel_strategy import EMATunnelStrategy
from datetime import datetime, timedelta
import mplfinance as mpf
import os

# 1. 读取回测日志
log_file = 'backtest_ema_tunnel_log.csv'
df = pd.read_csv(log_file)

# 2. 资金曲线
plt.figure(figsize=(12, 6))
plt.plot(df[df['action'] == 'close']['close_time'], df[df['action'] == 'close']['capital'], marker='o')
plt.title('资金曲线')
plt.xlabel('时间')
plt.ylabel('资金 (USDT)')
plt.xticks(rotation=30)
plt.grid(True)
plt.tight_layout()
plt.savefig('equity_curve.png')
plt.close()

# 3. 每笔盈亏分布
plt.figure(figsize=(10, 5))
pnl = df[df['action'] == 'close']['pnl']
plt.hist(pnl, bins=30, color='skyblue', edgecolor='k')
plt.title('每笔交易盈亏分布')
plt.xlabel('盈亏 (USDT)')
plt.ylabel('频数')
plt.tight_layout()
plt.savefig('pnl_hist.png')
plt.close()

# 4. 基础统计
print('总交易次数:', len(pnl))
print('胜率:', (pnl > 0).sum() / len(pnl) if len(pnl) > 0 else 0)
capital_curve = df[df['action'] == 'close']['capital']
max_drawdown = (capital_curve.cummax() - capital_curve).max() if len(capital_curve) > 0 else 0
print('最大回撤:', max_drawdown)
print('总收益:', capital_curve.iloc[-1] - capital_curve.iloc[0] if len(capital_curve) > 1 else 0)
print('夏普比率:', pnl.mean() / pnl.std() * (len(pnl) ** 0.5) if pnl.std() > 0 and len(pnl) > 0 else 'N/A')

# 5. 参数优化（遍历ATR倍数和风险比例）
def run_backtest(atr_mult, risk_pct):
    # 读取K线
    df_4h = pd.read_csv('kline_cache/BTCUSDT_4h.csv', index_col='open_time')
    df_15m = pd.read_csv('kline_cache/BTCUSDT_15m.csv', index_col='open_time')
    end_time = df_15m.index[-1]
    end_dt = datetime.fromtimestamp(end_time/1000) if end_time > 1e10 else datetime.fromtimestamp(end_time)
    start_dt = end_dt - timedelta(days=180)
    start_time = int(start_dt.timestamp() * 1000)
    df_15m = df_15m[df_15m.index >= start_time]
    df_4h = df_4h[df_4h.index >= start_time]
    strat = EMATunnelStrategy(atr_mult=atr_mult)
    capital = 100.0
    position = None
    for i in range(100, len(df_15m)):
        df_15m_window = df_15m.iloc[:i+1]
        current_time = df_15m_window.index[-1]
        df_4h_window = df_4h[df_4h.index <= current_time]
        price = df_15m_window['close'].iloc[-1]
        htf_trend = strat.htf_trend(df_4h_window)
        ltf_signal = strat.ltf_signal_confirmed(df_15m_window)
        if position:
            close_long = (position['direction']=='long' and (htf_trend=='空头排列' or ltf_signal=='死叉'))
            close_short = (position['direction']=='short' and (htf_trend=='多头排列' or ltf_signal=='金叉'))
            if close_long or close_short:
                close_price = price
                pnl = (close_price - position['entry_price']) * position['quantity'] * (1 if position['direction']=='long' else -1)
                capital += pnl
                position = None
        if not position:
            if htf_trend == '多头排列' and ltf_signal == '金叉':
                qty = capital / price
                position = {'direction': 'long', 'entry_price': price, 'quantity': qty, 'entry_time': current_time}
            elif htf_trend == '空头排列' and ltf_signal == '死叉':
                qty = capital / price
                position = {'direction': 'short', 'entry_price': price, 'quantity': qty, 'entry_time': current_time}
    return capital

print('\n参数优化结果:')
best_result = None
best_params = None
for atr_mult in [1.5, 2, 2.5, 3]:
    for risk_pct in [0.01, 0.02, 0.05]:
        final_capital = run_backtest(atr_mult, risk_pct)
        print(f'ATR倍数: {atr_mult}, 风险比例: {risk_pct}, 最终资金: {final_capital:.2f}')
        if best_result is None or final_capital > best_result:
            best_result = final_capital
            best_params = (atr_mult, risk_pct)
print('最优参数:', best_params, '最大资金:', best_result)

# 6. K线与信号可视化（仅展示近1000根15mK线）
def plot_kline_with_signals():
    df_15m = pd.read_csv('kline_cache/BTCUSDT_15m.csv', index_col='open_time')
    df_15m = df_15m.iloc[-1000:]
    df_log = df[df['action'].isin(['open', 'close'])]
    df_log = df_log[-20:]  # 只展示最近20笔
    # 构造信号点
    opens = df_log[df_log['action']=='open']
    closes = df_log[df_log['action']=='close']
    apds = []
    if not opens.empty:
        apds.append(mpf.make_addplot(opens.set_index('entry_time')['entry_price'], type='scatter', markersize=80, marker='^', color='g'))
    if not closes.empty:
        apds.append(mpf.make_addplot(closes.set_index('close_time')['close_price'], type='scatter', markersize=80, marker='v', color='r'))
    df_ohlc = df_15m[['open','high','low','close']]
    df_ohlc.index = pd.to_datetime(df_ohlc.index, unit='ms')
    mpf.plot(df_ohlc, type='candle', style='charles', addplot=apds, title='BTCUSDT 15m K线与开/平仓信号', volume=False, savefig='kline_signals.png')

try:
    plot_kline_with_signals()
    print('K线与信号图已保存为 kline_signals.png')
except Exception as e:
    print('K线信号可视化失败:', e) 