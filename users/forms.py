
# users/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile, KidProfile, VendorProfile 
from .models import FamilyCaregiver  # Make sure FamilyCaregiver model is defined in users/models.py

class CaregiverForm(forms.ModelForm):
    class Meta:
        model = FamilyCaregiver
        fields = ("first_name", "last_name", "phone_number", "avatar")

class CaregiverSignupForm(UserCreationForm):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    phone_number = forms.CharField(max_length=15)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'first_name', 'last_name')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            UserProfile.objects.create(user=user, role='caregiver', phone_number=self.cleaned_data['phone_number'])
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

    class Meta:
        model = User
        fields = ('username','password1', 'password2', 'first_name', 'last_name')

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            UserProfile.objects.create(user=user, role='vendor')  # Set role
            VendorProfile.objects.create(
                user=user,
                store_name=self.cleaned_data['store_name'],
                description=self.cleaned_data['description'],
                contact_email=self.cleaned_data['contact_email'],
                address=self.cleaned_data['address'],
                logo=self.cleaned_data.get('logo')  # Handle file
            )
        return user