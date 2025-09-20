
#events/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Event, EventRegistration, FiveMinFun, Routine, KidRoutineAssignment, AgeGroup, SuperPower, FORMAT_CHOICES, KidFiveMinFunCompletion, RoutineInstance,KidRoutineCompletion,CaregiverEventCompletion, KidEventCompletion  # FIXED: Added FORMAT_CHOICES import
from users.models import FamilyCaregiver, KidProfile
from .forms import EventCreateForm, EventUpdateForm, EventFilterForm, EventRegistrationForm, FiveMinFunCreateForm, FiveMinFunUpdateForm, RoutineCreateForm, RoutineUpdateForm, KidRoutineAssignmentForm
from users.models import UserProfile
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
import logging
from django.db.utils import IntegrityError
import json
from datetime import timedelta, date
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY

logger = logging.getLogger(__name__)

# Generate RoutineInstances based on frequency (EXTENDED: next 12 months)
def generate_routine_instances(assignment, kid):
    today = date.today()
    end_date = today + timedelta(days=365)  # EXTENDED: 12 months ahead
    # Delete future instances (date >= today) for this SPECIFIC assignment and kid to prevent duplicates, keep past ones
    RoutineInstance.objects.filter(assignment=assignment, kid=kid, date__gte=today).delete()
    if assignment.frequency == 'daily':
        dates = rrule(DAILY, dtstart=today, until=end_date)
    elif assignment.frequency == 'weekly':
        weekday_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
        weekday = weekday_map.get(assignment.day, 0)
        dates = rrule(WEEKLY, dtstart=today, until=end_date, byweekday=weekday)
    elif assignment.frequency == 'monthly':
        day = int(assignment.day) if assignment.day.isdigit() else 1
        dates = rrule(MONTHLY, dtstart=today, until=end_date, bymonthday=day)
    else:
        return
    for dt in dates:
        RoutineInstance.objects.get_or_create(assignment=assignment, kid=kid, date=dt.date())

@login_required
def create_event(request):
    try:
        profile = request.user.userprofile
        if profile.role != 'vendor':
            messages.error(request, "Only vendors can create events.")
            return redirect('vendor_dashboard')
        if not request.user.vendor_profile.is_approved:
            messages.error(request, "Your vendor account is not approved yet. Please wait for approval before creating events.")
            return redirect('vendor_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, "Profile not found. Please complete signup.")
        return redirect('vendor_dashboard')
    if request.method == 'POST':
        form = EventCreateForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.vendor = request.user
            event.save()
            form.save_m2m()  # For M2M age/super
            messages.success(request, "Event created successfully!")
            return redirect('vendor_dashboard')
    else:
        form = EventCreateForm()
    return render(request, 'events/create_event.html', {'form': form})

def event_list(request):
    now = timezone.now()
    events = Event.objects.filter(is_active=True, end_datetime__gt=now).order_by('start_datetime')
    five_min_funs = FiveMinFun.objects.filter(is_active=True).order_by('-created_at')
    age_ids = request.GET.getlist('age_groups')
    format_type = request.GET.get('format_type')  # Single
    place = request.GET.get('place')
    power_ids = request.GET.getlist('super_powers')
    if age_ids:
        events = events.filter(age_groups__id__in=age_ids)
        five_min_funs = five_min_funs.filter(age_groups__id__in=age_ids)
    if format_type:
        events = events.filter(format_type=format_type)
        five_min_funs = five_min_funs.filter(format_type=format_type)
    if place:
        events = events.filter(place=place)
        five_min_funs = five_min_funs.filter(place=place)
    if power_ids:
        events = events.filter(super_powers__id__in=power_ids)
        five_min_funs = five_min_funs.filter(super_powers__id__in=power_ids)
    filter_form = EventFilterForm(request.GET)
    items = []
    for e in events:
        e.type = 'event'
        items.append(e)
    for f in five_min_funs:
        f.type = 'five_min_fun'
        items.append(f)
    items.sort(key=lambda x: x.created_at, reverse=True)
    event_markers = [
        {
            "name": event.name,
            "lat": event.latitude,
            "lng": event.longitude,
            "id": event.id,
            "location": event.location,
            "start_datetime": event.start_datetime.strftime("%Y-%m-%d %H:%M"),
            "detail_url": f"/events/{event.slug}/",
        }
        for event in events if event.latitude is not None and event.longitude is not None
    ]
    context = {
        'items': items,
        'filter_form': filter_form,
        'num_events': len(items),
        'event_markers': json.dumps(event_markers),
    }
    return render(request, 'events/event_list.html', context)

@login_required
def manage_event(request, event_id):
    if UserProfile.objects.get(user=request.user).role != 'vendor':
        messages.error(request, "Only vendors can manage events.")
        return redirect('vendor_dashboard')
    event = get_object_or_404(Event, id=event_id, vendor=request.user)
    registrations = event.registrations.all().order_by('-registered_at')
    # FIXED: Pure caregiver only if exclusively 'caregivers' (no kid ages)
    is_caregiver_only = event.age_groups.filter(name='caregivers').exists() and not event.age_groups.filter(name__in=['0-3', '3-10', '11+']).exists()
    if is_caregiver_only:
        tickets_registered = sum(r.caregivers.count() for r in registrations)  # Only caregivers
        registration_count = tickets_registered
    else:
        # FIXED: For kid events (with or without caregivers): Count ONLY kids
        tickets_registered = sum(r.kids.count() for r in registrations)
        registration_count = tickets_registered
    tickets_left = event.tickets_available - tickets_registered
    if request.method == 'POST':
        form = EventUpdateForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            event = form.save(commit=False)
            event.vendor = request.user
            event.save()
            form.save_m2m()  # For M2M age/super
            messages.success(request, "Event updated successfully!")
            return redirect('manage_event', event_id=event.id)
    else:
        form = EventUpdateForm(instance=event)
    return render(request, 'events/manage_event.html', {
        'event': event,
        'form': form,
        'registrations': registrations,
        'tickets_left': tickets_left,
        'registration_count': registration_count,
    })

@login_required
def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug, is_active=True)
    selected_ages = ', '.join([ag.name for ag in event.age_groups.all()]) if event.age_groups.exists() else "None selected"
    selected_powers = ', '.join([sp.name for sp in event.super_powers.all()]) if event.super_powers.exists() else "None selected"
    user = request.user
    kids = user.kids.all()
    caregivers = user.family_caregivers.all()
    registrations = EventRegistration.objects.filter(event=event)
    # FIXED: Pure caregiver only if exclusively 'caregivers' (no kid ages)
    is_caregiver_only = event.age_groups.filter(name='caregivers').exists() and not event.age_groups.filter(name__in=['0-3', '3-10', '11+']).exists()
    if is_caregiver_only:
        tickets_registered = sum(r.caregivers.count() for r in registrations)  # Only caregivers
    else:
        # FIXED: For kid events (with or without caregivers): Count ONLY kids
        tickets_registered = sum(r.kids.count() for r in registrations)
    tickets_left = event.tickets_available - tickets_registered
    show_kids = not is_caregiver_only  # FIXED: Show kids unless pure caregiver
    already_registered = registrations.filter(caregivers__in=caregivers).exists()

    can_complete_today = False
    available_kids = []
    if request.user.is_authenticated and event.format_type == '5-min-play':
        today = timezone.now().date()
        completed_kid_ids = KidEventCompletion.objects.filter(
            event=event, date_completed=today, kid__caregiver=request.user
        ).values_list('kid__id', flat=True)
        available_kids = kids.exclude(id__in=completed_kid_ids)
        can_complete_today = available_kids.exists()

    if request.method == 'POST' and not already_registered and tickets_left > 0:
        if is_caregiver_only:  # FIXED: Pure caregiver only
            selected_caregiver_ids = request.POST.getlist('caregivers')
            if not selected_caregiver_ids:
                return render(request, 'events/event_detail.html', {
                    'event': event, 'kids': kids, 'caregivers': caregivers, 'error': 'Please select at least one caregiver.',
                    'already_registered': already_registered, 'tickets_left': tickets_left, 'show_kids': show_kids, 'can_complete_today': can_complete_today, 'available_kids': available_kids,
                    'selected_ages': selected_ages, 'selected_powers': selected_powers,
                })
            if len(selected_caregiver_ids) > tickets_left:
                return render(request, 'events/event_detail.html', {
                    'event': event, 'kids': kids, 'caregivers': caregivers, 'error': 'Not enough tickets for that many caregivers.',
                    'already_registered': already_registered, 'tickets_left': tickets_left, 'show_kids': show_kids, 'can_complete_today': can_complete_today, 'available_kids': available_kids,
                    'selected_ages': selected_ages, 'selected_powers': selected_powers,
                })
            registration = EventRegistration.objects.create(event=event)
            registration.caregivers.set(selected_caregiver_ids)
            registration.save()
        else:  # Kid or mixed: Allow kids + caregivers, but deduct only kids
            selected_kids_ids = request.POST.getlist('kids')
            selected_caregiver_ids = request.POST.getlist('caregivers')
            if not selected_kids_ids and not selected_caregiver_ids:
                return render(request, 'events/event_detail.html', {
                    'event': event, 'kids': kids, 'caregivers': caregivers, 'error': 'Select at least one kid or caregiver.',
                    'already_registered': already_registered, 'tickets_left': tickets_left, 'show_kids': show_kids, 'can_complete_today': can_complete_today, 'available_kids': available_kids,
                    'selected_ages': selected_ages, 'selected_powers': selected_powers,
                })
            num_requested = len(selected_kids_ids)  # FIXED: Deduct only kids (ignore caregivers)
            if num_requested > tickets_left:
                return render(request, 'events/event_detail.html', {
                    'event': event, 'kids': kids, 'caregivers': caregivers, 'error': 'Not enough tickets for that many kids.',
                    'already_registered': already_registered, 'tickets_left': tickets_left, 'show_kids': show_kids, 'can_complete_today': can_complete_today, 'available_kids': available_kids,
                    'selected_ages': selected_ages, 'selected_powers': selected_powers,
                })
            registration = EventRegistration.objects.create(event=event)
            if selected_kids_ids:
                registration.kids.set(selected_kids_ids)
            if selected_caregiver_ids:
                registration.caregivers.set(selected_caregiver_ids)  # Save but not deduct
            registration.save()
        return redirect('event_detail', slug=event.slug)
    return render(request, 'events/event_detail.html', {
        'event': event,
        'kids': kids,
        'caregivers': caregivers,
        'already_registered': already_registered,
        'tickets_left': tickets_left,
        'show_kids': show_kids,
        'can_complete_today': can_complete_today,
        'available_kids': available_kids,
        'selected_ages': selected_ages,
        'selected_powers': selected_powers,
    })

@login_required
def delete_event(request, event_id):
    if UserProfile.objects.get(user=request.user).role != 'vendor':
        messages.error(request, "Only vendors can delete events.")
        return redirect('vendor_dashboard')
    event = get_object_or_404(Event, id=event_id, vendor=request.user)
    if request.method == 'POST':
        event.is_active = False
        event.save()
        messages.success(request, f"{event.name} has been deactivated.")
        return redirect('vendor_dashboard')
    return render(request, 'events/delete_event.html', {'event': event})

@require_POST
@login_required
def mark_caregiver_event_completed(request):
    caregiver_id = request.POST.get("caregiver_id")
    event_id = request.POST.get("event_id")
    event_date = request.POST.get("event_date")
    try:
        caregiver = FamilyCaregiver.objects.get(id=caregiver_id, user=request.user)
        event = Event.objects.get(id=event_id)
        if event.format_type != '5-min-play':
            if not EventRegistration.objects.filter(event=event, caregivers=caregiver).exists():
                return JsonResponse({"success": False, "error": "Not registered for this event."})
        completion, created = CaregiverEventCompletion.objects.get_or_create(
            caregiver=caregiver,
            event=event,
            date_completed=event_date
        )
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@require_POST
@login_required
def mark_kid_event_completed(request):
    event_id = request.POST.get('event_id')
    try:
        event = get_object_or_404(Event, id=event_id)
        date_completed = request.POST.get('event_date', timezone.now().date().isoformat())
        kid_ids = request.POST.getlist('kid_ids[]')
        if not kid_ids:
            kid_id = request.POST.get('kid_id')
            if kid_id:
                kid_ids = [kid_id]
        if not kid_ids:
            return JsonResponse({'success': False, 'error': 'No kids selected.'})
        created_count = 0
        already_completed = []
        not_registered = []
        for kid_id in kid_ids:
            kid = get_object_or_404(KidProfile, id=kid_id, caregiver=request.user)
            if event.format_type != '5-min-play':
                if not EventRegistration.objects.filter(event=event, kids=kid).exists():
                    not_registered.append(kid.first_name)
                    continue
            completion, created = KidEventCompletion.objects.get_or_create(
                kid=kid, event=event, date_completed=date_completed
            )
            if created:
                created_count += 1
            else:
                already_completed.append(kid.first_name)
        if created_count > 0:
            message = f"Marked as completed for {created_count} kid(s)!"
            if already_completed:
                message += f" Skipped already completed: {', '.join(already_completed)}"
            if not_registered:
                message += f" Skipped not registered: {', '.join(not_registered)}"
            return JsonResponse({'success': True, 'message': message})
        else:
            error_msg = ""
            if already_completed:
                error_msg += f"Already completed: {', '.join(already_completed)}. "
            if not_registered:
                error_msg += f"Not registered: {', '.join(not_registered)}."
            if not error_msg:
                error_msg = "Unknown error."
            return JsonResponse({'success': False, 'error': error_msg})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Views for FiveMinFun - Added approval check
@login_required
def create_five_min_fun(request):
    try:
        profile = request.user.userprofile
        if profile.role != 'vendor':
            messages.error(request, "Only vendors can create 5-Min Fun.")
            return redirect('vendor_dashboard')
        if not request.user.vendor_profile.is_approved:
            messages.error(request, "Your vendor account is not approved yet. Please wait for approval before creating 5-Min Fun.")
            return redirect('vendor_dashboard')
        # Specific approval check
        if not request.user.vendor_profile.can_create_five_min_fun:
            messages.error(request, "You are not approved to create 5-Min Fun. Contact superadmin for access.")
            return redirect('vendor_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, "Profile not found. Please complete signup.")
        return redirect('vendor_dashboard')
    if request.method == 'POST':
        form = FiveMinFunCreateForm(request.POST, request.FILES, vendor=request.user)
        if form.is_valid():
            five_min_fun = form.save(commit=False)
            five_min_fun.vendor = request.user
            five_min_fun.save()
            form.save_m2m()
            messages.success(request, "5-Min Fun created successfully!")
            return redirect('vendor_dashboard')
    else:
        form = FiveMinFunCreateForm(vendor=request.user)
    return render(request, 'events/create_five_min_fun.html', {'form': form})

@login_required
def manage_five_min_fun(request, five_min_fun_id):
    if UserProfile.objects.get(user=request.user).role != 'vendor':
        messages.error(request, "Only vendors can manage 5-Min Fun.")
        return redirect('vendor_dashboard')
    five_min_fun = get_object_or_404(FiveMinFun, id=five_min_fun_id, vendor=request.user)
    # Specific approval check for management
    if not request.user.vendor_profile.can_create_five_min_fun:
        messages.error(request, "You are not approved to manage 5-Min Fun. Contact superadmin for access.")
        return redirect('vendor_dashboard')
    if request.method == 'POST':
        form = FiveMinFunUpdateForm(request.POST, request.FILES, instance=five_min_fun, vendor=request.user)
        if form.is_valid():
            five_min_fun = form.save(commit=False)
            five_min_fun.vendor = request.user
            five_min_fun.save()
            form.save_m2m()
            messages.success(request, "5-Min Fun updated successfully!")
            return redirect('manage_five_min_fun', five_min_fun_id=five_min_fun.id)
    else:
        form = FiveMinFunUpdateForm(instance=five_min_fun, vendor=request.user)
    return render(request, 'events/manage_five_min_fun.html', {
        'five_min_fun': five_min_fun,
        'form': form,
    })

@login_required
def delete_five_min_fun(request, five_min_fun_id):
    if UserProfile.objects.get(user=request.user).role != 'vendor':
        messages.error(request, "Only vendors can delete 5-Min Fun.")
        return redirect('vendor_dashboard')
    five_min_fun = get_object_or_404(FiveMinFun, id=five_min_fun_id, vendor=request.user)
    # Specific approval check for deletion
    if not request.user.vendor_profile.can_create_five_min_fun:
        messages.error(request, "You are not approved to manage 5-Min Fun. Contact superadmin for access.")
        return redirect('vendor_dashboard')
    if request.method == 'POST':
        five_min_fun.is_active = False
        five_min_fun.save()
        messages.success(request, f"{five_min_fun.name} has been deactivated.")
        return redirect('vendor_dashboard')
    return render(request, 'events/delete_five_min_fun.html', {'five_min_fun': five_min_fun})
    # five_min_fun_detail view - UPDATED: Add assigned_routines
@login_required
def five_min_fun_detail(request, slug):
    five_min_fun = get_object_or_404(FiveMinFun, slug=slug, is_active=True)
    user = request.user
    kids = user.kids.all()
    assigned_routines = five_min_fun.routines.all()  # Fetch assigned routines
    selected_ages = ', '.join([ag.name for ag in five_min_fun.age_groups.all()]) if five_min_fun.age_groups.exists() else "None selected"
    selected_powers = ', '.join([sp.name for sp in five_min_fun.super_powers.all()]) if five_min_fun.super_powers.exists() else "None selected"

    # For "Completed" button (for kids)
    can_complete_today = False
    available_kids = []
    if request.user.is_authenticated:
        today = timezone.now().date()
        completed_kid_ids = KidFiveMinFunCompletion.objects.filter(
            five_min_fun=five_min_fun, date_completed=today, kid__caregiver=request.user
        ).values_list('kid__id', flat=True)
        available_kids = kids.exclude(id__in=completed_kid_ids)
        can_complete_today = available_kids.exists()
    return render(request, 'events/five_min_fun_detail.html', {
        'five_min_fun': five_min_fun,
        'assigned_routines': assigned_routines,
        'can_complete_today': can_complete_today,
        'available_kids': available_kids,
        'selected_ages': selected_ages,  
        'selected_powers': selected_powers,  
    })

@require_POST
@login_required
def mark_kid_five_min_fun_completed(request):
    five_min_fun_id = request.POST.get('five_min_fun_id')
    try:
        five_min_fun = get_object_or_404(FiveMinFun, id=five_min_fun_id)
        today = timezone.now().date()
        kid_ids = request.POST.getlist('kid_ids[]')  # FIXED: Use 'kid_ids[]'
        if not kid_ids:
            return JsonResponse({'success': False, 'error': 'No kids selected.'})
        created_count = 0
        already_completed = []
        for kid_id in kid_ids:
            kid = get_object_or_404(KidProfile, id=kid_id, caregiver=request.user)
            try:
                KidFiveMinFunCompletion.objects.create(kid=kid, five_min_fun=five_min_fun, date_completed=today)
                created_count += 1
            except IntegrityError:
                already_completed.append(kid.first_name)
        if created_count > 0:
            message = f"Marked as completed for {created_count} kid(s)!"
            if already_completed:
                message += f" Skipped {', '.join(already_completed)} (already completed)."
            return JsonResponse({'success': True, 'message': message})
        else:
            error_msg = "Already completed today for selected kids."
            if already_completed:
                error_msg += f" ({', '.join(already_completed)})"
            return JsonResponse({'success': False, 'error': error_msg})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Generate RoutineInstances based on frequency (MVP: next 30 days)
def generate_routine_instances(assignment, kid):
    today = date.today()
    end_date = today + timedelta(days=30)  # MVP limit
    # Delete future instances (date >= today) for this SPECIFIC assignment and kid to prevent duplicates, keep past ones
    RoutineInstance.objects.filter(assignment=assignment, kid=kid, date__gte=today).delete()
    if assignment.frequency == 'daily':
        dates = rrule(DAILY, dtstart=today, until=end_date)
    elif assignment.frequency == 'weekly':
        weekday_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
        weekday = weekday_map.get(assignment.day, 0)
        dates = rrule(WEEKLY, dtstart=today, until=end_date, byweekday=weekday)
    elif assignment.frequency == 'monthly':
        day = int(assignment.day) if assignment.day.isdigit() else 1
        dates = rrule(MONTHLY, dtstart=today, until=end_date, bymonthday=day)
    else:
        return
    for dt in dates:
        RoutineInstance.objects.get_or_create(assignment=assignment, kid=kid, date=dt.date())
        
# Vendor Create Routine - Added approval check
@login_required
def create_routine(request):
    if request.user.userprofile.role != 'vendor':
        messages.error(request, "Only vendors can create routines.")
        return redirect('vendor_dashboard')
    if not request.user.vendor_profile.is_approved:
        messages.error(request, "Your vendor account is not approved yet. Please wait for approval before creating routines.")
        return redirect('vendor_dashboard')
    # Specific approval check
    if not request.user.vendor_profile.can_create_routine:
        messages.error(request, "You are not approved to create Routines. Contact superadmin for access.")
        return redirect('vendor_dashboard')
    if request.method == 'POST':
        form = RoutineCreateForm(request.POST, request.FILES)
        if form.is_valid():
            routine = form.save(commit=False)
            routine.vendor = request.user
            routine.save()
            form.save_m2m()  # FIXED: For M2M age/super
            messages.success(request, "Routine created successfully!")
            return redirect('vendor_dashboard')
    else:
        form = RoutineCreateForm()
    return render(request, 'events/create_routine.html', {'form': form})

# Vendor Manage/Edit Routine - UPDATED: Add approval check
@login_required
def manage_routine(request, routine_id):
    if request.user.userprofile.role != 'vendor':
        messages.error(request, "Only vendors can manage routines.")
        return redirect('vendor_dashboard')
    routine = get_object_or_404(Routine, id=routine_id, vendor=request.user)
    # Specific approval check for management
    if not request.user.vendor_profile.can_create_routine:
        messages.error(request, "You are not approved to manage Routines. Contact superadmin for access.")
        return redirect('vendor_dashboard')
    if request.method == 'POST':
        form = RoutineUpdateForm(request.POST, request.FILES, instance=routine)
        if form.is_valid():
            routine = form.save(commit=False)
            routine.vendor = request.user
            routine.save()
            form.save_m2m()  # FIXED: For M2M age/super
            messages.success(request, "Routine updated successfully!")
            return redirect('manage_routine', routine_id=routine.id)
    else:
        form = RoutineUpdateForm(instance=routine)
    return render(request, 'events/manage_routine.html', {'form': form, 'routine': routine})

# Vendor Delete Routine - UPDATED: Add approval check
@login_required
def delete_routine(request, routine_id):
    if request.user.userprofile.role != 'vendor':
        messages.error(request, "Only vendors can delete routines.")
        return redirect('vendor_dashboard')
    routine = get_object_or_404(Routine, id=routine_id, vendor=request.user)
    # Specific approval check for deletion
    if not request.user.vendor_profile.can_create_routine:
        messages.error(request, "You are not approved to manage Routines. Contact superadmin for access.")
        return redirect('vendor_dashboard')
    if request.method == 'POST':
        routine.is_active = False
        routine.save()
        messages.success(request, f"{routine.name} deactivated.")
        return redirect('vendor_dashboard')
    return render(request, 'events/delete_routine.html', {'routine': routine})

# List Routines for Caregivers
def routine_list(request):
    routines = Routine.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'events/routine_list.html', {'routines': routines})

# Routine Detail and Assign for Caregivers
@login_required
def routine_detail(request, slug):
    routine = get_object_or_404(Routine, slug=slug, is_active=True)
    selected_ages = ', '.join([ag.name for ag in routine.age_groups.all()]) if routine.age_groups.exists() else "None selected"
    selected_powers = ', '.join([sp.name for sp in routine.super_powers.all()]) if routine.super_powers.exists() else "None selected"
    kids = request.user.kids.all()
    selected_kid_id = request.GET.get('kid_id') or request.POST.get('kid')
    existing_assignment = None
    initial_data = {}

    if selected_kid_id:
        existing_assignment = KidRoutineAssignment.objects.filter(
            caregiver=request.user,
            routine=routine,
            kid_id=selected_kid_id
        ).first()
        if existing_assignment:
            initial_data = {
                'kid': selected_kid_id,
                'frequency': existing_assignment.frequency,
                'day': existing_assignment.day,
            }

    if request.method == 'POST':
        form = KidRoutineAssignmentForm(request.POST, user=request.user)
        if form.is_valid():
            kid = form.cleaned_data['kid']
            existing_assignment = KidRoutineAssignment.objects.filter(
                caregiver=request.user,
                routine=routine,
                kid=kid
            ).first()
            if existing_assignment:
                existing_assignment.frequency = form.cleaned_data['frequency']
                existing_assignment.day = form.cleaned_data['day']
                existing_assignment.save()
                assignment = existing_assignment
            else:
                assignment = form.save(commit=False)
                assignment.caregiver = request.user
                assignment.routine = routine
                assignment.kid = kid
                assignment.save()
            generate_routine_instances(assignment, kid)
            messages.success(request, "Routine added/updated in calendar!")
            return redirect('my_account')
    else:
        form = KidRoutineAssignmentForm(user=request.user, initial=initial_data)

    return render(request, 'events/routine_detail.html', {
        'routine': routine,
        'form': form,
        'existing_assignment': existing_assignment,
        'selected_kid_id': selected_kid_id,
        'selected_ages': selected_ages,
        'selected_powers': selected_powers,
    })
    
# Assign FiveMinFun to Routine (for caregivers) - Removed has_routine check
@login_required
def assign_five_min_fun_to_routine(request, five_min_fun_id):
    five_min_fun = get_object_or_404(FiveMinFun, id=five_min_fun_id, is_active=True)
    # REMOVED: if not five_min_fun.has_routine: ... (now always allowed)
    kids = request.user.kids.all()
    selected_kid_id = request.GET.get('kid_id') or request.POST.get('kid')
    existing_assignment = None
    initial_data = {}

    if selected_kid_id:
        existing_assignment = KidRoutineAssignment.objects.filter(
            caregiver=request.user,
            five_min_fun=five_min_fun,
            kid_id=selected_kid_id  # CHANGED: Use kid_id
        ).first()
        if existing_assignment:
            initial_data = {
                'kid': selected_kid_id,
                'frequency': existing_assignment.frequency,
                'day': existing_assignment.day,
            }

    if request.method == 'POST':
        form = KidRoutineAssignmentForm(request.POST, user=request.user)
        if form.is_valid():
            kid = form.cleaned_data['kid']
            existing_assignment = KidRoutineAssignment.objects.filter(
                caregiver=request.user,
                five_min_fun=five_min_fun,
                kid=kid
            ).first()
            if existing_assignment:
                existing_assignment.frequency = form.cleaned_data['frequency']
                existing_assignment.day = form.cleaned_data['day']
                existing_assignment.save()
                assignment = existing_assignment
            else:
                assignment = form.save(commit=False)
                assignment.caregiver = request.user
                assignment.five_min_fun = five_min_fun
                assignment.kid = kid  # CHANGED: Set single kid
                assignment.save()
            generate_routine_instances(assignment, kid)
            messages.success(request, "5-Min Fun added/updated in routine and calendar!")
            return redirect('my_account')
    else:
        form = KidRoutineAssignmentForm(user=request.user, initial=initial_data)

    return render(request, 'events/assign_routine.html', {
        'form': form,
        'item': five_min_fun,
        'existing_assignment': existing_assignment,
        'selected_kid_id': selected_kid_id,
    })

# Mark Kid Routine Completed
@login_required
def mark_kid_routine_completed(request):
    if request.method == 'POST':
        routine_instance_id = request.POST.get('routine_instance_id')
        try:
            instance = get_object_or_404(RoutineInstance, id=routine_instance_id, kid__caregiver=request.user)
            if not instance.completed:
                KidRoutineCompletion.objects.create(kid=instance.kid, routine_instance=instance)
                instance.completed = True
                instance.save()
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Already completed.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request.'})

# Popup view for assigning a routine from a Five Min Fun
@login_required
def assign_routine_from_fun(request, fun_id, routine_id):
    fun = get_object_or_404(FiveMinFun, id=fun_id, is_active=True)
    routine = get_object_or_404(Routine, id=routine_id, is_active=True)
    # Optional: Check if routine is assigned to fun
    if routine not in fun.routines.all():
        messages.error(request, "This routine is not assigned to this 5-Min Fun.")
        return redirect('five_min_fun_detail', slug=fun.slug)
    kids = request.user.kids.all()
    selected_kid_id = request.GET.get('kid_id') or request.POST.get('kid')
    existing_assignment = None
    initial_data = {}

    if selected_kid_id:
        existing_assignment = KidRoutineAssignment.objects.filter(
            caregiver=request.user,
            routine=routine,
            kid_id=selected_kid_id
        ).first()
        if existing_assignment:
            initial_data = {
                'kid': selected_kid_id,
                'frequency': existing_assignment.frequency,
                'day': existing_assignment.day,
            }

    if request.method == 'POST':
        form = KidRoutineAssignmentForm(request.POST, user=request.user)
        if form.is_valid():
            kid = form.cleaned_data['kid']
            existing = KidRoutineAssignment.objects.filter(
                caregiver=request.user,
                routine=routine,
                kid=kid
            ).first()
            if existing:
                existing.frequency = form.cleaned_data['frequency']
                existing.day = form.cleaned_data['day']
                existing.save()
                assignment = existing
            else:
                assignment = form.save(commit=False)
                assignment.caregiver = request.user
                assignment.routine = routine  # Set routine (five_min_fun=None)
                assignment.five_min_fun = None
                assignment.kid = kid
                assignment.save()
            generate_routine_instances(assignment, kid)
            # For popup - reload parent and close
            return HttpResponse("""
                <script>
                    alert('Routine added/updated successfully!');
                    if (window.opener) {
                        window.opener.location.reload();
                    }
                    window.close();
                </script>
            """)
    else:
        form = KidRoutineAssignmentForm(user=request.user, initial=initial_data)

    return render(request, 'events/assign_routine_from_fun.html', {
        'routine': routine,
        'fun': fun,
        'form': form,
        'existing_assignment': existing_assignment,
        'selected_kid_id': selected_kid_id,
    })