#!/usr/bin/env python3
import pandas as pd
from datetime import datetime

for fname in ['kline_cache/BTCUSDT_4h.csv', 'kline_cache/BTCUSDT_15m.csv']:
    print(f'检查文件: {fname}')
    df = pd.read_csv(fname)
    if 'open_time' not in df.columns:
        print('未找到open_time列')
        continue
    times = pd.to_datetime(df['open_time'], unit='ms')
    print(f'最早K线: {times.min()}')
    print(f'最晚K线: {times.max()}')
    print(f'总条数: {len(df)}')
    print('-'*40) 