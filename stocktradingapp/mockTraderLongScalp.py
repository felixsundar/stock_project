import logging
import queue
import threading
from datetime import timedelta
from queue import PriorityQueue, Queue
from time import sleep

import requests
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils.timezone import now
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp.models import Stock, ZerodhaAccount, Controls, LiveMonitor

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

# CONSTANTS
ENTER = 1
EXIT = 0
STATUS_COMPLETE = 'COMPLETE'
STATUS_CANCELLED = 'CANCELLED'
STATUS_REJECTED = 'REJECTED'
CO_ORDER = 'co'
REGULAR_ORDER = 'regular'

# PARAMETERS
ENTRY_TRIGGER_TIMES = (100.0 - settings.ENTRY_TRIGGER_PERCENT) / 100.0

MAX_RISK_PERCENT_PER_TRADE = settings.MAX_RISK_PERCENT_PER_TRADE
MAX_INVESTMENT_PER_POSITION = settings.MAX_INVESTMENT_PER_POSITION
MIN_INVESTMENT_PER_POSITION = settings.MIN_INVESTMENT_PER_POSITION

POSITION_STOPLOSS_PERCENT = settings.POSITION_STOPLOSS_PERCENT
POSITION_TARGET_STOPLOSS = settings.POSITION_TARGET_STOPLOSS
POSITION_TARGET_PERCENT = settings.POSITION_TARGET_PERCENT
POSITION_STOPLOSS_TARGET_RATIO = POSITION_TARGET_PERCENT / POSITION_STOPLOSS_PERCENT

USER_STOPLOSS_PERCENT = settings.USER_STOPLOSS_PERCENT
USER_TARGET_STOPLOSS = settings.USER_TARGET_STOPLOSS
USER_TARGET_PERCENT = settings.USER_TARGET_PERCENT
USER_STOPLOSS_TARGET_RATIO = USER_TARGET_PERCENT / USER_STOPLOSS_PERCENT

COMMISSION_PERCENT = settings.COMMISSION_PERCENT
ENTRY_TIME_START = now().time().replace(hour=settings.ENTRY_TIME_START[0], minute=settings.ENTRY_TIME_START[1],
                                        second=settings.ENTRY_TIME_START[2])

MOCK_TRADING_INITIAL_VALUE = settings.MOCK_TRADING_INITIAL_VALUE

# FOR EACH TOKEN
token_symbols = {}
token_trigger_prices = {}
token_mis_margins = {}
token_co_margins = {}
token_co_lower_trigger = {}
current_positions = {}

# FOR EACH USER
user_kites = {}
pending_orders = {} # {userid1:[], userid2:[], userid3:[{enter_or_exit:1, orderid:32435, instrument_token:xx}]}
user_initial_value = {}
live_funds_available = {}
user_net_value = {}
user_commission = {}
user_target_value = {}
user_stoploss = {}
user_target_stoploss = {}
user_amount_at_risk = {}
signal_queues = {}
live_monitor = {}

# OTHER GLOBALS
postback_queue = Queue(maxsize=500)
order_variety = REGULAR_ORDER
order_id = 1
entry_allowed = True
exit_time_reached = False

def analyzeTicks(tick_queue):
    setupParameters()
    if not setupUserAccounts():
        return
    updateTriggerRangesInDB()
    setupTokenMaps()
    startPostbackProcessingThread()
    logging.debug('long scalp mock trader thread started')
    scheduleExit()
    while True:
        try:
            tick = tick_queue.get(True)
            current_time = now()
            for instrument in tick:
                instrument_token = instrument['instrument_token']
                current_price = instrument['last_price']
                checkEntryTrigger(instrument_token, current_price)
                checkStoploss(instrument_token, current_price, current_time)
        except Exception as e:
            pass

def setupUserAccounts():
    user_zerodhas = ZerodhaAccount.objects.filter(is_active=True)
    user_present = False
    for user_zerodha in user_zerodhas:
        user_present = True
        if not validateAccessToken(user_zerodha.access_token_time):
            continue
        setupUserMaps(user_zerodha)
        updateLiveMonitor(user_zerodha.user_id)
        trading_thread = threading.Thread(target=tradeExecutor, daemon=True, args=(user_zerodha.user_id,),
                                          name=user_zerodha.user_id + '_trader_thread')
        trading_thread.start()
        break # run only one user for mock
    return user_present

def setupUserMaps(user_zerodha):
    kite = KiteConnect(user_zerodha.api_key)
    kite.set_access_token(user_zerodha.access_token)
    user_kites[user_zerodha.user_id] = kite

    live_funds_available[user_zerodha.user_id] = MOCK_TRADING_INITIAL_VALUE
    user_zerodha.fund_available = live_funds_available[user_zerodha.user_id]
    user_zerodha.save()

    user_initial_value[user_zerodha.user_id] = live_funds_available[user_zerodha.user_id]
    user_target_value[user_zerodha.user_id] = live_funds_available[user_zerodha.user_id] * (100.0 + USER_TARGET_PERCENT) / 100.0
    user_net_value[user_zerodha.user_id] = live_funds_available[user_zerodha.user_id]
    user_commission[user_zerodha.user_id] = 0.0
    user_stoploss[user_zerodha.user_id] = (100.0 - USER_STOPLOSS_PERCENT) * live_funds_available[user_zerodha.user_id] / 100.0
    user_target_stoploss[user_zerodha.user_id] = USER_TARGET_STOPLOSS * user_net_value[user_zerodha.user_id] / 100.0
    user_amount_at_risk[user_zerodha.user_id] = 0.0
    signal_queues[user_zerodha.user_id] = PriorityQueue(maxsize=100)
    pending_orders[user_zerodha.user_id] = []
    test_user = User.objects.get_by_natural_key('testuser2')
    live_monitor[user_zerodha.user_id] = LiveMonitor(hstock_user=test_user, user_id='Long Scalp',
                                                     initial_value=user_initial_value[user_zerodha.user_id])

def updateLiveMonitor(user_id):
    user_live_monitor = live_monitor[user_id]
    user_live_monitor.current_value = user_net_value[user_id]
    user_live_monitor.stoploss = user_stoploss[user_id]
    user_live_monitor.net_profit_percent = (user_live_monitor.current_value - user_live_monitor.initial_value) * 100.0 / user_live_monitor.initial_value
    user_live_monitor.value_at_risk = user_amount_at_risk[user_id]
    user_live_monitor.commission = user_commission[user_id]
    user_live_monitor.profit = user_live_monitor.current_value - user_live_monitor.initial_value + user_live_monitor.commission
    user_live_monitor.save()

def validateAccessToken(access_token_time):
    expiry_time = now().replace(hour=8, minute=30, second=0, microsecond=0)
    if now() > expiry_time and access_token_time < expiry_time:
        return False
    return True

def updateTriggerRangesInDB():
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

def setupTokenMaps():
    stocks = Stock.objects.filter(active=True)
    for stock in stocks:
        current_positions[stock.instrument_token] = []
        token_symbols[stock.instrument_token] = stock.trading_symbol
        token_trigger_prices[stock.instrument_token] = 0.0 # initial trigger price
        token_mis_margins[stock.instrument_token] = stock.mis_margin
        token_co_margins[stock.instrument_token] = stock.co_margin
        token_co_lower_trigger[stock.instrument_token] = stock.co_trigger_percent_lower

def setupParameters():
    global ENTRY_TRIGGER_TIMES, MAX_RISK_PERCENT_PER_TRADE, MAX_INVESTMENT_PER_POSITION, MIN_INVESTMENT_PER_POSITION, COMMISSION_PERCENT, \
        POSITION_STOPLOSS_PERCENT, POSITION_TARGET_STOPLOSS, POSITION_TARGET_PERCENT, USER_STOPLOSS_PERCENT, MOCK_TRADING_INITIAL_VALUE, \
        USER_TARGET_STOPLOSS, USER_STOPLOSS_TARGET_RATIO, USER_TARGET_PERCENT, ENTRY_TIME_START, POSITION_STOPLOSS_TARGET_RATIO

    try:
        controls = Controls.objects.get(control_id=settings.CONTROLS_RECORD_ID)

        ENTRY_TRIGGER_TIMES = (100.0 - controls.entry_trigger_percent) / 100.0

        MAX_RISK_PERCENT_PER_TRADE = controls.max_risk_percent_per_trade
        MAX_INVESTMENT_PER_POSITION = controls.max_investment_per_position
        MIN_INVESTMENT_PER_POSITION = controls.min_investment_per_position

        POSITION_STOPLOSS_PERCENT = controls.position_stoploss_percent
        POSITION_TARGET_STOPLOSS = controls.position_target_stoploss
        POSITION_TARGET_PERCENT = controls.position_target_percent
        POSITION_STOPLOSS_TARGET_RATIO = POSITION_TARGET_PERCENT / POSITION_STOPLOSS_PERCENT

        USER_STOPLOSS_PERCENT = controls.user_stoploss_percent
        USER_TARGET_STOPLOSS = controls.user_target_stoploss
        USER_TARGET_PERCENT = controls.user_target_percent
        USER_STOPLOSS_TARGET_RATIO = USER_TARGET_PERCENT / USER_STOPLOSS_PERCENT

        ENTRY_TIME_START = controls.entry_time_start.time()

        MOCK_TRADING_INITIAL_VALUE = controls.mock_trading_initial_value
    except Exception as e:
        pass

def startPostbackProcessingThread():
    postback_processing_thread = threading.Thread(target=updateOrderFromPostback, daemon=True, name='postback_processing_thread')
    postback_processing_thread.start()

def checkEntryTrigger(instrument_token, current_price):
    if current_price <= token_trigger_prices[instrument_token]: # entry trigger breached
        token_trigger_prices[instrument_token] = current_price * ENTRY_TRIGGER_TIMES
        sendSignal(ENTER, instrument_token, current_price)
    else: # update entry trigger
        token_trigger_prices[instrument_token] = max(token_trigger_prices[instrument_token], current_price * ENTRY_TRIGGER_TIMES)

def checkStoploss(instrument_token, current_price, current_time):
    for position in current_positions[instrument_token]:
        if current_time >= position['exit_time'] or current_price >= position['target_price'] or exit_time_reached: # stoploss breached
            position['exit_price'] = current_price
            sendSignal(EXIT, instrument_token, position)

def sendSignal(enter_or_exit, instrument_token, currentPrice_or_currentPosition): # 0 for exit, 1 for enter
    if enter_or_exit == ENTER:
        for signal_queue in signal_queues.values():
            try:
                signal_queue.put_nowait((ENTER, instrument_token, currentPrice_or_currentPosition))
            except queue.Full:
                pass
    else:
        signal_queue = signal_queues[currentPrice_or_currentPosition['user_id']]
        signal_queue.put((EXIT, instrument_token, currentPrice_or_currentPosition), block=True)

def tradeExecutor(zerodha_user_id):
    signal_queue = signal_queues[zerodha_user_id]
    kite = user_kites[zerodha_user_id]
    while True:
        signal = signal_queue.get(True)
        try:
            if signal[0] == ENTER and verifyEntryCondition(zerodha_user_id, signal[1]):
                placeEntryOrder(zerodha_user_id, kite, signal)
            elif signal[0] == EXIT and not signal[2]['exit_pending']:
                placeExitOrder(kite, signal[1], signal[2])
        except Exception as e:
            logging.debug('Exception while placing order for user - {}\n'
                          'Instrument Token - {}\n\n{}'.format(zerodha_user_id, signal[1], e))

def verifyEntryCondition(zerodha_user_id, instrument_token):
    for position in current_positions[instrument_token]:
        if position['user_id'] == zerodha_user_id:
            return False
    current_time = now().time()
    if (not entry_allowed) or current_time < ENTRY_TIME_START or \
            user_net_value[zerodha_user_id] <= user_stoploss[zerodha_user_id] or pending_orders[zerodha_user_id]:
        return False
    return True

def placeEntryOrder(zerodha_user_id, kite, signal):
    quantity, variety = calculateNumberOfStocksToTrade(zerodha_user_id, signal[1], signal[2])
    if quantity == 0:
        return
    if variety == CO_ORDER: #place co order
        trigger_price = calculateCOtriggerPrice(token_co_lower_trigger[signal[1]], signal[2])
        order_id = kite.place_order(variety=variety, exchange='NSE', tradingsymbol=token_symbols[signal[1]],
                                    transaction_type='BUY', quantity=quantity, product='MIS', order_type='MARKET',
                                    validity='DAY', disclosed_quantity=quantity, trigger_price=trigger_price)
    else: #place regular order(mis)
        # order_id = kite.place_order(variety=variety, exchange='NSE', tradingsymbol=token_symbols[signal[1]],
        #                             transaction_type='BUY', quantity=quantity, product='MIS',
        #                             order_type='MARKET', validity='DAY', disclosed_quantity=quantity)
        order_id = place_order(zerodha_user_id, variety, quantity, signal[2], signal[1])
    pending_orders[zerodha_user_id].append({'enter_or_exit':ENTER, 'order_id':order_id, 'instrument_token':signal[1]})

def placeExitOrder(kite, instrument_token, position):
    if position['variety'] == CO_ORDER:
        order_id = kite.cancel_order(variety=CO_ORDER, order_id=position['order_id'], parent_order_id=position['parent_order_id'])
    else:
        # order_id = kite.place_order(variety=position['variety'], exchange='NSE', tradingsymbol=token_symbols[instrument_token],
        #                             transaction_type='SELL', quantity=position['number_of_stocks'], order_type='MARKET',
        #                             product='MIS', validity='DAY', disclosed_quantity=position['number_of_stocks'])
        order_id = place_order(position['user_id'], REGULAR_ORDER, position['number_of_stocks'], position['exit_price'], instrument_token)
    position['exit_pending'] = True
    pending_orders[position['user_id']].append({'enter_or_exit':EXIT, 'order_id':order_id, 'instrument_token':instrument_token})

def place_order(user_id, order_variety, number_of_stocks, entry_or_exit_price, instrument_token):
    global order_id
    order_id += 1
    order_details = {
        'user_id': user_id,
        'variety': order_variety,
        'filled_quantity': number_of_stocks,
        'average_price': entry_or_exit_price,
        'order_id': order_id,
        'instrument_token': instrument_token,
        'status': STATUS_COMPLETE
    }
    postback_queue.put(item=order_details, block=True)
    return order_id

def calculateNumberOfStocksToTrade(zerodha_user_id, instrument_token, current_price):
    order_variety_local = order_variety
    if order_variety_local == CO_ORDER:
        margin = token_co_margins[instrument_token]
    else:
        margin = token_mis_margins[instrument_token]
    riskable_amount = min(MAX_RISK_PERCENT_PER_TRADE * user_net_value[zerodha_user_id] / 100.0,
                          user_net_value[zerodha_user_id] - user_amount_at_risk[zerodha_user_id] - user_stoploss[zerodha_user_id])
    if riskable_amount <= 0:
        return (0, order_variety_local)
    investment_for_riskable_amount = riskable_amount * 100.0 / POSITION_STOPLOSS_PERCENT # riskable_amount = 0.5% then ? = 100%...
    amount_to_invest = min(investment_for_riskable_amount, live_funds_available[zerodha_user_id] * margin, MAX_INVESTMENT_PER_POSITION)
    quantity = amount_to_invest // (current_price + 1) # 1 added to match the anticipated price increase in the time gap
    quantity = quantity if (quantity * current_price) >= MIN_INVESTMENT_PER_POSITION else 0
    return (int(quantity), order_variety_local)

def calculateCOtriggerPrice(co_lower_trigger_percent, current_price):
    trigger_price = current_price - (current_price * (min(co_lower_trigger_percent - 1.0, 2.5) / 100.0))
    return float('{:.1f}'.format(trigger_price))

def updateOrderFromPostback():
    while True:
        order_details = postback_queue.get(block=True)
        sleep(0.3)  # postback maybe received instantly after placing order. so wait till order id is added to pending orders list
        try:
            pending_order = getPendingOrder(order_details)
            if pending_order is None:
                continue
            if order_details['status'] == STATUS_CANCELLED:
                pending_orders[order_details['user_id']].remove(pending_order)
            elif order_details['status'] == STATUS_REJECTED:
                pending_orders[order_details['user_id']].remove(pending_order)
                global order_variety
                order_variety = REGULAR_ORDER
            elif order_details['status'] == STATUS_COMPLETE:
                if pending_order['enter_or_exit'] == ENTER:
                    updateEntryOrderComplete(order_details)
                else:
                    updateExitOrderComplete(order_details)
                pending_orders[order_details['user_id']].remove(pending_order)
                updateLiveMonitor(order_details['user_id'])
        except Exception as e:
            logging.debug('exception while processing postback: \n{}'.format(e))

def getPendingOrder(order_details):
    user_pending_orders = pending_orders[order_details['user_id']]
    for order in user_pending_orders:
        if order['order_id'] == order_details['order_id']:
            return order
    return None

def updateEntryOrderComplete(order_details):
    if order_details['variety'] == CO_ORDER:
        second_leg_order_details = getSecondLegOrder(order_details)
        new_position = constructNewPosition(order_details, second_leg_order_details)
    else:
        new_position = constructNewPosition(order_details)
    updateAmountAtRisk(ENTER, order_details['user_id'], order_details['average_price'], order_details['filled_quantity'])
    current_positions[order_details['instrument_token']].append(new_position)
    live_funds_available[order_details['user_id']] -= (order_details['average_price'] * order_details['filled_quantity']
                                                       / token_mis_margins[order_details['instrument_token']])

def updateAmountAtRisk(enter_or_exit, zerodha_user_id, price, number_of_stocks):
    if enter_or_exit == ENTER:
        user_amount_at_risk[zerodha_user_id] = user_amount_at_risk[zerodha_user_id] + (price * number_of_stocks * POSITION_STOPLOSS_PERCENT / 100.0)
    else:
        user_amount_at_risk[zerodha_user_id] = user_amount_at_risk[zerodha_user_id] - (price * number_of_stocks * POSITION_STOPLOSS_PERCENT / 100.0)

def updateExitOrderComplete(order_details):
    current_positions_for_instrument = current_positions[order_details['instrument_token']]
    for position in current_positions_for_instrument:
        if position['user_id'] == order_details['user_id']:
            updateUserNetValue(position['user_id'], position, order_details['average_price'])
            updateAmountAtRisk(EXIT, position['user_id'], position['entry_price'], position['number_of_stocks'])
            current_positions_for_instrument.remove(position)
            live_funds_available[order_details['user_id']] += (position['entry_price'] * position['number_of_stocks']
                                                               / token_mis_margins[order_details['instrument_token']])
            return

def updateUserNetValue(user_id, position, exit_price):
    trade_profit = (exit_price - position['entry_price']) * position['number_of_stocks']
    live_funds_available[user_id] += trade_profit
    commission = calculateCommission(position['entry_price'] * position['number_of_stocks'], exit_price * position['number_of_stocks'])
    user_commission[user_id] += commission
    user_net_value[user_id] += (trade_profit - commission)
    user_stoploss[user_id] = max(user_stoploss[user_id], updateUserStoploss(user_id))

def calculateCommission(buy_value, sell_value):
    trade_value = buy_value + sell_value
    broker_commission_buy = min(20.0, buy_value * 0.03 / 100.0)
    broker_commission_sell = min(20.0, sell_value * 0.03 / 100.0)
    transaction_charge_trade = trade_value * 0.00325 / 100.0
    gst_trade = (broker_commission_buy + broker_commission_sell + transaction_charge_trade) * 18.0 / 100.0
    stt_sell = sell_value * 0.025 / 100.0
    sebi_trade = trade_value * 0.0001 / 100.0
    stamp_duty_trade = trade_value * 0.006 / 100.0
    return broker_commission_buy + broker_commission_sell + transaction_charge_trade + gst_trade + stt_sell + sebi_trade + stamp_duty_trade

def updateUserStoploss(user_id):
    return user_net_value[user_id] - \
           max((user_target_value[user_id] - user_net_value[user_id]) / USER_STOPLOSS_TARGET_RATIO, user_target_stoploss[user_id])

def getSecondLegOrder(order_details):
    kite = user_kites[order_details['user_id']]
    orders = kite.orders()
    for order in orders:
        if order['parent_order_id'] == order_details['order_id']:
            return order
    logging.debug('second leg order not found for co-order: \n{}\n\nall orders retreived: \n{}'.format(order_details, orders))

def constructNewPosition(order_details, second_leg_order_details=None):
    new_position = {}
    new_position['user_id'] = order_details['user_id']
    new_position['variety'] = order_details['variety']
    new_position['number_of_stocks'] = order_details['filled_quantity']
    new_position['entry_price'] = order_details['average_price']
    new_position['stoploss'] = order_details['average_price'] * (100.0 - POSITION_STOPLOSS_PERCENT) / 100.0
    new_position['exit_time'] = now() + timedelta(minutes=5)
    new_position['target_price'] = order_details['average_price'] * (100.0 + POSITION_TARGET_PERCENT) / 100.0
    new_position['exit_pending'] = False
    if second_leg_order_details:
        new_position['order_id'] = second_leg_order_details['order_id']
        new_position['parent_order_id'] = second_leg_order_details['parent_order_id']
    return new_position

def scheduleExit():
    try:
        controls = Controls.objects.get(control_id=settings.CONTROLS_RECORD_ID)
        entry_time_end = controls.entry_time_end.time()
        exit_time = controls.exit_time.time()
    except Exception as e:
        entry_time_end = now().time().replace(hour=settings.ENTRY_TIME_END[0], minute=settings.ENTRY_TIME_END[1],
                                              second=settings.ENTRY_TIME_END[2])
        exit_time =  now().time().replace(hour=settings.EXIT_TIME[0], minute=settings.EXIT_TIME[1])
    entry_time_end_str = str(entry_time_end.hour) + ':' + str(entry_time_end.minute)
    exit_time_str = str(exit_time.hour) + ':' + str(exit_time.minute)

def blockEntry():
    global entry_allowed
    entry_allowed = False

def exitAllPositions():
    global exit_time_reached
    exit_time_reached = True

def stripDecimalValues(value):
    return '{:.3f}'.format(value)

def sendStatusEmail():
    logging.debug('\n\nsend status email from long scalp called.\n\n')
    try:
        l_monitor = live_monitor['FX3876']
        monitor_status = 'Status for Mock Long Scalp at time : ' + str(now()) \
                         + '\nProfit percent : ' + stripDecimalValues(l_monitor.net_profit_percent) \
                         + '\nProfit : ' + stripDecimalValues(l_monitor.profit) \
                         + '\nCommission : ' + stripDecimalValues(l_monitor.commission) \
                         + '\nFinal Value : ' + stripDecimalValues(l_monitor.current_value) \
                         + '\nStoploss : ' + str(l_monitor.stoploss) \
                         + '\nValue at risk : ' + str(l_monitor.value_at_risk)
        x = send_mail(subject='Mock Long Scalp Status', message=monitor_status,
                      from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=['felixsundar07@gmail.com'], fail_silently=False)
    except Exception as e:
        logging.debug('\n\n\n\nexception while sending status email:\n\n{}\n\n'.format(e))
