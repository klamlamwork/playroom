
#chatbot/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat_view, name='chatbot'),
    #path('ai-plan/', views.ai_plan_recommend, name='ai_plan_recommend'),
]
