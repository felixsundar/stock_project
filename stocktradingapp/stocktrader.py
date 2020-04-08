import logging
import queue
import threading
from queue import PriorityQueue
from time import sleep

import requests
from django.contrib.auth.models import User
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp.models import Stock

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

# CONSTANTS
# enter_or_exit: 1 - enter, 0 - exit
STATUS_COMPLETE = 'COMPLETE'
STATUS_CANCELLED = 'CANCELLED'
STATUS_REJECTED = 'REJECTED'

current_positions = {} # {'instrument_token': {'entry_price': entry_price,
                       #                       'stoploss': stoploss,
                       #                       'users': [(zerodha_user_id, number_of_stocks)]
                       #                      }
                       # } for each token
user_kites = {} # for each user
pending_orders = {} # for each user
funds_available = {} # for each user
signal_queues = {} # for each user
token_symbols = {} # for each token
token_trigger_prices = {} # for each token
token_mis_margins = {} # for each token
token_co_margins = {} # for each token
token_co_lower_trigger = {} # for each token
token_co_upper_trigger = {} # for each token
order_variety = 'co'

def analyzeTicks(tick_queue):
    if not setupTradingThreads():
        return
    updateTriggerRanges()
    setupTokenInfoMap()
    printInitialValues()
    while True:
        try:
            tick = tick_queue.get(True)
            if isinstance(tick, (list,)):
                for instrument in tick:
                    instrument_token = instrument['instrument_token']
                    current_price = instrument['last_price']
                    checkEntryTrigger(instrument_token, current_price)
                    checkStoploss(instrument_token, current_price)
                # logging.debug('tick - {}'.format(tick))
            else:
                pass
        except Exception as e:
            pass

def setupTradingThreads():
    users = User.objects.filter(is_active=True)
    if not users.exists():
        return False
    zerodha_present = False
    for user in users:
        user_zerodha = user.user_zerodha.first()
        if user_zerodha is None:
            continue
        zerodha_present = True

        kite = KiteConnect(user_zerodha.api_key)
        kite.set_access_token(user_zerodha.access_token)
        user_kites[user_zerodha.user_id] = kite

        fund_available = updateFundAvailable(user_zerodha.user_id)
        user_zerodha.fund_available = fund_available
        user_zerodha.save()

        signal_queues[user_zerodha.user_id] = PriorityQueue(maxsize=5)
        pending_orders[user_zerodha.user_id] = []

        trading_thread = threading.Thread(target=tradeExecutor, daemon=True, args=(user_zerodha.user_id,),
                                          name=user_zerodha.user_id+'_trader')
        trading_thread.start()

    return zerodha_present

def updateFundAvailable(zerodha_user_id):
    margin = user_kites[zerodha_user_id].margins()
    fund_available = margin['equity']['available']['live_balance']
    funds_available[zerodha_user_id] = fund_available
    return fund_available

def updateTriggerRanges():
    trigger_ranges_response = requests.get(url=settings.TRIGGER_RANGE_URL)
    trigger_ranges = trigger_ranges_response.json()
    stocks = Stock.objects.filter(active=True)
    symbol_stock = {}
    for stock in stocks:
        symbol_stock[stock.trading_symbol] = stock
    for instrument in trigger_ranges:
        stock = symbol_stock.get(instrument['tradingsymbol'])
        if stock is not None:
            stock.co_trigger_percent_lower = instrument['co_lower']
            stock.co_trigger_percent_upper = instrument['co_upper']
            stock.mis_margin = instrument['mis_multiplier']
            stock.save()

def setupTokenInfoMap():
    stocks = Stock.objects.filter(active=True)
    for stock in stocks:
        token_symbols[stock.instrument_token] = stock.trading_symbol
        token_trigger_prices[stock.instrument_token] = 0.0 # initial trigger price
        token_mis_margins[stock.instrument_token] = stock.mis_margin
        token_co_margins[stock.instrument_token] = stock.co_margin
        token_co_lower_trigger[stock.instrument_token] = stock.co_trigger_percent_lower
        token_co_upper_trigger[stock.instrument_token] = stock.co_trigger_percent_upper

def printInitialValues():
    logging.debug('\n\ncurrent Positions - {}\n\n'.format(current_positions))
    logging.debug('\n\npending orders - {}\n\n'.format(pending_orders))
    logging.debug('\n\nfunds available - {}\n\n'.format(funds_available))
    logging.debug('\n\nsignal queues - {}\n\n'.format(signal_queues))
    logging.debug('\n\ntoken symbols - {}\n\n'.format(token_symbols))
    logging.debug('\n\ntoken trigger prices - {}\n\n'.format(token_trigger_prices))
    logging.debug('\n\ntoken mis margins - {}\n\n'.format(token_mis_margins))
    logging.debug('\n\ntoken co margins - {}\n\n'.format(token_co_margins))
    logging.debug('\n\ntoken co lower trigger - {}\n\n'.format(token_co_lower_trigger))
    logging.debug('\n\ntoken co upper trigger - {}\n\n'.format(token_co_upper_trigger))

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

def tradeExecutor(zerodha_user_id):
    signal_queue = signal_queues[zerodha_user_id]
    kite = user_kites[zerodha_user_id]
    place = True
    while True:
        signal = signal_queue.get(True)
        try:
            if signal[0] == 1 and not pending_orders.get(zerodha_user_id) and place == True:
                placeEntryOrder(zerodha_user_id, kite, signal)
                place = False
            else:
                pass
                # placeExitOrder(zerodha_user_id, kite, signal)
        except Exception as e:
            logging.debug('Exception while placing order for user - {}\n'
                          'Instrument Token - {}\n\n{}'.format(zerodha_user_id, signal[1], e))

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

def placeEntryOrder(zerodha_user_id, kite, signal):
    quantity, variety = calculateNumberOfStocksToTrade(zerodha_user_id, signal[1], signal[2])
    if variety == 'co': #place co order
        trigger_price = calculateCOtriggerPrice(token_co_upper_trigger[signal[1]], signal[2])
        order_id = kite.place_order(variety=variety, exchange='NSE', tradingsymbol=token_symbols[signal[1]],
                                    transaction_type='SELL', quantity=quantity, product='MIS', order_type='MARKET',
                                    validity='DAY', disclosed_quantity=quantity, trigger_price=trigger_price)
        logging.debug('CO ENTRY ORDER PLACED for zerodha user - {}\nInstrument token for entry - {}'
                      '\nTrigger price for co order exit - {}'
                      '\norder quantity - {}'.format(zerodha_user_id, signal[1], trigger_price, quantity))
    else: #place regular order(mis)
        order_id = kite.place_order(variety=variety, exchange='NSE', tradingsymbol=token_symbols[signal[1]],
                                    transaction_type='SELL', quantity=quantity, product='MIS',
                                    order_type='MARKET', validity='DAY', disclosed_quantity=quantity)
        logging.debug('REGULAR ENTRY ORDER PLACED for zerodha user - {}\nInstrument token for entry - {}'
                      '\norder quantity - {}'.format(zerodha_user_id, signal[1], quantity))
    pending_orders[zerodha_user_id].append((order_id, signal[0]))

def calculateNumberOfStocksToTrade(zerodha_user_id, instrument_token, current_price):
    order_variety_local = order_variety
    if order_variety_local == 'co':
        margin = token_co_margins[instrument_token]
    else:
        margin = token_mis_margins[instrument_token]
    total_fund = margin * funds_available[zerodha_user_id]
    quantity = total_fund//(current_price + 1) # 1 added to match the anticipated price increase in the time gap
    return (int(quantity), order_variety_local)

def calculateCOtriggerPrice(co_upper_trigger_percent, current_price):
    trigger_price = current_price + (current_price * (min(co_upper_trigger_percent - 1.0, 1.5) / 100.0))
    return float('{:.1f}'.format(trigger_price))

def updateOrderFromPostback(order_details):
    sleep(0.5) # postback may be received instantly after placing order. wait till order id is entered in the pending orders list
    pending_order = getPendingOrder(order_details)
    if pending_order is None:
        return
    if order_details['status'] == STATUS_CANCELLED:
        pending_orders[order_details['user_id']].remove(pending_order)
    elif order_details['status'] == STATUS_REJECTED:
        pending_orders[order_details['user_id']].remove(pending_order)
        order_variety = 'regular'
    elif order_details['status'] == STATUS_COMPLETE:
        updateFundAvailable(order_details['user_id'])
        if pending_order['enter_or_exit'] == 1:
            updateEntryOrderComplete(pending_order, order_details)
        else:
            updateExitOrderComplete(pending_order, order_details)

def getPendingOrder(order_details):
    user_pending_orders = pending_orders[order_details['user_id']]
    for order in user_pending_orders:
        if order['order_id'] == order_details['order_id']:
            return order
    return None

def updateEntryOrderComplete(pending_order, order_details):
    pass

def updateExitOrderComplete(pending_order, order_details):
    pass
