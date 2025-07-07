#!/usr/bin/env python3
"""
自动从币安获取BTCUSDT近半年4小时和15分钟K线数据，保存到本地csv，自动补全缺失部分
"""
import pandas as pd
import time
from datetime import datetime, timedelta
from exchanges.binance import Binance
import os

symbol = 'BTCUSDT'
intervals = ['4h', '15m', '1m', '1h']
cache_dir = 'kline_cache'
os.makedirs(cache_dir, exist_ok=True)

# 获取近半年的起止时间戳
end_dt = datetime.utcnow()
start_dt = end_dt - timedelta(days=180)
end_time = int(time.mktime(end_dt.timetuple())) * 1000
start_time = int(time.mktime(start_dt.timetuple())) * 1000

print(f"开始时间: {datetime.fromtimestamp(start_time/1000)}")
print(f"结束时间: {datetime.fromtimestamp(end_time/1000)}")

binance = Binance(api_key="", api_secret="")

for interval in intervals:
    print(f"\n正在获取 {symbol} {interval} 近半年K线...")
    klines = []
    limit = 1000  # 币安单次最大返回
    ts = start_time
    retry_count = 0
    max_retries = 3
    
    while ts < end_time and retry_count < max_retries:
        try:
            data = binance.get_klines_with_time(symbol, interval, limit=limit, startTime=ts, endTime=end_time)
            if not data:
                print(f"未获取到数据，重试 {retry_count + 1}/{max_retries}")
                retry_count += 1
                time.sleep(1)
                continue
                
            for k in data:
                klines.append({
                    'open_time': k.open_time,
                    'open': float(k.open),
                    'high': float(k.high),
                    'low': float(k.low),
                    'close': float(k.close),
                    'volume': float(k.volume),
                    'close_time': k.close_time
                })
            
            # 下一个窗口
            last_close_time = data[-1].close_time
            if ts >= last_close_time:
                print('检测到时间未推进，强制跳出，防止死循环')
                break
            ts = last_close_time + 1
            
            if len(data) < limit:
                print(f"获取到 {len(data)} 条数据，小于限制 {limit}，数据获取完成")
                break
                
            print(f"已获取 {len(klines)} 条数据，当前时间: {datetime.fromtimestamp(ts/1000)}")
            time.sleep(0.1)  # 防止频率过高
            
        except Exception as e:
            print(f"获取数据出错: {e}，重试 {retry_count + 1}/{max_retries}")
            retry_count += 1
            time.sleep(2)
    
    if retry_count >= max_retries:
        print(f"获取 {interval} 数据失败，重试次数已达上限")
        continue
        
    # 合并去重，按open_time排序
    df = pd.DataFrame(klines)
    if len(df) == 0:
        print(f"未获取到 {interval} 数据")
        continue
        
    df = df.drop_duplicates(subset=['open_time'])
    df = df.sort_values('open_time')
    
    # 检查数据完整性
    expected_count = 0
    if interval == '4h':
        expected_count = 180 * 24 // 4  # 半年约180天，每天6根4小时K线
    elif interval == '15m':
        expected_count = 180 * 24 * 4  # 半年约180天，每天96根15分钟K线
    elif interval == '1h':
        expected_count = 180 * 24  # 半年约180天，每天24根1小时K线
    elif interval == '1m':
        expected_count = 180 * 24 * 60  # 半年约180天，每天1440根1分钟K线
    
    print(f"预期 {interval} K线数量: {expected_count}")
    print(f"实际获取 {interval} K线数量: {len(df)}")
    
    # 保存数据
    filename = f'{cache_dir}/{symbol}_{interval}.csv'
    df.to_csv(filename, index=False)
    print(f"已保存 {filename}, 共{len(df)}条")
    
    # 显示时间范围
    if len(df) > 0:
        start_dt_str = datetime.fromtimestamp(df['open_time'].min()/1000)
        end_dt_str = datetime.fromtimestamp(df['open_time'].max()/1000)
        print(f"数据时间范围: {start_dt_str} 到 {end_dt_str}")

print("\n数据获取完成！") 