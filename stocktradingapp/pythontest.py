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
    schedule.every().day.at('16:06').do(logtime)
    logging.debug('schedule started...')
    logging.debug('tiMe : {}'.format(time.time()))
    logging.debug('localtiMe : {}'.format(time.localtime()))
    logging.debug('gmtiMe : {}'.format(time.gmtime()))
    logging.debug('timezOne : {}'.format(time.timezone))
    logging.debug('django time : {}'.format(now()))
    while True:
        schedule.run_pending()
        sleep(1)

def logtime():
    logging.debug('message by scheduled run at......................... {}'.format(datetime.now(tz=pytz.timezone(settings.TIME_ZONE))))
