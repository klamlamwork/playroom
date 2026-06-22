
#chatbot/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat_view, name='chatbot'),
    path('test-ai/', views.gemini_test_view, name='gemini_test'), 
]
