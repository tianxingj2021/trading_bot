"""
account_adapter.py
统一账户余额和最大杠杆查询，自动适配binance/aster/backpack等交易所
"""
from exchanges.aster import Aster
from exchanges.backpack import Backpack
from exchanges.binance import Binance
from config import ASTER_API_KEY, ASTER_API_SECRET, BACKPACK_API_KEY, BACKPACK_API_SECRET

BINANCE_API_KEY = ""
BINANCE_API_SECRET = ""

aster = Aster(api_key=ASTER_API_KEY, api_secret=ASTER_API_SECRET)
backpack = Backpack(api_key=BACKPACK_API_KEY, api_secret=BACKPACK_API_SECRET)
binance = Binance(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

symbol_map = {
    "BTCUSDT": {
        "binance": "BTCUSDT",
        "aster": "BTCUSDT",
        "backpack": "BTC_USDC_PERP"
    },
    "ETHUSDT": {
        "binance": "ETHUSDT",
        "aster": "ETHUSDT",
        "backpack": "ETH_USDC_PERP"
    },
    # ... 可扩展
}

def adapt_symbol(symbol, exchange):
    if symbol in symbol_map and exchange in symbol_map[symbol]:
        return symbol_map[symbol][exchange]
    if exchange == "backpack":
        return symbol.replace("USDT", "_USDC_PERP").upper()
    return symbol

def get_exchange_instance(exchange):
    if exchange == 'backpack':
        return backpack
    elif exchange == 'binance':
        return binance
    else:
        return aster

def get_account_balance(exchange, asset='USDT'):
    """
    查询账户余额，返回float
    """
    ex = get_exchange_instance(exchange)
    if exchange == 'backpack':
        balances = ex.get_balances()
        info = balances.get(asset)
        if info and isinstance(info, dict):
            return float(info.get('available', 0))
        return 0.0
    else:
        account = ex.get_account()
        for a in getattr(account, 'assets', []):
            if (getattr(a, 'asset', None) or a.get('asset')) == asset:
                return float(getattr(a, 'wallet_balance', 0) or a.get('walletBalance', 0) or 0)
        return 0.0

def get_max_leverage(exchange, symbol):
    """
    查询指定交易所和symbol的最大杠杆
    """
    ex = get_exchange_instance(exchange)
    real_symbol = adapt_symbol(symbol, exchange)
    if hasattr(ex, 'get_max_leverage'):
        return ex.get_max_leverage(real_symbol)
    return 1 