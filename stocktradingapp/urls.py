from django.urls import path, include

from . import views

urlpatterns = [
    path('accounts/', include('django.contrib.auth.urls')),
    path('', views.index, name='index'),
    path('auth/zerodha/', views.authZerodha, name='authZerodha'),
    path('auth/zerodha/redirect/', views.authRedirect, name='redirect'),
    path('zerodha/postback/', views.zerodhaPostback, name='postback'),
]