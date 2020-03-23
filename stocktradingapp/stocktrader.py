import logging
from collections import deque

from django.contrib.auth.models import User
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp.models import Stock

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

current_positions = []
pending_orders = []
fund_available = 0.0
token_symbol_map = {}
price_windows = {}

def analyzeTicks(tick_queue):
    kite = createKiteConnect()
    if not kite:
        return
    setupTokenSymbolMap()
    while True:
        tick = tick_queue.get(True)
        for instrument in tick:
            price_window = price_windows[instrument['instrument_token']]
            dump = price_window.popleft()
            price_window.append(instrument['last_price'])


def createKiteConnect():
    user = User.objects.get_by_natural_key(settings.PRIMARY_USERNAME)
    user_zerodha = user.user_zerodha.first()
    if user_zerodha is None:
        return None
    kite = KiteConnect(settings.KITE_API_KEY)
    kite.set_access_token(user_zerodha.access_token)
    return kite

def setupTokenSymbolMap():
    stocks = Stock.objects.filter(active=True)
    for stock in stocks:
        token_symbol_map[stock.instrument_token] = stock.trading_symbol
        price_windows[stock.instrument_token] = deque(iterable=[0 for i in range(10)], maxlen=10)