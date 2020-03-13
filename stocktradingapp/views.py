import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render

# Create your views here.
from kiteconnect import KiteConnect

from stock_project import settings

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