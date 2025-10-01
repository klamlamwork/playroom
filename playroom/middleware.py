
# playroom/middleware.py (define TimezoneMiddleware to prefer profile iana_timezone)
import pytz
from django.utils import timezone

class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = None
        if request.user.is_authenticated:
            try:
                # Changed 'iana_timezone' to 'timezone_name' to match models
                tzname = request.user.userprofile.timezone_name
            except AttributeError:
                pass  # No profile
        if not tzname:
            tzname = request.session.get('user_timezone')
        if tzname:
            try:
                timezone.activate(pytz.timezone(tzname))
            except pytz.UnknownTimeZoneError:
                pass  # Invalid tz, skip
        response = self.get_response(request)
        timezone.deactivate()
        return response

class AdminUTCMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            timezone.activate(pytz.timezone('UTC'))
        response = self.get_response(request)
        return response