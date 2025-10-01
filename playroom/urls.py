
# playroom/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from events import views
from users.views import set_timezone, get_current_utc_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')),  # Include users URLs (now includes homepage)
    path('events/', include('events.urls')),  # All event/routine paths here
    path('set-timezone/', set_timezone, name='set_timezone'),
    path('get_utc/', get_current_utc_view, name='get_utc'),
    path('chatbot/', include('chatbot.urls')),
    # REMOVED: mark_kid_event_completed and mark_caregiver_event_completed (duplicates in events/urls.py)
]

# Add static/media for dev (good you have media; add static if using CSS/JS)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
