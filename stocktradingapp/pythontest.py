import logging
import threading
import time
from datetime import datetime
from time import sleep

import pytz
import schedule
from django.utils.timezone import now

from stock_project import settings
logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

# positions = [{'name': 'felix', 'age': 24, 'gender': 'male'},
#              {'name': 'felix', 'age': 25, 'gender': 'male'},
#              {'name': 'felix', 'age': 26, 'gender': 'male'},
#              {'name': 'felix', 'age': 27, 'gender': 'male'},
#              {'name': 'felix', 'age': 28, 'gender': 'male'}]


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

value = 100000
commission = calculateCommission(value, value)
profit = (100.15 * value / 100.0) - value
netprofit = profit - commission
print('profit - ', profit)
print('commission - ', commission)
print('netprofit - ', netprofit)
print('netprofit percent - ', netprofit * 100.0 / value)

# target_price = (100.0 + 0.13) * 240.0 / 100.0
# limit_price = float('{:.1f}'.format(target_price))
# limit_price -= 0.1
# while limit_price < target_price:
#     limit_price += 0.05
# print(float('{:.2f}'.format(limit_price)))

# def scheduleExit():
#     schedule.every().day.at('16:21').do(logtime)
    # logging.debug('schedule started...')
    # logging.debug('tiMe : {}'.format(time.time()))
    # logging.debug('localtiMe : {}'.format(time.localtime()))
    # logging.debug('gmtiMe : {}'.format(time.gmtime()))
    # logging.debug('timezOne : {}'.format(time.timezone))
    # logging.debug('django time : {}'.format(now()))
    # expiry_time = now().replace(hour=8, minute=30, second=0, microsecond=0)
    # current_time = now()
    # token_time = now().replace(hour=8, minute=31, second=0, microsecond=0)
    # print('\n\nexpiry.........', expiry_time, '..........\n\n')
    # print('\n\ntoken.........', token_time, '..........\n\n')
    # print('\n\ncurrent.........', current_time, '..........\n\n')
    # if current_time > expiry_time and token_time < expiry_time:
    #     print('\n\n..........expired...........\n\n')
    # else:
    #     print('\n\n..........valid.............\n\n')
#
#     for position in positions:
#         if position['age'] == 27:
#             print(positions)
#             startthread()
#             sleep(2)
#             print(positions)
#             print(position)
#             positions.remove(position)
#             print(positions)
#
# def startthread():
#     t = threading.Thread(target=changeAge, daemon=True, name='agethread')
#     t.start()
#
# def changeAge():
#     for position in positions:
#         if position['age'] == 27:
#             position['age'] = 35

