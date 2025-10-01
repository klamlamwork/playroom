
# users/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import pytz
from timezonefinder import TimezoneFinder
from django.db.models.signals import post_save
from django.dispatch import receiver


class VendorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    store_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=False)
    logo = models.ImageField(upload_to='vendor_logos/', blank=True, null=True)
    rating = models.FloatField(default=0.0)
    contact_email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    can_create_five_min_fun = models.BooleanField(default=False, help_text="Superadmin approval for creating 5-Min Fun")
    can_create_routine = models.BooleanField(default=False, help_text="Superadmin approval for creating Routines")
    city = models.CharField(max_length=255, blank=True, null=True)  # Added for location
    country = models.CharField(max_length=100, blank=True, null=True)  
    latitude = models.FloatField(null=True, blank=True)  # Added for timezone derivation
    longitude = models.FloatField(null=True, blank=True)  # Added for timezone derivation
    timezone_name = models.CharField(max_length=100, blank=True, null=True, choices=[(tz, tz) for tz in pytz.all_timezones])  

    def __str__(self):
        return self.store_name
    def save(self, *args, **kwargs):
        if self.latitude is not None and self.longitude is not None and not self.timezone_name:
            tf = TimezoneFinder()
            self.timezone_name = tf.timezone_at(lng=self.longitude, lat=self.latitude)
        super().save(*args, **kwargs)
        if self.timezone_name:
            try:
                profile = self.user.userprofile
                if profile.timezone_name != self.timezone_name:
                    profile.timezone_name = self.timezone_name
                    profile.save(update_fields=['timezone_name'])
            except UserProfile.DoesNotExist:
                pass
class UserProfile(models.Model):
    USER_ROLES = (
        ('caregiver', 'Caregiver'),
        ('vendor', 'Vendor'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=USER_ROLES, default='caregiver')
    phone_number = models.CharField(max_length=15, blank=True)
    city = models.CharField(max_length=255, blank=True, null=True)  # City or Town
    country = models.CharField(max_length=100, blank=True, null=True)  
    latitude = models.FloatField(null=True, blank=True)  
    longitude = models.FloatField(null=True, blank=True) 
    timezone_name = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self):
            return f"{self.user.username} - {self.role}"

    def save(self, *args, **kwargs):
        if self.latitude is not None and self.longitude is not None and not self.timezone_name:
            tf = TimezoneFinder()
            self.timezone_name = tf.timezone_at(lng=self.longitude, lat=self.latitude)
        super().save(*args, **kwargs)
class FamilyCaregiver(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='family_caregivers')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='caregiver_avatars/', blank=True, null=True)
    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

class KidProfile(models.Model):
    caregiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kids')
    first_name = models.CharField(max_length=100)
    birthday = models.DateField()
    def __str__(self):
        return self.first_name
    
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, role='caregiver')  # Default to 'caregiver'; adjust logic if needed (e.g., check if vendor)