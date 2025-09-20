
#users/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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
    # NEW: Specific approvals for features
    can_create_five_min_fun = models.BooleanField(default=False, help_text="Superadmin approval for creating 5-Min Fun")
    can_create_routine = models.BooleanField(default=False, help_text="Superadmin approval for creating Routines")
    def __str__(self):
        return self.store_name

class UserProfile(models.Model):
    USER_ROLES = (
        ('caregiver', 'Caregiver'),
        ('vendor', 'Vendor'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=USER_ROLES, default='caregiver')
    phone_number = models.CharField(max_length=15, blank=True)
    def __str__(self):
        return f"{self.user.username} - {self.role}"

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
