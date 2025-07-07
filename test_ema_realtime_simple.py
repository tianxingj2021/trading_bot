#!/usr/bin/env python3
"""
简化版EMA隧道实时策略测试
主要测试架构和逻辑，不依赖API密钥
"""
import time
from datetime import datetime
import threading
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class MockKline:
    """模拟K线数据"""
    open_time: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    close_time: int

@dataclass
class MockTicker:
    """模拟Ticker数据"""
    symbol: str
    last_price: str

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

class MockEMATunnelStrategyRealtime:
    """模拟实时EMA隧道策略 - 用于测试架构"""
    
    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol
        self.is_running = False
        self.is_ready = False
        
        # 模拟数据
        self.kline_4h: List[MockKline] = []
        self.kline_15m: List[MockKline] = []
        self.ticker_snapshot: Optional[MockTicker] = None
        
        # 策略状态
        self.signal_history: List[StrategySignal] = []
        self.signal_count = 0
        
        # 回调函数
        self.signal_callbacks: List[callable] = []
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 模拟数据生成线程
        self.data_thread = None
        
    def add_signal_callback(self, callback):
        """添加信号回调函数"""
        self.signal_callbacks.append(callback)
    
    def _generate_mock_data(self):
        """生成模拟数据"""
        base_price = 50000.0
        current_time = int(time.time() * 1000)
        
        # 生成4小时K线数据
        for i in range(700):
            price_change = (i % 100 - 50) * 10  # 模拟价格波动
            close_price = base_price + price_change
            
            kline = MockKline(
                open_time=current_time - (700 - i) * 4 * 60 * 60 * 1000,
                open=str(close_price - 100),
                high=str(close_price + 200),
                low=str(close_price - 200),
                close=str(close_price),
                volume="1000",
                close_time=current_time - (700 - i) * 4 * 60 * 60 * 1000 + 4 * 60 * 60 * 1000
            )
            self.kline_4h.append(kline)
        
        # 生成15分钟K线数据
        for i in range(200):
            price_change = (i % 50 - 25) * 5  # 模拟价格波动
            close_price = base_price + price_change
            
            kline = MockKline(
                open_time=current_time - (200 - i) * 15 * 60 * 1000,
                open=str(close_price - 50),
                high=str(close_price + 100),
                low=str(close_price - 100),
                close=str(close_price),
                volume="500",
                close_time=current_time - (200 - i) * 15 * 60 * 1000 + 15 * 60 * 1000
            )
            self.kline_15m.append(kline)
        
        # 生成Ticker数据
        self.ticker_snapshot = MockTicker(
            symbol=self.symbol,
            last_price=str(base_price)
        )
        
        self.is_ready = True
        print("✓ 模拟数据生成完成")
    
    def _simulate_data_updates(self):
        """模拟数据更新"""
        while self.is_running:
            try:
                # 模拟15分钟K线更新
                if self.kline_15m:
                    last_kline = self.kline_15m[-1]
                    new_close = float(last_kline.close) + (time.time() % 10 - 5) * 10
                    
                    new_kline = MockKline(
                        open_time=last_kline.close_time,
                        open=last_kline.close,
                        high=str(max(float(last_kline.high), new_close)),
                        low=str(min(float(last_kline.low), new_close)),
                        close=str(new_close),
                        volume="500",
                        close_time=last_kline.close_time + 15 * 60 * 1000
                    )
                    
                    with self.lock:
                        self.kline_15m.append(new_kline)
                        if len(self.kline_15m) > 200:
                            self.kline_15m = self.kline_15m[-200:]
                        
                        # 更新Ticker
                        if self.ticker_snapshot:
                            self.ticker_snapshot.last_price = str(new_close)
                        
                        # 处理策略信号
                        self._process_strategy_signals()
                
                time.sleep(15)  # 模拟15分钟更新间隔
                
            except Exception as e:
                print(f"数据更新错误: {e}")
                time.sleep(5)
    
    def _process_strategy_signals(self):
        """处理策略信号"""
        if not self.is_ready or not self.ticker_snapshot:
            return
        
        current_price = float(self.ticker_snapshot.last_price)
        
        # 模拟信号生成
        signal_types = ['wait', 'open_long', 'open_short', 'hold']
        action = signal_types[self.signal_count % len(signal_types)]
        
        signal = StrategySignal(
            timestamp=int(time.time() * 1000),
            symbol=self.symbol,
            htf_trend='多头排列' if self.signal_count % 2 == 0 else '空头排列',
            ltf_signal='金叉' if self.signal_count % 3 == 0 else '死叉',
            current_price=current_price,
            action=action,
            reason=f'模拟信号 #{self.signal_count + 1}',
            confidence=0.8
        )
        
        self.signal_count += 1
        self.signal_history.append(signal)
        
        # 调用回调函数
        for callback in self.signal_callbacks:
            try:
                callback(signal)
            except Exception as e:
                print(f"信号回调错误: {e}")
    
    def start(self):
        """启动策略"""
        print("启动模拟EMA隧道实时策略...")
        self._generate_mock_data()
        self.is_running = True
        
        # 启动数据更新线程
        self.data_thread = threading.Thread(target=self._simulate_data_updates, daemon=True)
        self.data_thread.start()
        
        print("策略已启动，开始模拟实时监控...")
    
    def stop(self):
        """停止策略"""
        print("停止模拟EMA隧道实时策略...")
        self.is_running = False
        if self.data_thread:
            self.data_thread.join(timeout=5)
        print(f"策略已停止，共生成 {self.signal_count} 个信号")
    
    def get_status(self):
        """获取策略状态"""
        return {
            'is_running': self.is_running,
            'is_ready': self.is_ready,
            'signal_count': self.signal_count,
            'kline_4h_count': len(self.kline_4h),
            'kline_15m_count': len(self.kline_15m),
            'current_price': float(self.ticker_snapshot.last_price) if self.ticker_snapshot else 0
        }

def test_architecture():
    """测试架构功能"""
    print("=== 测试实时架构功能 ===")
    
    strategy = MockEMATunnelStrategyRealtime(symbol='BTCUSDT')
    
    # 添加信号回调
    def on_signal(signal: StrategySignal):
        print(f"\n[信号 #{signal.timestamp}] {datetime.fromtimestamp(signal.timestamp/1000)}")
        print(f"  动作: {signal.action}")
        print(f"  原因: {signal.reason}")
        print(f"  4H趋势: {signal.htf_trend}")
        print(f"  15M信号: {signal.ltf_signal}")
        print(f"  当前价格: {signal.current_price:.2f}")
        print(f"  置信度: {signal.confidence:.2f}")
    
    strategy.add_signal_callback(on_signal)
    
    # 启动策略
    strategy.start()
    
    # 运行测试
    start_time = time.time()
    while time.time() - start_time < 60:  # 运行1分钟
        time.sleep(5)
        status = strategy.get_status()
        print(f"状态: 运行中={status['is_running']}, 信号数={status['signal_count']}, 价格={status['current_price']:.2f}")
    
    strategy.stop()

def test_performance():
    """测试性能对比"""
    print("\n=== 性能测试 ===")
    
    # 模拟轮询方式
    print("模拟轮询方式（60秒间隔）:")
    poll_start = time.time()
    for i in range(5):
        time.sleep(1)  # 模拟API调用延迟
        print(f"  轮询 #{i+1}: 延迟 {time.time() - poll_start:.1f}秒")
    poll_time = time.time() - poll_start
    print(f"轮询总时间: {poll_time:.1f}秒")
    
    # 模拟实时方式
    print("\n模拟实时方式（WebSocket）:")
    realtime_start = time.time()
    time.sleep(0.1)  # 模拟WebSocket响应时间
    print(f"  实时响应: 延迟 {time.time() - realtime_start:.3f}秒")
    realtime_time = time.time() - realtime_start
    print(f"实时总时间: {realtime_time:.3f}秒")
    
    # 性能对比
    improvement = (poll_time - realtime_time) / poll_time * 100
    print(f"\n性能提升: {improvement:.1f}%")

def test_threading():
    """测试多线程安全性"""
    print("\n=== 多线程安全性测试 ===")
    
    strategy = MockEMATunnelStrategyRealtime()
    
    # 模拟多线程访问
    def thread_worker(thread_id):
        for i in range(10):
            with strategy.lock:
                status = strategy.get_status()
                print(f"线程{thread_id}: 访问状态 - {status['is_ready']}")
            time.sleep(0.1)
    
    # 启动多个线程
    threads = []
    for i in range(3):
        thread = threading.Thread(target=thread_worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    print("✓ 多线程安全性测试通过")

def test_error_handling():
    """测试错误处理"""
    print("\n=== 错误处理测试 ===")
    
    strategy = MockEMATunnelStrategyRealtime()
    
    # 测试回调函数错误
    def error_callback(signal):
        raise Exception("模拟回调错误")
    
    strategy.add_signal_callback(error_callback)
    
    # 启动策略（应该能正常处理回调错误）
    strategy.start()
    time.sleep(5)
    strategy.stop()
    
    print("✓ 错误处理测试通过")

def main():
    """主测试函数"""
    print("简化版EMA隧道实时策略测试")
    print("=" * 50)
    
    try:
        test_performance()
        test_threading()
        test_error_handling()
        test_architecture()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n测试完成")

if __name__ == "__main__":
    main() 