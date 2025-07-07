#!/usr/bin/env python3
"""
BTC近半年EMA趋势策略回测脚本
分别测试三种止盈方式：
1、只使用固定止盈（3:1盈亏比）
2、只使用信号止盈
3、固定止盈和信号止盈相结合
"""
import pandas as pd
from strategies.ema_trend_strategy import EMATrendStrategy
from datetime import datetime, timedelta

def check_ema_triple_signal(df_15m):
    """
    检查15分钟13、21、55三条EMA的金叉/死叉信号
    与策略文件中的ltf_signal_realtime保持一致
    金叉：当前EMA13 > EMA21 > EMA55，且前一根EMA13 > EMA21，EMA21刚刚上穿EMA55
    死叉：当前EMA13 < EMA21 < EMA55，且前一根EMA13 < EMA21，EMA21刚刚下穿EMA55
    """
    if len(df_15m) < 55:
        return None
    
    ema13 = EMATrendStrategy.calc_ema(df_15m, 13)
    ema21 = EMATrendStrategy.calc_ema(df_15m, 21)
    ema55 = EMATrendStrategy.calc_ema(df_15m, 55)
    
    # 获取最新值和前一根值（倒数第二、三根）
    ema13_val, ema21_val, ema55_val = ema13.iloc[-2], ema21.iloc[-2], ema55.iloc[-2]
    ema13_prev, ema21_prev, ema55_prev = ema13.iloc[-3], ema21.iloc[-3], ema55.iloc[-3]

    # 三线金叉：21刚刚上穿55，且13已在21上方
    if (ema13_val > ema21_val > ema55_val and
        ema13_prev > ema21_prev and ema21_prev <= ema55_prev):
        return '金叉'
    # 三线死叉：21刚刚下穿55，且13已在21下方
    if (ema13_val < ema21_val < ema55_val and
        ema13_prev < ema21_prev and ema21_prev >= ema55_prev):
        return '死叉'
    return None

def htf_trend_filter(df_1h):
    """
    1小时趋势过滤：价格位于EMA200上方只做多，下方只做空
    """
    ema200 = EMATrendStrategy.calc_ema(df_1h, 200)
    current_price = df_1h['close'].iloc[-1]
    ema200_value = ema200.iloc[-1]
    if current_price > ema200_value:
        return '多头趋势'
    elif current_price < ema200_value:
        return '空头趋势'
    else:
        return '无明显趋势'

def atr_stop_and_take_profit_fast(df_15m, entry_price, direction, atr_period=14, atr_mult=3, risk_reward_ratio=2):
    """
    快速计算ATR止损价和止盈价，atr用15分钟K线
    """
    atr = EMATrendStrategy.calc_atr(df_15m, atr_period).iloc[-1]
    stop_distance = atr_mult * atr
    take_profit_distance = stop_distance * risk_reward_ratio
    if direction == 'long':
        stop_price = entry_price - stop_distance
        take_profit_price = entry_price + take_profit_distance
    else:
        stop_price = entry_price + stop_distance
        take_profit_price = entry_price - take_profit_distance
    return stop_price, take_profit_price, atr

def atr_stop_fast(df_15m, entry_price, direction, atr_period=14, atr_mult=3):
    """
    快速计算ATR止损价，atr用15分钟K线
    """
    atr = EMATrendStrategy.calc_atr(df_15m, atr_period).iloc[-1]
    stop_distance = atr_mult * atr
    if direction == 'long':
        stop_price = entry_price - stop_distance
    else:
        stop_price = entry_price + stop_distance
    return stop_price, atr

def run_backtest(df_15m, df_1h, ema13_15m, ema21_15m, ema55_15m, ema200_1h, strategy_name, use_fixed_tp=True, use_signal_tp=True):
    """
    运行回测
    :param use_fixed_tp: 是否使用固定止盈
    :param use_signal_tp: 是否使用信号止盈
    """
    capital = 100.0
    position = None
    trade_log = []
    
    # 策略参数
    leverage = 50
    risk_pct = 0.10  # 调整为10%
    atr_period = 14
    atr_mult = 3  # 修改为3倍ATR
    risk_reward_ratio = 3.0
    fee_rate = 0.0005  # 交易手续费率 0.05%
    
    signal_count = 0
    stop_loss_count = 0
    fixed_tp_count = 0
    signal_close_count = 0
    
    print(f"\n=== 开始回测策略: {strategy_name} ===")
    
    for i in range(100, len(df_15m)):
        current_time = df_15m.index[i]
        price = df_15m['close'].iloc[i]
        high_price = df_15m['high'].iloc[i]
        low_price = df_15m['low'].iloc[i]
        
        # 获取对应的1小时数据
        df_1h_window = df_1h[df_1h.index <= current_time]
        
        # 检查1小时趋势
        if len(df_1h_window) > 0:
            current_price_1h = df_1h_window['close'].iloc[-1]
            ema200_value = ema200_1h[df_1h_window.index[-1]] if df_1h_window.index[-1] in ema200_1h.index else 0
            
            if current_price_1h > ema200_value:
                htf_trend = '多头趋势'
            elif current_price_1h < ema200_value:
                htf_trend = '空头趋势'
            else:
                htf_trend = '无明显趋势'
        else:
            htf_trend = '无明显趋势'
        
        # 检查15分钟信号
        if i >= 1:
            ema13_val, ema21_val, ema55_val = ema13_15m.iloc[i], ema21_15m.iloc[i], ema55_15m.iloc[i]
            ema13_prev, ema21_prev, ema55_prev = ema13_15m.iloc[i-1], ema21_15m.iloc[i-1], ema55_15m.iloc[i-1]
            
            # 区分金叉/二次金叉、死叉/二次死叉
            if (ema13_val > ema21_val > ema55_val):
                if (ema13_prev > ema21_prev and ema21_prev <= ema55_prev):
                    ltf_signal = '金叉'
                elif (ema13_prev <= ema21_prev and ema21_prev > ema55_prev):
                    ltf_signal = '二次金叉'
                else:
                    ltf_signal = None
            elif (ema13_val < ema21_val < ema55_val):
                if (ema13_prev < ema21_prev and ema21_prev >= ema55_prev):
                    ltf_signal = '死叉'
                elif (ema13_prev >= ema21_prev and ema21_prev < ema55_prev):
                    ltf_signal = '二次死叉'
                else:
                    ltf_signal = None
            else:
                ltf_signal = None
        else:
            ltf_signal = None
        
        # 统计信号
        if ltf_signal in ['金叉', '二次金叉', '死叉', '二次死叉']:
            signal_count += 1
        
        # 平仓逻辑
        if position:
            close_reason = None
            close_price = price
            
            # 检查止损
            if position['direction'] == 'long':
                if low_price <= position['stop_price']:
                    close_reason = '止损'
                    close_price = position['stop_price']
                    stop_loss_count += 1
            else:
                if high_price >= position['stop_price']:
                    close_reason = '止损'
                    close_price = position['stop_price']
                    stop_loss_count += 1
            
            # 检查固定止盈
            if not close_reason and use_fixed_tp and 'take_profit_price' in position:
                if position['direction'] == 'long':
                    if high_price >= position['take_profit_price']:
                        close_reason = '固定止盈'
                        close_price = position['take_profit_price']
                        fixed_tp_count += 1
                else:
                    if low_price <= position['take_profit_price']:
                        close_reason = '固定止盈'
                        close_price = position['take_profit_price']
                        fixed_tp_count += 1
            
            # 检查信号平仓
            if not close_reason and use_signal_tp and ltf_signal:
                if position['direction'] == 'long' and ltf_signal == '死叉':
                    close_reason = '信号平仓'
                    close_price = price
                    signal_close_count += 1
                elif position['direction'] == 'short' and ltf_signal == '金叉':
                    close_reason = '信号平仓'
                    close_price = price
                    signal_close_count += 1
            
            # 执行平仓
            if close_reason:
                # 计算平仓手续费
                close_fee = close_price * position['quantity'] * fee_rate
                # 计算盈亏（包含开仓和平仓手续费）
                pnl = (close_price - position['entry_price']) * position['quantity'] * (1 if position['direction']=='long' else -1) - position['open_fee'] - close_fee
                capital += pnl
                trade_log.append({
                    'action': 'close',
                    'direction': position['direction'],
                    'entry_time': position['entry_time'],
                    'entry_price': position['entry_price'],
                    'close_time': current_time,
                    'close_price': close_price,
                    'quantity': position['quantity'],
                    'pnl': pnl,
                    'capital': capital,
                    'close_reason': close_reason
                })
                position = None
        
        # 保存当前信号类型
        current_signal_type = ltf_signal
        
        # 开仓逻辑
        open_long = (htf_trend == '多头趋势' and ltf_signal in ['金叉', '二次金叉'])
        open_short = (htf_trend == '空头趋势' and ltf_signal in ['死叉', '二次死叉'])

        if not position:
            if open_long:
                qty = capital * leverage * risk_pct / price
                
                # 计算开仓手续费
                open_fee = price * qty * fee_rate
                
                if use_fixed_tp:
                    stop_price, take_profit_price, atr = atr_stop_and_take_profit_fast(
                        df_15m.iloc[:i+1], price, 'long', atr_period, atr_mult, risk_reward_ratio
                    )
                    position = {
                        'direction': 'long',
                        'entry_price': price,
                        'quantity': qty,
                        'entry_time': current_time,
                        'stop_price': stop_price,
                        'take_profit_price': take_profit_price,
                        'open_fee': open_fee
                    }
                else:
                    stop_price, atr = atr_stop_fast(
                        df_15m.iloc[:i+1], price, 'long', atr_period, atr_mult
                    )
                    position = {
                        'direction': 'long',
                        'entry_price': price,
                        'quantity': qty,
                        'entry_time': current_time,
                        'stop_price': stop_price,
                        'open_fee': open_fee
                    }
                
                trade_log.append({
                    'action': 'open',
                    'direction': 'long',
                    'entry_time': current_time,
                    'entry_price': price,
                    'quantity': qty,
                    'capital': capital,
                    'stop_price': stop_price,
                    'atr': atr,
                    'signal_type': current_signal_type
                })
                
            elif open_short:
                qty = capital * leverage * risk_pct / price
                
                # 计算开仓手续费
                open_fee = price * qty * fee_rate
                
                if use_fixed_tp:
                    stop_price, take_profit_price, atr = atr_stop_and_take_profit_fast(
                        df_15m.iloc[:i+1], price, 'short', atr_period, atr_mult, risk_reward_ratio
                    )
                    position = {
                        'direction': 'short',
                        'entry_price': price,
                        'quantity': qty,
                        'entry_time': current_time,
                        'stop_price': stop_price,
                        'take_profit_price': take_profit_price,
                        'open_fee': open_fee
                    }
                else:
                    stop_price, atr = atr_stop_fast(
                        df_15m.iloc[:i+1], price, 'short', atr_period, atr_mult
                    )
                    position = {
                        'direction': 'short',
                        'entry_price': price,
                        'quantity': qty,
                        'entry_time': current_time,
                        'stop_price': stop_price,
                        'open_fee': open_fee
                    }
                
                trade_log.append({
                    'action': 'open',
                    'direction': 'short',
                    'entry_time': current_time,
                    'entry_price': price,
                    'quantity': qty,
                    'capital': capital,
                    'stop_price': stop_price,
                    'atr': atr,
                    'signal_type': current_signal_type
                })
    
    # 输出结果
    print(f"=== {strategy_name} 回测结果 ===")
    print(f"初始资金: 100 USDT")
    print(f"最终资金: {capital:.2f} USDT")
    print(f"总收益率: {((capital - 100) / 100 * 100):.2f}%")
    print(f"总交易次数: {len([t for t in trade_log if t['action']=='open'])}")
    print(f"总平仓次数: {len([t for t in trade_log if t['action']=='close'])}")
    print(f"止损次数: {stop_loss_count}")
    if use_fixed_tp:
        print(f"固定止盈次数: {fixed_tp_count}")
    if use_signal_tp:
        print(f"信号平仓次数: {signal_close_count}")
    
    # 统计各类信号分布
    df_log = pd.DataFrame([t for t in trade_log if t['action']=='open'])
    print("\n各类信号分布:")
    print(df_log['signal_type'].value_counts())

    # 统计每类信号的胜率和平均盈亏
    closes = [t for t in trade_log if t['action']=='close']
    df_closes = pd.DataFrame(closes)
    df_log = df_log.reset_index(drop=True)
    df_closes = df_closes.reset_index(drop=True)
    # 合并开仓和平仓信息
    result = pd.concat([
        df_log[['signal_type', 'direction', 'entry_time', 'entry_price', 'quantity']],
        df_closes[['close_price', 'pnl']]
    ], axis=1)
    grouped = result.groupby('signal_type')
    print('\n各类信号胜率/盈亏统计:')
    for name, group in grouped:
        win = group[group['pnl'] > 0].shape[0]
        total = group.shape[0]
        win_rate = win / total * 100 if total > 0 else 0
        avg_pnl = group['pnl'].mean()
        print(f'{name}: 开仓次数={total}, 胜率={win_rate:.1f}%, 平均盈亏={avg_pnl:.2f}')

    return {
        'strategy_name': strategy_name,
        'final_capital': capital,
        'return_rate': ((capital - 100) / 100 * 100),
        'total_trades': len([t for t in trade_log if t['action']=='open']),
        'stop_loss_count': stop_loss_count,
        'fixed_tp_count': fixed_tp_count if use_fixed_tp else 0,
        'signal_close_count': signal_close_count if use_signal_tp else 0,
        'trade_log': trade_log
    }

# 主程序
if __name__ == "__main__":
    # 1. 读取历史K线数据
    print("正在加载K线数据...")
    df_1h = pd.read_csv('kline_cache/BTCUSDT_1h.csv', index_col='open_time')
    df_15m = pd.read_csv('kline_cache/BTCUSDT_15m.csv', index_col='open_time')

    # 2. 取近半年的数据
    end_time = df_15m.index[-1]
    end_dt = datetime.fromtimestamp(end_time/1000) if end_time > 1e10 else datetime.fromtimestamp(end_time)
    start_dt = end_dt - timedelta(days=180)
    start_time = int(start_dt.timestamp() * 1000)
    df_15m = df_15m[df_15m.index >= start_time]
    df_1h = df_1h[df_1h.index >= start_time]

    # 3. 预计算所有指标
    print("正在预计算技术指标...")
    ema13_15m = EMATrendStrategy.calc_ema(df_15m, 13)
    ema21_15m = EMATrendStrategy.calc_ema(df_15m, 21)
    ema55_15m = EMATrendStrategy.calc_ema(df_15m, 55)
    ema200_1h = EMATrendStrategy.calc_ema(df_1h, 200)

    print('15m最早K线:', datetime.fromtimestamp(df_15m.index[0]/1000))
    print('15m最晚K线:', datetime.fromtimestamp(df_15m.index[-1]/1000))
    print('15m K线数量:', len(df_15m))
    print('1h K线数量:', len(df_1h))

    # 4. 运行三种策略的回测
    results = []
    
    # 策略1：只使用固定止盈（3:1盈亏比）
    result1 = run_backtest(df_15m, df_1h, ema13_15m, ema21_15m, ema55_15m, ema200_1h, 
                          "策略1: 只使用固定止盈(3:1)", use_fixed_tp=True, use_signal_tp=False)
    results.append(result1)
    
    # 策略2：只使用信号止盈
    result2 = run_backtest(df_15m, df_1h, ema13_15m, ema21_15m, ema55_15m, ema200_1h, 
                          "策略2: 只使用信号止盈", use_fixed_tp=False, use_signal_tp=True)
    results.append(result2)
    
    # 策略3：固定止盈和信号止盈相结合
    result3 = run_backtest(df_15m, df_1h, ema13_15m, ema21_15m, ema55_15m, ema200_1h, 
                          "策略3: 固定止盈+信号止盈", use_fixed_tp=True, use_signal_tp=True)
    results.append(result3)

    # 5. 对比分析
    print(f"\n{'='*60}")
    print("策略对比分析")
    print(f"{'='*60}")
    print(f"{'策略名称':<20} {'最终资金':<10} {'收益率':<10} {'交易次数':<10} {'止损':<8} {'固定止盈':<10} {'信号平仓':<10}")
    print(f"{'-'*60}")
    
    for result in results:
        print(f"{result['strategy_name']:<20} "
              f"{result['final_capital']:<10.2f} "
              f"{result['return_rate']:<10.2f}% "
              f"{result['total_trades']:<10} "
              f"{result['stop_loss_count']:<8} "
              f"{result['fixed_tp_count']:<10} "
              f"{result['signal_close_count']:<10}")
    
    # 找出最佳策略
    best_strategy = max(results, key=lambda x: x['final_capital'])
    print(f"\n🏆 最佳策略: {best_strategy['strategy_name']}")
    print(f"   最终资金: {best_strategy['final_capital']:.2f} USDT")
    print(f"   收益率: {best_strategy['return_rate']:.2f}%")
    
    # 保存详细交易记录
    for result in results:
        if result['trade_log']:
            df_log = pd.DataFrame(result['trade_log'])
            filename = f"backtest_{result['strategy_name'].replace(':', '').replace(' ', '_')}.csv"
            df_log.to_csv(filename, index=False)
            print(f"交易记录已保存到: {filename}")
    
    print(f"\n半年内共检测到{len([i for i in range(100, len(df_15m)) if i >= 1 and 
        (ema13_15m.iloc[i] > ema21_15m.iloc[i] > ema55_15m.iloc[i] and 
         ema13_15m.iloc[i-1] > ema21_15m.iloc[i-1] and ema21_15m.iloc[i-1] <= ema55_15m.iloc[i-1]) or
        (ema13_15m.iloc[i] < ema21_15m.iloc[i] < ema55_15m.iloc[i] and 
         ema13_15m.iloc[i-1] < ema21_15m.iloc[i-1] and ema21_15m.iloc[i-1] >= ema55_15m.iloc[i-1])])}次15分钟三条EMA金叉/死叉信号") 