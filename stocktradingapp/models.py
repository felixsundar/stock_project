from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models

# Create your models here.

class KiteConnectApp(models.Model):
    hstock_user = models.ForeignKey(User, related_name='user_kite_app', on_delete=models.CASCADE, primary_key=True)
    api_key = models.CharField(max_length=100)
    api_secret = models.CharField(max_length=100)

class ZerodhaAccount(models.Model):
    hstock_user = models.ForeignKey(User, related_name='user_zerodha', on_delete=models.CASCADE, primary_key=True)
    access_token = models.CharField(max_length=100)
    access_token_time = models.DateTimeField(null=True, blank=True)
    refresh_token = models.CharField(max_length=100)
    public_token = models.CharField(max_length=100)
    api_key = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    user_name = models.CharField(max_length=100)
    user_shortname = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    user_type = models.CharField(max_length=100)
    broker = models.CharField(max_length=100)
    exchanges = JSONField(null=True, blank=True)
    products = JSONField(null=True, blank=True)
    order_types = JSONField(null=True, blank=True)
    fund_available = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=True)

class Stock(models.Model):
    stock_id = models.AutoField(primary_key=True)
    instrument_token = models.BigIntegerField(unique=True)
    trading_symbol = models.CharField(max_length=20, unique=True)
    stock_name = models.CharField(max_length=100, unique=True)
    mis_margin = models.FloatField()
    co_margin = models.FloatField()
    co_trigger_percent_lower = models.FloatField()
    co_trigger_percent_upper = models.FloatField()
    active = models.BooleanField()

class Controls(models.Model):
    control_id = models.CharField(max_length=40, primary_key=True)
    entry_trigger_percent = models.FloatField(help_text='default: 0.5')
    max_risk_percent_per_trade = models.FloatField(help_text='default: 0.5')
    max_investment_per_position = models.FloatField(help_text='default: 300000.0')
    min_investment_per_position = models.FloatField(help_text='default: 1000.0')
    position_stoploss_percent = models.FloatField(help_text='default: 0.5')
    position_target_stoploss = models.FloatField(help_text='default: 0.1')
    position_target_percent = models.FloatField(help_text='default: 1.0')
    user_stoploss_percent = models.FloatField(help_text='default: 5.0')
    user_target_stoploss = models.FloatField(help_text='default: 1.0')
    user_target_percent = models.FloatField(help_text='default: 10.0')
    entry_time_start = models.DateTimeField(help_text='default: 9:15:04')
    entry_time_end = models.DateTimeField(help_text='default: 15:18:00')
    exit_time = models.DateTimeField(help_text='default: 15:19:00')
    trading_side = models.IntegerField(choices=[(1, 'Short Side'), (2, 'Long Side'), (3, 'Don\'t Trade')], default=1)
