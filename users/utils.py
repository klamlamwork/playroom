
# users/utils.py (to avoid circular imports)
import requests
from datetime import datetime
from django.utils import timezone

def get_current_utc():
    try:
        response = requests.get('http://worldtimeapi.org/api/timezone/Etc/UTC.json')
        response.raise_for_status()
        data = response.json()
        # Parse ISO format, replace Z with +00:00 for fromisoformat compatibility
        return datetime.fromisoformat(data['utc_datetime'].replace('Z', '+00:00'))
    except Exception as e:
        print(f"Error fetching UTC time: {e}. Falling back to server time.")
        return timezone.now()