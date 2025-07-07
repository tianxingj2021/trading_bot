import sys
from utils.order_adapter import get_latest_price

symbols = ['BTCUSDT', 'ETHUSDT']
exchanges = ['binance', 'backpack', 'aster']

for exchange in exchanges:
    print(f'--- {exchange} ---')
    for symbol in symbols:
        try:
            price = get_latest_price(exchange, symbol)
            print(f'{symbol}: {price}')
        except Exception as e:
            print(f'{symbol}: 获取失败 - {e}') 