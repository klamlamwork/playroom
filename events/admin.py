#events/admin.py
from django.contrib import admin
from .models import (
    Event, EventRegistration, CaregiverEventCompletion, KidEventCompletion,
    FiveMinFun, KidFiveMinFunCompletion, Routine, KidRoutineAssignment,
    RoutineInstance, KidRoutineCompletion, AgeGroup, SuperPower  # REMOVED: FormatType
)

@admin.register(AgeGroup)
class AgeGroupAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

@admin.register(SuperPower)
class SuperPowerAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_datetime', 'get_age_groups_display', 'format_type', 'place', 'get_super_powers_display', 'vendor', 'is_active']  # FIXED: format_type single; removed format_types
    list_filter = ['format_type', 'place', 'is_active', 'vendor', 'age_groups', 'super_powers']  # FIXED: Single format_type + M2M
    search_fields = ['name', 'description', 'tags']
    inlines = [EventRegistrationInline]
    date_hierarchy = 'start_datetime'

    def get_age_groups_display(self, obj):
        return ', '.join([ag.name for ag in obj.age_groups.all()])  # Multi
    get_age_groups_display.short_description = 'Age Groups'

    def get_super_powers_display(self, obj):
        return ', '.join([sp.name for sp in obj.super_powers.all()])  # Multi
    get_super_powers_display.short_description = 'Super Powers'

@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ['event', 'registered_at', 'get_kids_display', 'get_caregivers_display', 'is_completed']
    list_filter = ['registered_at', 'is_completed', 'with_caregiver']
    raw_id_fields = ['event']

    def get_kids_display(self, obj):
        return ', '.join([kid.first_name for kid in obj.kids.all()])
    get_kids_display.short_description = 'Kids'

    def get_caregivers_display(self, obj):
        return ', '.join([cg.first_name for cg in obj.caregivers.all()])
    get_caregivers_display.short_description = 'Caregivers'

@admin.register(CaregiverEventCompletion)
class CaregiverEventCompletionAdmin(admin.ModelAdmin):
    list_display = ['caregiver', 'event', 'date_completed']
    list_filter = ['date_completed']
    search_fields = ['caregiver__first_name', 'event__name']

@admin.register(KidEventCompletion)
class KidEventCompletionAdmin(admin.ModelAdmin):
    list_display = ['kid', 'event', 'date_completed']
    list_filter = ['date_completed']
    search_fields = ['kid__first_name', 'event__name']

class KidRoutineAssignmentInline(admin.TabularInline):
    model = KidRoutineAssignment
    extra = 0

@admin.register(FiveMinFun)
class FiveMinFunAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_age_groups_display', 'format_type', 'place', 'get_super_powers_display', 'vendor', 'is_active']  # FIXED: Single format_type
    list_filter = ['format_type', 'place', 'is_active', 'vendor', 'age_groups', 'super_powers']  # FIXED: Single + M2M
    search_fields = ['name', 'instructions', 'tags']
    inlines = [KidRoutineAssignmentInline]

    def get_age_groups_display(self, obj):
        return ', '.join([ag.name for ag in obj.age_groups.all()])
    get_age_groups_display.short_description = 'Age Groups'

    def get_super_powers_display(self, obj):
        return ', '.join([sp.name for sp in obj.super_powers.all()])
    get_super_powers_display.short_description = 'Super Powers'

@admin.register(KidFiveMinFunCompletion)
class KidFiveMinFunCompletionAdmin(admin.ModelAdmin):
    list_display = ['kid', 'five_min_fun', 'date_completed']
    list_filter = ['date_completed']
    search_fields = ['kid__first_name', 'five_min_fun__name']

@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_age_groups_display', 'format_type', 'place', 'get_super_powers_display', 'vendor', 'is_active']  # FIXED: Single format_type
    list_filter = ['format_type', 'place', 'is_active', 'vendor', 'age_groups', 'super_powers']  # FIXED: Single + M2M
    search_fields = ['name', 'instructions']

    def get_age_groups_display(self, obj):
        return ', '.join([ag.name for ag in obj.age_groups.all()])
    get_age_groups_display.short_description = 'Age Groups'

    def get_super_powers_display(self, obj):
        return ', '.join([sp.name for sp in obj.super_powers.all()])
    get_super_powers_display.short_description = 'Super Powers'

@admin.register(KidRoutineAssignment)
class KidRoutineAssignmentAdmin(admin.ModelAdmin):
    list_display = ['kid', 'get_routine_or_fun', 'frequency', 'day', 'created_at']
    list_filter = ['frequency', 'created_at']
    search_fields = ['kid__first_name', 'routine__name', 'five_min_fun__name']

    def get_routine_or_fun(self, obj):
        if obj.routine:
            return obj.routine.name
        return obj.five_min_fun.name if obj.five_min_fun else 'N/A'
    get_routine_or_fun.short_description = 'Routine/Fun'

@admin.register(RoutineInstance)
class RoutineInstanceAdmin(admin.ModelAdmin):
    list_display = ['get_assignment_item', 'kid', 'date', 'completed']
    list_filter = ['date', 'completed']
    search_fields = ['kid__first_name']

    def get_assignment_item(self, obj):
        return obj.assignment.routine.name if obj.assignment.routine else obj.assignment.five_min_fun.name
    get_assignment_item.short_description = 'Item'

@admin.register(KidRoutineCompletion)
class KidRoutineCompletionAdmin(admin.ModelAdmin):
    list_display = ['kid', 'get_routine_instance', 'date_completed']
    list_filter = ['date_completed']
    search_fields = ['kid__first_name']

    def get_routine_instance(self, obj):
        return str(obj.routine_instance)
    get_routine_instance.short_description = 'Routine Instance'