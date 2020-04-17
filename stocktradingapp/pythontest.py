import logging
import time
from datetime import datetime
from time import sleep

import pytz
import schedule
from django.utils.timezone import now

from stock_project import settings
logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

def runTests():
    logging.debug('schedule started...')
    logging.debug('tiMe : {}'.format(time.time()))
    logging.debug('localtiMe : {}'.format(time.localtime()))
    logging.debug('gmtiMe : {}'.format(time.gmtime()))
    logging.debug('timezOne : {}'.format(time.timezone))
    logging.debug('django time : {}'.format(now()))
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

def logtime():
    logging.debug('message by scheduled run at......................... {}'.format(datetime.now(tz=pytz.timezone(settings.TIME_ZONE))))
