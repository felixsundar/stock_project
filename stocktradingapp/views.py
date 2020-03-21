import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render

# Create your views here.
from django.urls import reverse
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp.models import ZerodhaAccount

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

@login_required
def index(request):
    context = {
        'user_zerodha':request.user.user_zerodha.first()
    }
    return render(request, template_name='stocktradingapp/user_home.html', context=context)

@login_required
def authZerodha(request):
    kite = KiteConnect(settings.KITE_API_KEY)
    return HttpResponseRedirect(kite.login_url())

@login_required
def authRedirect(request):
    logging.debug('get query params - {}'.format(request.GET))
    request_token = request.GET['request_token']
    kite = KiteConnect(settings.KITE_API_KEY)
    zerodha_user_data = kite.generate_session(request_token=request_token, api_secret=settings.KITE_API_SECRET)
    user_zerodha = request.user.user_zerodha.first()
    if user_zerodha is None:
        user_zerodha = ZerodhaAccount(hstock_user=request.user)
    user_zerodha.access_token = zerodha_user_data['access_token']
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