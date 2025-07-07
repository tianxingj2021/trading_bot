#!/usr/bin/env python3
"""
测试网络错误处理机制
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ema_trend_backpack_trader import EMATrendBackpackTrader
import time

def test_network_error_handling():
    """测试网络错误处理"""
    print("=== 测试网络错误处理机制 ===")
    
    # 创建交易程序实例
    trader = EMATrendBackpackTrader()
    
    # 测试网络错误检测
    print("\n1. 测试网络错误检测...")
    import requests
    import socket
    
    # 测试各种网络错误
    test_errors = [
        requests.exceptions.ConnectionError("Connection failed"),
        requests.exceptions.Timeout("Request timeout"),
        socket.error("Socket error"),
        BrokenPipeError("Broken pipe"),
        ConnectionResetError("Connection reset"),
        OSError("OS error")
    ]
    
    for error in test_errors:
        is_network = trader.is_network_error(error)
        print(f"  {type(error).__name__}: {'是' if is_network else '否'} 网络错误")
    
    # 测试安全API调用
    print("\n2. 测试安全API调用...")
    
    def mock_api_call():
        """模拟API调用"""
        import random
        if random.random() < 0.7:  # 70%概率失败
            raise requests.exceptions.ConnectionError("模拟网络错误")
        return "API调用成功"
    
    try:
        result = trader.safe_api_call(mock_api_call)
        print(f"  结果: {result}")
    except Exception as e:
        print(f"  最终失败: {e}")
    
    print("\n3. 测试账户状态检查...")
    try:
        trader.check_account_status()
        print("  账户状态检查完成")
    except Exception as e:
        print(f"  账户状态检查失败: {e}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_network_error_handling() 