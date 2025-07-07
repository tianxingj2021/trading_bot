"""
工具函数
"""
from typing import Dict, List, Optional
from exchanges.aster import AsterAccountSnapshot, AsterKline


def get_position(account_snapshot: Optional[AsterAccountSnapshot], trade_symbol: str) -> Dict:
    """
    获取持仓信息
    
    Args:
        account_snapshot: 账户快照
        trade_symbol: 交易对符号
    
    Returns:
        持仓信息字典，包含positionAmt, entryPrice, unrealizedProfit
    """
    if not account_snapshot:
        return {"positionAmt": 0, "entryPrice": 0, "unrealizedProfit": 0}
    
    for position in account_snapshot.positions:
        if position.symbol == trade_symbol:
            return {
                "positionAmt": float(position.position_amt),
                "entryPrice": float(position.entry_price),
                "unrealizedProfit": float(position.unrealized_profit),
            }
    
    return {"positionAmt": 0, "entryPrice": 0, "unrealizedProfit": 0}


def get_sma30(kline_snapshot: List[AsterKline]) -> Optional[float]:
    """
    计算SMA30均线
    
    Args:
        kline_snapshot: K线数据列表
    
    Returns:
        SMA30均线值，如果数据不足返回None
    """
    if not kline_snapshot or len(kline_snapshot) < 30:
        return None
    
    # 取最近30根K线的收盘价
    closes = [float(kline.close) for kline in kline_snapshot[-30:]]
    return sum(closes) / len(closes)


def to_price_1_decimal(price: float) -> float:
    """
    价格保留1位小数
    
    Args:
        price: 原始价格
    
    Returns:
        保留1位小数的价格
    """
    return round(price * 10) / 10


def to_qty_3_decimal(qty: float) -> float:
    """
    数量保留3位小数
    
    Args:
        qty: 原始数量
    
    Returns:
        保留3位小数的数量
    """
    return round(qty * 1000) / 1000


def adapt_symbol(symbol: str, exchange: str) -> str:
    """
    统一适配不同交易所的symbol格式
    :param symbol: 通用symbol，如BTCUSDT
    :param exchange: 交易所名
    :return: 适配后的symbol
    """
    s = symbol.upper()
    if exchange == 'backpack':
        # Backpack合约如BTC_USDC_PERP
        if s.endswith('USDT'):
            base = s[:-4]
            return f'{base}_USDC_PERP'
        elif s.endswith('USDC'):
            base = s[:-4]
            return f'{base}_USDC_PERP'
        else:
            return s
    elif exchange == 'binance':
        return s
    elif exchange == 'aster':
        return s
    else:
        return s 