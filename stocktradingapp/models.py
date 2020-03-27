from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models

# Create your models here.

class ZerodhaAccount(models.Model):
    hstock_user = models.ForeignKey(User, related_name='user_zerodha', on_delete=models.CASCADE, primary_key=True)
    access_token = models.CharField(max_length=100)
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

class Stock(models.Model):
    stock_id = models.AutoField(primary_key=True)
    instrument_token = models.BigIntegerField(unique=True)
    trading_symbol = models.CharField(max_length=20, unique=True)
    stock_name = models.CharField(max_length=100, unique=True)
    mis_margin = models.FloatField()
    co_margin = models.FloatField()
    active = models.BooleanField()
