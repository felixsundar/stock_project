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
            logging.debug(price_window)
            signal = checkForEntry(list(price_window))
            if signal != 0:
                # sendEntrySignal(instrument['instrument_token'], signal)
                logging.debug('\n\n\n\n\nsignal received - {}\n\n\n\n\n'.format(signal))

def checkForEntry(price_list):
    for i in range(5,10):
        if price_list[i] <= price_list[i-1]:
            break
    else:
        return 1 #long entry signal
    for i in range(5,10):
        if price_list[i] >= price_list[i-1]:
            break
    else:
        return 2 #short entry signal
    return 0
    # pointfivepercent = 45
    # latest_price = price_list[9]
    # for i in range(4,9):
    #     if latest_price - price_list[i] >=

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