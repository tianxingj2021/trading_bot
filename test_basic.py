"""
基本功能测试
"""
import unittest
from utils.helper import get_sma30, to_price_1_decimal, to_qty_3_decimal
from utils.order import calc_stop_loss_price, calc_trailing_activation_price


class TestHelperFunctions(unittest.TestCase):
    """测试辅助函数"""
    
    def test_to_price_1_decimal(self):
        """测试价格保留1位小数"""
        self.assertEqual(to_price_1_decimal(123.456), 123.4)
        self.assertEqual(to_price_1_decimal(123.789), 123.7)
        self.assertEqual(to_price_1_decimal(123.0), 123.0)
    
    def test_to_qty_3_decimal(self):
        """测试数量保留3位小数"""
        self.assertEqual(to_qty_3_decimal(0.123456), 0.123)
        self.assertEqual(to_qty_3_decimal(0.123789), 0.123)
        self.assertEqual(to_qty_3_decimal(0.123), 0.123)
    
    def test_get_sma30(self):
        """测试SMA30计算"""
        # 模拟K线数据
        klines = []
        for i in range(35):
            klines.append({
                'close': str(100 + i)  # 100, 101, 102, ..., 134
            })
        
        sma = get_sma30(klines)
        expected = sum(range(105, 135)) / 30  # 最近30个收盘价的平均值
        self.assertAlmostEqual(sma, expected, places=2)
    
    def test_calc_stop_loss_price(self):
        """测试止损价格计算"""
        # 多头止损
        stop_price = calc_stop_loss_price(100, 1, "long", 10)
        self.assertEqual(stop_price, 90)  # 100 - 10/1 = 90
        
        # 空头止损
        stop_price = calc_stop_loss_price(100, 1, "short", 10)
        self.assertEqual(stop_price, 110)  # 100 + 10/1 = 110
    
    def test_calc_trailing_activation_price(self):
        """测试动态止盈激活价格计算"""
        # 多头激活价格
        activation_price = calc_trailing_activation_price(100, 1, "long", 10)
        self.assertEqual(activation_price, 110)  # 100 + 10/1 = 110
        
        # 空头激活价格
        activation_price = calc_trailing_activation_price(100, 1, "short", 10)
        self.assertEqual(activation_price, 90)  # 100 - 10/1 = 90


if __name__ == "__main__":
    unittest.main() 