import hashlib
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render

# Create your views here.
from django.urls import reverse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp import stockTraderShortStoploss, stockmonitor, stockTraderLongStoploss, stockTraderShortStopprofit, \
    stockTraderLongStopprofit, stockTraderShortFixed, stockTraderLongFixed, stockTraderLongScalpReverse
from stocktradingapp.models import ZerodhaAccount

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

@login_required
def index(request):
    user_zerodha = request.user.user_zerodha.first()
    access_token_valid = validateAccessToken(user_zerodha.access_token_time) if user_zerodha else None
    context = {
        'user_zerodha':user_zerodha,
        'access_token_valid': access_token_valid
    }
    return render(request, template_name='stocktradingapp/user_home.html', context=context)

def validateAccessToken(access_token_time):
    expiry_time = now().replace(hour=8, minute=30, second=0, microsecond=0)
    if now() > expiry_time and access_token_time < expiry_time:
        return False
    return True

@login_required
def authZerodha(request):
    user_kite_app = request.user.user_kite_app.first()
    kite = KiteConnect(user_kite_app.api_key)
    return HttpResponseRedirect(kite.login_url())

@login_required
def authRedirect(request):
    logging.debug('get query params - {}'.format(request.GET))
    request_token = request.GET['request_token']
    user_kite_app = request.user.user_kite_app.first()
    kite = KiteConnect(user_kite_app.api_key)
    zerodha_user_data = kite.generate_session(request_token=request_token, api_secret=user_kite_app.api_secret)
    user_zerodha = request.user.user_zerodha.first()
    if user_zerodha is None:
        user_zerodha = ZerodhaAccount(hstock_user=request.user)
    user_zerodha.access_token = zerodha_user_data['access_token']
    user_zerodha.access_token_time = now()
    user_zerodha.refresh_token = zerodha_user_data['refresh_token']
    user_zerodha.public_token = zerodha_user_data['public_token']
    user_zerodha.api_key = zerodha_user_data['api_key']
    user_zerodha.user_id = zerodha_user_data['user_id']
    user_zerodha.user_name = zerodha_user_data['user_name']
    user_zerodha.user_shortname = zerodha_user_data['user_shortname']
    user_zerodha.email = zerodha_user_data['email']
    user_zerodha.user_type = zerodha_user_data['user_type']
    user_zerodha.broker = zerodha_user_data['broker']
    user_zerodha.exchanges = json.dumps(zerodha_user_data['exchanges'])
    user_zerodha.products = json.dumps(zerodha_user_data['products'])
    user_zerodha.order_types = json.dumps(zerodha_user_data['order_types'])
    user_zerodha.save()
    return HttpResponseRedirect(reverse(index))

@csrf_exempt
def zerodhaPostback(request):
    order_details = json.loads(request.body)
    if verifyCheckSum(order_details):
        if stockmonitor.TRADING_SIDE == stockmonitor.SHORT_STOPPROFIT:
            stockTraderShortStopprofit.postback_queue.put(item=order_details, block=True)
        elif stockmonitor.TRADING_SIDE == stockmonitor.LONG_STOPPROFIT:
            stockTraderLongScalpReverse.postback_queue.put(item=order_details, block=True)
        elif stockmonitor.TRADING_SIDE == stockmonitor.SHORT_STOPLOSS:
            stockTraderShortStoploss.postback_queue.put(item=order_details, block=True)
        elif stockmonitor.TRADING_SIDE == stockmonitor.LONG_STOPLOSS:
            stockTraderLongStoploss.postback_queue.put(item=order_details, block=True)
        elif stockmonitor.TRADING_SIDE == stockmonitor.SHORT_FIXED:
            stockTraderShortFixed.postback_queue.put(item=order_details, block=True)
        elif stockmonitor.TRADING_SIDE == stockmonitor.LONG_FIXED:
            stockTraderLongFixed.postback_queue.put(item=order_details, block=True)
        else:
            return HttpResponse('algo trading not running now.')
    return HttpResponse('order details received.')

def verifyCheckSum(order_details):
    try:
        user_zerodha = ZerodhaAccount.objects.get(user_id=order_details['user_id'])
        kite_app = user_zerodha.hstock_user.user_kite_app.first()
        if kite_app is None:
            return False
        api_secret = kite_app.api_secret
        stringToHash = order_details['order_id'] + order_details['order_timestamp'] + api_secret
        hashedString = hashlib.sha256(stringToHash.encode()).hexdigest()
        if hashedString == order_details['checksum']:
            return True
    except:
        pass
    return False
