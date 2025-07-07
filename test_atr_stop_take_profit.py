import pandas as pd
from strategies.ema_trend_strategy import EMATrendStrategy

# 读取本地1分钟K线数据
kline_path = 'kline_cache/BTCUSDT_1m.csv'
df_1m = pd.read_csv(kline_path)

# 取最新一根K线的收盘价作为入场价
entry_price = df_1m['close'].iloc[-1]
print(f"最新K线收盘价（入场价）: {entry_price}")

# 实例化策略对象
strategy = EMATrendStrategy()

print("\n=== 测试多单止损/止盈 ===")
strategy.atr_stop_and_take_profit(df_1m, entry_price, 'long')

print("\n=== 测试空单止损/止盈 ===")
strategy.atr_stop_and_take_profit(df_1m, entry_price, 'short') 