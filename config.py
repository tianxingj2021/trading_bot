"""
配置文件
"""
import os
from dotenv import load_dotenv

load_dotenv()

# 交易配置
TRADE_SYMBOL = "BTCUSDT"
TRADE_AMOUNT = 0.001
ARB_THRESHOLD = 80
CLOSE_DIFF = 3  # 3U
PROFIT_DIFF_LIMIT = 1  # 平仓时两个交易所收益差额阈值，单位USDT
LOSS_LIMIT = 0.03  # 单笔最大亏损USDT
STOP_LOSS_DIST = 0.1  # 止损距离USDT
TRAILING_PROFIT = 0.2  # 动态止盈激活利润USDT
TRAILING_CALLBACK_RATE = 0.2  # 动态止盈回撤百分比

# API配置
ASTER_API_KEY = os.getenv("ASTER_API_KEY", "")
ASTER_API_SECRET = os.getenv("ASTER_API_SECRET", "")
BITGET_API_KEY = os.getenv("BITGET_API_KEY", "")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET", "")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE", "")
BACKPACK_API_KEY = os.getenv("BACKPACK_API_KEY", "")
BACKPACK_API_SECRET = os.getenv("BACKPACK_API_SECRET", "") 