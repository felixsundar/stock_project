import logging
from datetime import datetime
from time import sleep

import pytz
import schedule

from stock_project import settings
logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

def runTests():
    schedule.every().day.at('11:00').do(logtime)
    while True:
        schedule.run_pending()
        sleep(1)

def logtime():
    logging.debug('message by scheduled run at {}'.format(datetime.now(tz=pytz.timezone(settings.TIME_ZONE))))