
# events/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.utils.text import slugify

# Shared models for multi-select (Age/Super only)
class AgeGroup(models.Model):
    name = models.CharField(max_length=20, unique=True)
    def __str__(self):
        return self.name

class SuperPower(models.Model):
    name = models.CharField(max_length=20, unique=True)
    def __str__(self):
        return self.name

# Format choices (single-select, aligned for all)
FORMAT_CHOICES = [
    ('hangout', 'Hangout'),
    ('project', 'Project'),
    ('course', 'Course'),
    ('workshop', 'Workshop'),
    ('contest', 'Contest'),
    ('others', 'Others'),
    ('5-min-play', '5-Min Play'),
]

class Event(models.Model):
    name = models.CharField(max_length=255)
    start_datetime = models.DateTimeField()
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    photo = models.URLField(blank=True, null=True)
    end_datetime = models.DateTimeField()
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    location = models.TextField()
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    tickets_available = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    tags = models.CharField(max_length=255, blank=True)
    age_groups = models.ManyToManyField(AgeGroup, blank=True)  # Multi
    format_type = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='workshop')  # Single
    place = models.CharField(max_length=20, choices=[('indoor', 'Indoor'), ('outdoor', 'Outdoor')], default='indoor')
    super_powers = models.ManyToManyField(SuperPower, blank=True)  # Multi
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events', limit_choices_to={'userprofile__role': 'vendor'})
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ['-start_datetime']
    def __str__(self):
        return f"{self.name} ({self.start_datetime})"
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            num = 1
            while Event.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{num}"
                num += 1
            self.slug = slug
        super().save(*args, **kwargs)

class EventRegistration(models.Model):
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name="registrations")
    kids = models.ManyToManyField('users.KidProfile', blank=True, related_name="eventregistrations")
    caregivers = models.ManyToManyField('users.FamilyCaregiver', blank=True, related_name="eventregistrations")
    registered_at = models.DateTimeField(auto_now_add=True)
    with_caregiver = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    class Meta:
        unique_together = ['event', 'registered_at']
    def __str__(self):
        return f"Registration (event: {self.event})"

class CaregiverEventCompletion(models.Model):
    caregiver = models.ForeignKey('users.FamilyCaregiver', on_delete=models.CASCADE, related_name="caregiver_completions")
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name="caregiver_completions")
    date_completed = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('caregiver', 'event', 'date_completed')
    def __str__(self):
        return f"{self.caregiver} completed {self.event} on {self.date_completed}"

class KidEventCompletion(models.Model):
    kid = models.ForeignKey('users.KidProfile', on_delete=models.CASCADE, related_name="kid_completions")
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name="kid_completions")
    date_completed = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('kid', 'event', 'date_completed')
    def __str__(self):
        return f"{self.kid} completed {self.event} on {self.date_completed}"

class FiveMinFun(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    photo = models.URLField(blank=True, null=True)
    instructions = models.TextField()
    audio = models.FileField(upload_to='five_min_fun_audio/', blank=True, null=True)
    tags = models.CharField(max_length=255, blank=True)
    age_groups = models.ManyToManyField(AgeGroup, blank=True)  # Multi
    format_type = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='workshop', blank=True)  # Single
    place = models.CharField(max_length=20, choices=[('indoor', 'Indoor'), ('outdoor', 'Outdoor')], default='indoor', blank=True)
    super_powers = models.ManyToManyField(SuperPower, blank=True)  # Multi
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='five_min_funs', limit_choices_to={'userprofile__role': 'vendor'})
    routines = models.ManyToManyField('Routine', blank=True, related_name='assigned_five_min_funs')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            num = 1
            while FiveMinFun.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{num}"
                num += 1
            self.slug = slug
        super().save(*args, **kwargs)

class KidFiveMinFunCompletion(models.Model):
    kid = models.ForeignKey('users.KidProfile', on_delete=models.CASCADE, related_name="kid_five_min_fun_completions")
    five_min_fun = models.ForeignKey('events.FiveMinFun', on_delete=models.CASCADE, related_name="kid_completions")
    date_completed = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('kid', 'five_min_fun', 'date_completed')
    def __str__(self):
        return f"{self.kid} completed {self.five_min_fun} on {self.date_completed}"

# Vendor Routine Model
class Routine(models.Model):
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='routines', limit_choices_to={'userprofile__role': 'vendor'})
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    photo = models.URLField(blank=True, null=True)
    instructions = models.TextField()
    age_groups = models.ManyToManyField(AgeGroup, blank=True)  # Multi
    format_type = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='workshop')  # Single
    place = models.CharField(max_length=20, choices=[('indoor', 'Indoor'), ('outdoor', 'Outdoor')], default='indoor')
    super_powers = models.ManyToManyField(SuperPower, blank=True)  # Multi
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            num = 1
            while Routine.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{num}"
                num += 1
            self.slug = slug
        super().save(*args, **kwargs)

class KidRoutineAssignment(models.Model):
    caregiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kid_routine_assignments')
    routine = models.ForeignKey(Routine, on_delete=models.CASCADE, related_name='assignments', null=True, blank=True)
    five_min_fun = models.ForeignKey('FiveMinFun', on_delete=models.CASCADE, related_name='routine_assignments', null=True, blank=True)
    frequency = models.CharField(max_length=20, choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='daily')
    day = models.CharField(max_length=20, blank=True)
    kid = models.ForeignKey('users.KidProfile', on_delete=models.CASCADE, related_name='routine_assignments')  # CHANGED: Single kid ForeignKey
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        item_name = self.routine.name if self.routine else self.five_min_fun.name
        return f"Assignment of {item_name} to {self.kid} by {self.caregiver}"

class RoutineInstance(models.Model):
    assignment = models.ForeignKey(KidRoutineAssignment, on_delete=models.CASCADE, related_name='instances')
    kid = models.ForeignKey('users.KidProfile', on_delete=models.CASCADE, related_name='routine_instances')  # Keep for direct filtering
    date = models.DateField()
    completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('assignment', 'kid', 'date')  # Still valid

    def __str__(self):
        
        item_name = self.assignment.routine.name if self.assignment.routine else self.assignment.five_min_fun.name
        return f"{item_name} for {self.kid} on {self.date}"

class KidRoutineCompletion(models.Model):
    kid = models.ForeignKey('users.KidProfile', on_delete=models.CASCADE, related_name="kid_routine_completions")
    routine_instance = models.ForeignKey(RoutineInstance, on_delete=models.CASCADE, related_name="completions")
    date_completed = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('kid', 'routine_instance')

    def __str__(self):
        item_name = self.routine_instance.assignment.routine.name if self.routine_instance.assignment.routine else self.routine_instance.assignment.five_min_fun.name
        return f"{self.kid} completed {item_name} on {self.date_completed}"