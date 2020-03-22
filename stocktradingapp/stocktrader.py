import logging

from django.contrib.auth.models import User
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp.models import Stock

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

current_positions = []
pending_orders = []
fund_available = 0.0
token_symbol_map = {}

def analyzeTicks(tick_queue):
    kite = createKiteConnect()
    if not kite:
        return
    setupTokenSymbolMap()
    while True:
         tick = tick_queue.get(True)
         print(tick)
         for instrument in tick:
             print(token_symbol_map[instrument['instrument_token']])


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