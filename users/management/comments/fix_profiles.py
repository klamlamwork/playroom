from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import UserProfile

class Command(BaseCommand):
    help = 'Create missing UserProfiles for existing users'

    def handle(self, *args, **kwargs):
        for user in User.objects.all():
            try:
                # Check if profile exists
                _ = user.userprofile
            except UserProfile.DoesNotExist:
                UserProfile.objects.create(user=user, role='caregiver')  # Default role; adjust if needed
                self.stdout.write(self.style.SUCCESS(f'Created profile for {user.username}'))
        self.stdout.write(self.style.SUCCESS('Finished fixing profiles.'))