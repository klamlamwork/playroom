
# Updated users/admin.py (custom display for created_at in UTC as string to avoid conversion)
from django.contrib import admin
from .models import UserProfile, KidProfile, VendorProfile, FamilyCaregiver
from django.utils import timezone

@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ['store_name', 'user', 'created_at_local', 'updated_at_local', 'is_approved']
    list_filter = ['is_approved', 'can_create_five_min_fun', 'can_create_routine']
    search_fields = ['store_name', 'user__username']
    readonly_fields = ['created_at_local', 'updated_at_local', 'admin_timezone_note']
    fieldsets = [
        ('Vendor Info', {'fields': ['user', 'store_name', 'description', 'logo', 'rating', 'contact_email', 'address']}),
        ('Approvals', {'fields': ['is_approved', 'can_create_five_min_fun', 'can_create_routine']}),
        ('Timestamps', {'fields': ['created_at_local', 'updated_at_local']}),
        ('Notes', {'fields': ['admin_timezone_note']}),
    ]
    exclude = ['created_at', 'updated_at']
    def created_at_local(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M:%S') + ' (UTC)'
    created_at_local.short_description = 'Created at (UTC)'

    def updated_at_local(self, obj):
        return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S') + ' (UTC)'
    updated_at_local.short_description = 'Updated at (UTC)'

    def admin_timezone_note(self, obj):
        user_tz = timezone.get_current_timezone()
        offset_hours = user_tz.utcoffset(timezone.now()).total_seconds() / 3600
        return f"Your current timezone is '{user_tz}' (offset: {offset_hours} hours from UTC). Datetimes are stored in UTC; local fields show in object's vendor TZ."
    admin_timezone_note.short_description = "Timezone Note"

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone_number', 'timezone_name', 'city', 'country']  # Fixed: Changed 'iana_timezone' to 'timezone_name'
    list_filter = ['role']
    search_fields = ['user__username', 'phone_number', 'city']

@admin.register(FamilyCaregiver)
class FamilyCaregiverAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'user', 'phone_number']
    search_fields = ['first_name', 'last_name', 'user__username']

@admin.register(KidProfile)
class KidProfileAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'caregiver', 'birthday']
    list_filter = ['birthday']
    search_fields = ['first_name', 'caregiver__user__username']