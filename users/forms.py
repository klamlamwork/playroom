
# Updated users/forms.py (change iana_timezone to timezone_name)
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile, KidProfile, VendorProfile 
from .models import FamilyCaregiver  # Make sure FamilyCaregiver model is defined in users/models.py
from timezonefinder import TimezoneFinder  # NEW: Requires 'pip install timezonefinder'
from .utils import get_current_utc  # Import for real UTC

class CaregiverForm(forms.ModelForm):
    class Meta:
        model = FamilyCaregiver
        fields = ("first_name", "last_name", "phone_number", "avatar")

class CaregiverSignupForm(UserCreationForm):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    phone_number = forms.CharField(max_length=15)
    city = forms.CharField(max_length=255, label="City or Town", widget=forms.TextInput(attrs={'list': 'city-suggestions'}))  # Added attrs to link datalist
    country = forms.CharField(max_length=100, widget=forms.HiddenInput(), required=False)  # Hidden for country
    latitude = forms.FloatField(widget=forms.HiddenInput(), required=False)  
    longitude = forms.FloatField(widget=forms.HiddenInput(), required=False)  
    class Meta:
        model = User
        fields = ('username', 'password1', 'password2', 'first_name', 'last_name')  # Removed 'email'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.date_joined = get_current_utc()  # Set real UTC before save
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            # NEW: Calculate IANA timezone from lat/lon
            lat = self.cleaned_data.get('latitude')
            lon = self.cleaned_data.get('longitude')
            tz = None
            if lat is not None and lon is not None:
                tf = TimezoneFinder()
                tz = tf.timezone_at(lng=lon, lat=lat)
            # CHANGED: Use get_or_create for safety/minimal change
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': 'caregiver',
                    'phone_number': self.cleaned_data['phone_number'],
                    'city': self.cleaned_data['city'],
                    'country': self.cleaned_data['country'],
                    'latitude': lat,
                    'longitude': lon,
                    'timezone_name': tz
                }
            )
            if not created:
                # If existed (from signal), update fields explicitly
                profile.phone_number = self.cleaned_data['phone_number']
                profile.city = self.cleaned_data['city']
                profile.country = self.cleaned_data['country']
                profile.latitude = lat
                profile.longitude = lon
                profile.timezone_name = tz
                profile.save()
        return user
class KidProfileForm(forms.ModelForm):
    class Meta:
        model = KidProfile
        fields = ('first_name', 'birthday')

# For adding multiple kids (we'll use formsets)
#KidFormSet = forms.modelformset_factory(KidProfile, form=KidProfileForm, extra=1, max_num=5)
KidFormSet = forms.modelformset_factory(KidProfile, form=KidProfileForm, extra=0, max_num=5)


class VendorSignupForm(UserCreationForm):
    store_name = forms.CharField(max_length=255)
    description = forms.CharField(widget=forms.Textarea, required=False)
    contact_email = forms.EmailField(required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)
    logo = forms.ImageField(required=False)  # Optional
    city = forms.CharField(max_length=255, label="City or Town", required=False, widget=forms.TextInput(attrs={'list': 'city-suggestions'}))  # Added for vendors (optional)
    country = forms.CharField(max_length=100, widget=forms.HiddenInput(), required=False)  # Added for vendors (optional)
    latitude = forms.FloatField(widget=forms.HiddenInput(), required=False)  
    longitude = forms.FloatField(widget=forms.HiddenInput(), required=False)  

    class Meta:
        model = User
        fields = ('username','password1', 'password2', 'first_name', 'last_name')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.date_joined = get_current_utc()  # NEW: Set real UTC before save
        if commit:
            user.save()
            # NEW: Calculate IANA timezone from lat/lon
            lat = self.cleaned_data.get('latitude')
            lon = self.cleaned_data.get('longitude')
            tz = None
            if lat is not None and lon is not None:
                tf = TimezoneFinder()
                tz = tf.timezone_at(lng=lon, lat=lat)
            # CHANGED: Use get_or_create for safety/minimal change
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': 'vendor',
                    'city': self.cleaned_data.get('city', ''),
                    'country': self.cleaned_data.get('country', ''),
                    'latitude': lat,
                    'longitude': lon,
                    'timezone_name': tz
                }
            )
            if not created:
                # If existed (from signal), update fields explicitly (override role)
                profile.role = 'vendor'
                profile.city = self.cleaned_data.get('city', '')
                profile.country = self.cleaned_data.get('country', '')
                profile.latitude = lat
                profile.longitude = lon
                profile.timezone_name = tz
                profile.save()
            VendorProfile.objects.create(
                user=user,
                store_name=self.cleaned_data['store_name'],
                description=self.cleaned_data['description'],
                contact_email=self.cleaned_data['contact_email'],
                address=self.cleaned_data['address'],
                logo=self.cleaned_data.get('logo'),  # Handle file
                created_at=get_current_utc(),  # Set real UTC for VendorProfile
                city=self.cleaned_data.get('city', ''),  # Sync
                country=self.cleaned_data.get('country', ''),  # Sync if needed, but VendorProfile has city/lat/lon/tz too
                latitude=lat,
                longitude=lon,
                timezone_name=tz  # Sync
            )
        return user