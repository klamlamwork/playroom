
#chatbot/urls.py
from django.urls import path
from . import views
from . import views_test   # ← Add this line

urlpatterns = [
    path('chat/', views.chat_view, name='chatbot'),
    path('gemini-simple-test/', views_test.gemini_simple_test, name='gemini_simple_test'),
    #path('ai-plan/', views.ai_plan_recommend, name='ai_plan_recommend'),
]
