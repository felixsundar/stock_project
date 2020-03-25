import logging
from queue import PriorityQueue

from django.contrib.auth.models import User
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp.models import Stock

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

current_positions = {} # list of length 2 for each position. list[0]: entry price. list[1]: stoploss
pending_orders = []
fund_available = 0.0
token_symbol_map = {}
trigger_prices = {}
signal_queue = PriorityQueue(maxsize=5)

def analyzeTicks(tick_queue):
    kite = createKiteConnect()
    if not kite:
        return
    setupTokenSymbolMap()
    while True:
        tick = tick_queue.get(True)
        for instrument in tick:
            instrument_token = instrument['instrument_token']
            current_price = instrument['last_price']
            checkEntryTrigger(instrument_token, current_price)
            checkStoploss(instrument_token, current_price)

def checkEntryTrigger(instrument_token, current_price):
    trigger_price = trigger_prices[instrument_token]
    if current_price < trigger_price:  # entry trigger breached
        trigger_prices[instrument_token] = 0.995 * current_price
        sendSignal(1, instrument_token)
    else:  # update entry trigger
        trigger_prices[instrument_token] = max(trigger_price, 0.995 * current_price)

def checkStoploss(instrument_token, current_price):
    current_position = current_positions.get(instrument_token)
    if current_position is None:
        return
    if current_price >= current_position[1]:  # stoploss breached
        sendSignal(0, instrument_token)
    else:  # update stoploss
        current_position[1] = min(current_position[1], 1.005 * current_price)

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
        trigger_prices[stock.instrument_token] = 0.0 # trigger price

def sendSignal(a, b):
    pass