#!/usr/bin/env python3
"""
测试币安U本位合约API基础功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from exchanges.binance import Binance

def test_binance_basic():
    """测试币安基础功能"""
    print("=== 币安U本位合约API测试 ===")
    
    # 初始化币安API（使用测试网或空密钥进行公开接口测试）
    # 注意：这里使用空密钥，只能测试公开接口
    binance = Binance(api_key="", api_secret="")
    
    try:
        # 1. 测试获取所有交易对
        print("\n1. 获取所有U本位合约交易对...")
        symbols = binance.get_all_symbols()
        print(f"获取到 {len(symbols)} 个交易对")
        print("前10个交易对:", symbols[:10])
        
        # 2. 测试获取BTCUSDT的深度数据
        print("\n2. 获取BTCUSDT深度数据...")
        depth = binance.get_depth("BTCUSDT", limit=5)
        print(f"交易对: {depth.symbol}")
        print(f"最后更新ID: {depth.last_update_id}")
        print("买盘前5档:")
        for i, bid in enumerate(depth.bids[:5]):
            print(f"  {i+1}. 价格: {bid.price}, 数量: {bid.quantity}")
        print("卖盘前5档:")
        for i, ask in enumerate(depth.asks[:5]):
            print(f"  {i+1}. 价格: {ask.price}, 数量: {ask.quantity}")
        
        # 3. 测试获取BTCUSDT的Ticker数据
        print("\n3. 获取BTCUSDT Ticker数据...")
        ticker = binance.get_ticker("BTCUSDT")
        print(f"交易对: {ticker.symbol}")
        print(f"最新价格: {ticker.last_price}")
        print(f"开盘价: {ticker.open_price}")
        print(f"最高价: {ticker.high_price}")
        print(f"最低价: {ticker.low_price}")
        print(f"24h成交量: {ticker.volume}")
        print(f"24h涨跌幅: {ticker.price_change_percent}%")
        
        # 4. 测试获取BTCUSDT的K线数据
        print("\n4. 获取BTCUSDT 1分钟K线数据...")
        klines = binance.get_klines("BTCUSDT", "1m", limit=5)
        print(f"获取到 {len(klines)} 根K线")
        for i, kline in enumerate(klines):
            print(f"K线 {i+1}:")
            print(f"  开盘时间: {kline.open_time}")
            print(f"  开盘价: {kline.open}")
            print(f"  最高价: {kline.high}")
            print(f"  最低价: {kline.low}")
            print(f"  收盘价: {kline.close}")
            print(f"  成交量: {kline.volume}")
        
        # 5. 测试获取交易对信息
        print("\n5. 获取BTCUSDT交易对信息...")
        try:
            symbol_info = binance.get_symbol_info("BTCUSDT")
            print(f"交易对: {symbol_info.get('symbol')}")
            print(f"状态: {symbol_info.get('status')}")
            print(f"基础资产: {symbol_info.get('baseAsset')}")
            print(f"计价资产: {symbol_info.get('quoteAsset')}")
            
            # 获取精度信息
            for filter_info in symbol_info.get('filters', []):
                if filter_info['filterType'] == 'LOT_SIZE':
                    print(f"最小下单量: {filter_info['minQty']}")
                    print(f"数量步长: {filter_info['stepSize']}")
                elif filter_info['filterType'] == 'PRICE_FILTER':
                    print(f"价格精度: {filter_info['tickSize']}")
        except Exception as e:
            print(f"获取交易对信息失败: {e}")
        
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_binance_basic() 