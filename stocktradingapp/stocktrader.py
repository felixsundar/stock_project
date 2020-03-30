import logging
import queue
import threading
from queue import PriorityQueue

from django.contrib.auth.models import User
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp.models import Stock

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

current_positions = {} # {'instrument_token': {'entry_price': entry_price,
                       #                       'stoploss': stoploss,
                       #                       'users': [(zerodha_user_id, number_of_stocks)]
                       #                      }
                       # }
pending_orders = {}
funds_available = {} # for each user
signal_queues = {} # for each user
token_symbols = {} # for each token
token_trigger_prices = {} # for each token
token_mis_margins = {} # for each token
token_co_margins = {} # for each token
order_variety = 'co'

def analyzeTicks(tick_queue):
    if not setupTradingThreads():
        return
    setupTokenInfoMap()
    while True:
        try:
            tick = tick_queue.get(True)
            if isinstance(tick, (list,)):
                for instrument in tick:
                    instrument_token = instrument['instrument_token']
                    current_price = instrument['last_price']
                    checkEntryTrigger(instrument_token, current_price)
                    checkStoploss(instrument_token, current_price)
            else:
                processMessage(tick)
        except Exception as e:
            pass

def checkEntryTrigger(instrument_token, current_price):
    trigger_price = token_trigger_prices[instrument_token]
    if current_price < trigger_price:  # entry trigger breached
        token_trigger_prices[instrument_token] = 0.995 * current_price
        sendSignal(1, instrument_token, current_price)
    else:  # update entry trigger
        token_trigger_prices[instrument_token] = max(trigger_price, 0.995 * current_price)

def checkStoploss(instrument_token, current_price):
    current_position = current_positions.get(instrument_token)
    if current_position is None:
        return
    if current_price >= current_position['stoploss']:  # stoploss breached
        sendSignal(0, instrument_token)
    else:  # update stoploss
        current_position['stoploss'] = min(current_position['stoploss'], 1.005 * current_price)

def setupTradingThreads():
    users = User.objects.filter(is_active=True)
    if not users.exists():
        return False
    for user in users:
        user_zerodha = user.user_zerodha.first()
        if user_zerodha is None:
            continue
        kite = KiteConnect(user_zerodha.api_key)
        kite.set_access_token(user_zerodha.access_token)
        signal_queues[user_zerodha.user_id] = PriorityQueue(maxsize=5)
        trading_thread = threading.Thread(target=tradeExecutor, daemon=True, args=(user_zerodha.user_id, kite,),
                                          name=user_zerodha.user_id+'_trader')
        trading_thread.start()
    return True

def setupTokenInfoMap():
    stocks = Stock.objects.filter(active=True)
    for stock in stocks:
        token_symbols[stock.instrument_token] = stock.trading_symbol
        token_trigger_prices[stock.instrument_token] = 0.0 # initial trigger price
        token_mis_margins[stock.instrument_token] = stock.mis_margin
        token_co_margins[stock.instrument_token] = stock.co_margin

def processMessage(tick):
    pass

def sendSignal(enter_or_exit, instrument_token, current_price=None): # 0 for exit, 1 for enter
    if enter_or_exit == 1:
        for signal_queue in signal_queues.values():
            try:
                signal_queue.put_nowait((enter_or_exit, instrument_token, current_price))
            except queue.Full:
                pass
    else:
        current_position = current_positions[instrument_token]
        for user in current_position['users']:
            signal_queues[user[0]].put((enter_or_exit, instrument_token, current_price), block=True)

def tradeExecutor(zerodha_user_id, kite):
    updateFundAvailable(zerodha_user_id, kite)
    signal_queue = signal_queues[zerodha_user_id]
    while True:
        signal = signal_queue.get(True)
        if signal[0] == 1 and not pending_orders.get(zerodha_user_id):
            quantity, variety = calculateNumberOfStocksToTrade(zerodha_user_id, signal[1], signal[2])
            if variety == 'co':
                #trigger_price = calculateCOtriggerPrice()
                order_id = kite.place_order(variety=variety, exchange='NSE', tradingsymbol=token_symbols[signal[1]],
                                 transaction_type='SELL', quantity=quantity, product='MIS', order_type='MARKET',
                                 validity='DAY', disclosed_quantity=quantity, trigger_price='d')
            # variety = regular, amo, bo, co
            # exchange = NSE, BSE
            # tradingsymbol = IRCTC, SBICARD, etc..
            # transaction_type = BUY, SELL
            # quantity = number of stocks
            # product = CNC, MIS
            # order_type = MARKET, LIMIT, SL, SL-M
            # price = limit price
            # validity = DAY, IOC # use day always
            # disclosed quantity = within 10 to 100 % of quantity. # set this same as quantity
            # trigger price = entry trigger price
            # squareoff = target profit to exit. Profit amount in Rupees
            # stoploss = loss amount in Rupees to exit
            # trailing_stoploss = moving stoploss
            # tag = random alphanumeric id attached to the order

def calculateNumberOfStocksToTrade(zerodha_user_id, instrument_token, current_price):
    order_variety_local = order_variety
    if order_variety_local == 'co':
        margin = token_co_margins[instrument_token]
    else:
        margin = token_mis_margins[instrument_token]
    total_fund = margin * funds_available[zerodha_user_id]
    quantity = total_fund//(current_price + 1) # 1 added to match the anticipated price increase in the time gap
    return (quantity, order_variety_local)

def updateFundAvailable(zerodha_user_id, kite):
    margin = kite.margins()
    fund_available = margin['data']['equity']['available']['cash']
    funds_available[zerodha_user_id] = fund_available
