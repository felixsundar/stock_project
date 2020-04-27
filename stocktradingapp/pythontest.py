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

def runTests():
    schedule.every().day.at('16:19').do(scheduleExit)
    while True:
        schedule.run_pending()
        sleep(1)

def scheduleExit():
    schedule.every().day.at('16:21').do(logtime)
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

def logtime():
    print('message by scheduled run at......................... {}'.format(now()))
