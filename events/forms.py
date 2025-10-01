
# events/forms.py
from django import forms
from .models import Event, EventRegistration, FiveMinFun, Routine, KidRoutineAssignment, AgeGroup, SuperPower, FORMAT_CHOICES
from users.models import KidProfile
from django.utils import timezone
import pytz

class EventCreateForm(forms.ModelForm):
    age_groups = forms.ModelMultipleChoiceField(
        queryset=AgeGroup.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Age Groups (select multiple)'
    )
    super_powers = forms.ModelMultipleChoiceField(
        queryset=SuperPower.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Super Powers (select multiple)'
    )

    class Meta:
        model = Event
        fields = [
            'name', 'description', 'photo', 'start_datetime', 'end_datetime',
            'fee', 'location', 'latitude', 'longitude', 'tickets_available', 'tags',
            'age_groups', 'format_type', 'place', 'super_powers'
        ]
        exclude = ['vendor']
        widgets = {
            'start_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'tags': forms.TextInput(attrs={'placeholder': 'e.g., fun, educational'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }
        labels = {
            'name': 'Event Name',
            'description': 'Description',
            'photo': 'Event Photo',
            'start_datetime': 'Start Date & Time (in your local time)',
            'end_datetime': 'End Date & Time (in your local time)',
            'fee': 'Event Fee (0 for free)',
            'location': 'Location',
            'tickets_available': 'Number of Tickets Available',
            'tags': 'Tags',
            'age_groups': 'Age Groups',
            'format_type': 'Format',
            'place': 'Place',
            'super_powers': 'Super Powers',
        }

    def __init__(self, *args, vendor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vendor = vendor

    def clean(self):
        cleaned_data = super().clean()
        format_type = cleaned_data.get('format_type')
        start_datetime = cleaned_data.get('start_datetime')
        end_datetime = cleaned_data.get('end_datetime')

        if format_type != '5-min-play':
            if not start_datetime:
                self.add_error('start_datetime', "This field is required for non-5-min plays.")
            if not end_datetime:
                self.add_error('end_datetime', "This field is required for non-5-min plays.")
            if start_datetime and end_datetime and start_datetime >= end_datetime:
                self.add_error('end_datetime', "End time must be after start time.")

        # Convert local times to UTC based on vendor's timezone (FIX: Use VendorProfile directly)
        if self.vendor and start_datetime and end_datetime:
            # Changed to vendor.vendor_profile.timezone_name (primary source for vendors)
            vendor_tz_str = self.vendor.vendor_profile.timezone_name or 'UTC'
            try:
                vendor_tz = pytz.timezone(vendor_tz_str)
            except pytz.UnknownTimeZoneError:
                vendor_tz = pytz.timezone('UTC')
            # Ensure start_datetime and end_datetime are naive (strip tzinfo if present)
            if start_datetime.tzinfo is not None:
                start_datetime = start_datetime.replace(tzinfo=None)
            if end_datetime.tzinfo is not None:
                end_datetime = end_datetime.replace(tzinfo=None)
            # Localize to vendor's timezone and convert to UTC
            cleaned_data['start_datetime'] = vendor_tz.localize(start_datetime).astimezone(pytz.UTC)
            cleaned_data['end_datetime'] = vendor_tz.localize(end_datetime).astimezone(pytz.UTC)

        return cleaned_data

class EventUpdateForm(EventCreateForm):
    class Meta(EventCreateForm.Meta):
        exclude = ['vendor']

class EventFilterForm(forms.Form):
    age_groups = forms.MultipleChoiceField(
        choices=[(ag.id, ag.name) for ag in AgeGroup.objects.all()],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Age Groups'
    )
    format_type = forms.ChoiceField(  # Single
        choices=[('', 'All Formats')] + list(FORMAT_CHOICES),  # FIXED: Use imported FORMAT_CHOICES
        required=False,
        label='Format Type'
    )
    place = forms.ChoiceField(
        choices=[('', 'All Places'), ('indoor', 'Indoor'), ('outdoor', 'Outdoor')],
        required=False,
        label='Place'
    )
    super_powers = forms.MultipleChoiceField(
        choices=[(sp.id, sp.name) for sp in SuperPower.objects.all()],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Super Powers'
    )

class EventRegistrationForm(forms.ModelForm):
    class Meta:
        model = EventRegistration
        fields = []

class FiveMinFunCreateForm(forms.ModelForm):
    routines = forms.ModelMultipleChoiceField(
        queryset=Routine.objects.none(),
        required=False,
        label='Assign Routines (select multiple to allow caregivers to add them)',
        help_text='Select from your existing routines. Caregivers will see "Add to Routine" buttons for these.'
    )
    age_groups = forms.ModelMultipleChoiceField(
        queryset=AgeGroup.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Age Groups (select multiple)'
    )
    super_powers = forms.ModelMultipleChoiceField(
        queryset=SuperPower.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Super Powers (select multiple)'
    )

    class Meta:
        model = FiveMinFun
        fields = ['name', 'photo', 'instructions', 'audio', 'tags', 'age_groups', 'format_type', 'place', 'super_powers', 'routines']
        exclude = ['vendor']
        widgets = {
            'instructions': forms.Textarea(attrs={'rows': 6}),
            'tags': forms.TextInput(attrs={'placeholder': 'e.g., fun, educational'}),
        }
        labels = {
            'name': '5-Min Fun Name',
            'photo': 'Photo',
            'instructions': 'Instructions',
            'audio': 'Audio File (for voice playback)',
            'tags': 'Tags',
            'age_groups': 'Age Groups',
            'format_type': 'Format',
            'place': 'Place',
            'super_powers': 'Super Powers',
        }

    def __init__(self, *args, vendor=None, **kwargs):
        super().__init__(*args, **kwargs)
        if vendor:
            self.fields['routines'].queryset = Routine.objects.filter(vendor=vendor, is_active=True)

class FiveMinFunUpdateForm(FiveMinFunCreateForm):
    class Meta(FiveMinFunCreateForm.Meta):
        exclude = ['vendor']

    def __init__(self, *args, vendor=None, **kwargs):
        super().__init__(*args, **kwargs)
        if vendor:
            self.fields['routines'].queryset = Routine.objects.filter(vendor=vendor, is_active=True)

class RoutineCreateForm(forms.ModelForm):
    age_groups = forms.ModelMultipleChoiceField(
        queryset=AgeGroup.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Age Groups (select multiple)'
    )
    super_powers = forms.ModelMultipleChoiceField(
        queryset=SuperPower.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Super Powers (select multiple)'
    )

    class Meta:
        model = Routine
        fields = ['name', 'photo', 'instructions', 'age_groups', 'format_type', 'place', 'super_powers']
        exclude = ['vendor']
        widgets = {
            'instructions': forms.Textarea(attrs={'rows': 6}),
        }

class RoutineUpdateForm(RoutineCreateForm):
    class Meta(RoutineCreateForm.Meta):
        exclude = ['vendor']

class KidRoutineAssignmentForm(forms.ModelForm):
    kid = forms.ModelChoiceField(queryset=KidProfile.objects.none(), required=True)

    class Meta:
        model = KidRoutineAssignment
        fields = ['kid', 'frequency', 'day']
        widgets = {
            'day': forms.TextInput(attrs={'placeholder': 'e.g., Monday or 15'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['kid'].queryset = user.kids.all()