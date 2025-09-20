
#users/admin.py
from django.contrib import admin
from .models import UserProfile, KidProfile, VendorProfile, FamilyCaregiver

# NO admin.site.register lines AT ALL - decorators only!

@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ['store_name', 'user', 'is_approved', 'can_create_five_min_fun', 'can_create_routine', 'rating']
    list_filter = ['is_approved', 'can_create_five_min_fun', 'can_create_routine']
    search_fields = ['store_name', 'user__username', 'contact_email']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone_number']
    list_filter = ['role']
    search_fields = ['user__username', 'phone_number']

@admin.register(FamilyCaregiver)
class FamilyCaregiverAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'user', 'phone_number']
    search_fields = ['first_name', 'last_name', 'user__username']

@admin.register(KidProfile)
class KidProfileAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'caregiver', 'birthday']
    list_filter = ['birthday']
    search_fields = ['first_name', 'caregiver__user__username']