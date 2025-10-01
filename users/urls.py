
#users/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.homepage, name='homepage'),  # <-- ADD THIS: Root URL for public homepage
    path('signup/step1/', views.signup_step1, name='signup_step1'),
    path('signup/step2/', views.signup_step2, name='signup_step2'),
    path('login/', views.user_login, name='login'),
    path('account/', views.my_account, name='my_account'),
    path('dashboard/', views.dashboard, name='dashboard'),  # New
    path('become-vendor/', views.become_vendor, name='become_vendor'),
    path('vendor-dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('logout/', views.user_logout, name='logout'),
    path('nominatim-proxy/', views.nominatim_proxy, name='nominatim_proxy'),
]
