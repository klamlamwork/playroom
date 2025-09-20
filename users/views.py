
# users/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from .forms import CaregiverSignupForm, KidFormSet, VendorSignupForm, KidProfileForm, CaregiverForm
from .models import KidProfile, FamilyCaregiver
from events.models import Event, EventRegistration, CaregiverEventCompletion, KidEventCompletion, FiveMinFun, KidFiveMinFunCompletion, RoutineInstance, KidRoutineCompletion, Routine  # ADDED Routine
from django.forms import modelformset_factory
from django.contrib import messages
from datetime import date, timedelta  # FIXED: Added timedelta
from collections import defaultdict
import calendar as py_calendar
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.contrib.auth import logout
from events.forms import RoutineCreateForm

def homepage(request):
    context = {
        'now': timezone.now(),  # <-- ADD THIS: For base.html footer date
    }
    return render(request, 'homepage.html', context)

def signup_step1(request):
    if request.method == 'POST':
        form = CaregiverSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('signup_step2')
    else:
        form = CaregiverSignupForm()
    return render(request, 'users/signup_step1.html', {'form': form})

def signup_step2(request):
    if not request.user.is_authenticated or request.user.userprofile.role != 'caregiver':
        return redirect('signup_step1')
    KidFormSet = forms.modelformset_factory(KidProfile, form=KidProfileForm, extra=1, max_num=5)
    if request.method == 'POST':
        formset = KidFormSet(request.POST, queryset=request.user.kids.all())
        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                instance.caregiver = request.user
                instance.save()
            return redirect('dashboard')
    else:
        formset = KidFormSet(queryset=request.user.kids.all())
    return render(request, 'users/signup_step2.html', {'formset': formset})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Redirect by role:
            role = user.userprofile.role
            if role == 'vendor':
                return redirect('vendor_dashboard')
            else:
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})

@login_required
def dashboard(request):
    if request.user.userprofile.role != 'caregiver':
        return redirect('login')
    return render(request, 'users/dashboard.html', {'user': request.user})

@login_required
@never_cache  # Prevent caching to ensure fresh data on reload
def my_account(request):
    user = request.user
    caregivers = FamilyCaregiver.objects.filter(user=user)
    kids = user.kids.all()

    # Print loaded kids for debug (shows what template sees on GET)
    print("Loaded kids on GET:")
    for kid in kids:
        print(f"Kid {kid.id}: {kid.first_name} birthday {kid.birthday}")

    # Existing add/edit code for kids/caregivers here...
    if request.method == "POST" and "first_name" in request.POST and "birthday" in request.POST and not request.POST.get("kid_id"):
        print("Add kid POST data:", request.POST)  # Debug: Print POST for add
        form = KidProfileForm(request.POST)
        if form.is_valid():
            kid = form.save(commit=False)
            kid.caregiver = user
            kid.save()
            kid.refresh_from_db()  # Refresh to confirm DB commit
            print("Added kid birthday (after refresh):", kid.birthday)  # Debug: Confirm saved birthday
            messages.success(request, "Kid added successfully!")
            return redirect('my_account')
        else:
            print("Add kid form errors:", form.errors)  # Debug: Print errors
            messages.error(request, f"Error adding kid: {form.errors.as_text()}")

    if request.method == "POST" and "kid_id" in request.POST:
        print("Edit kid POST data:", request.POST)  # Debug: Print POST for edit
        kid = get_object_or_404(KidProfile, id=request.POST['kid_id'], caregiver=user)
        kid_form = KidProfileForm(request.POST, instance=kid)
        if kid_form.is_valid():
            kid_form.save()
            kid.refresh_from_db()  # Refresh to confirm DB commit
            print("Updated kid birthday (after refresh):", kid.birthday)  # Debug: Confirm saved birthday after edit
            messages.success(request, "Kid updated successfully!")
            return redirect('my_account')
        else:
            print("Edit kid form errors:", kid_form.errors)  # Debug: Print errors
            messages.error(request, f"Error updating kid: {kid_form.errors.as_text()}")

    if request.method == "POST" and ("first_name" in request.POST) and ("caregiver_id" in request.POST or "add_caregiver" in request.POST):
        if request.POST.get("caregiver_id"):
            caregiver = get_object_or_404(FamilyCaregiver, id=request.POST["caregiver_id"], user=user)
            form = CaregiverForm(request.POST, request.FILES, instance=caregiver)
        else:
            form = CaregiverForm(request.POST, request.FILES)
        if form.is_valid():
            cg = form.save(commit=False)
            cg.user = user
            cg.save()
            if form.cleaned_data.get('avatar'):
                cg.avatar = form.cleaned_data.get('avatar')
                cg.save()
            return redirect('my_account')

    # Account creation date for history reference (optional, for past filter if needed)
    account_start = user.date_joined.date()

    # Build kid_events: Add RoutineInstances (EXTENDED: All history + 12 months future)
    kid_events = {}
    for kid in kids:
        events = []
        # All registrations (past/future/history)
        regs = EventRegistration.objects.filter(kids=kid)
        for reg in regs:
            event_obj = reg.event
            if event_obj.format_type != '5-min-play' and event_obj.start_datetime:
                event_date = event_obj.start_datetime.date().isoformat()
                start_time = event_obj.start_datetime.strftime('%H:%M') if event_obj.start_datetime else 'Anytime'
                end_time = event_obj.end_datetime.strftime('%H:%M') if event_obj.end_datetime else 'Anytime'
                events.append({
                    'id': event_obj.id,
                    'date': event_date,
                    'name': event_obj.name,
                    'desc': event_obj.description,
                    'start_time': start_time,
                    'end_time': end_time,
                    'location': event_obj.location,
                    'type': 'event'  #Type for mark done logic
                })
        # All 5-min plays from completions (history)
        completions = KidEventCompletion.objects.filter(kid=kid)
        for comp in completions:
            event_obj = comp.event
            event_date = comp.date_completed.isoformat()
            start_time = event_obj.start_datetime.strftime('%H:%M') if event_obj.start_datetime else 'Anytime'
            end_time = event_obj.end_datetime.strftime('%H:%M') if event_obj.end_datetime else 'Anytime'
            events.append({
                'id': event_obj.id,
                'date': event_date,
                'name': event_obj.name,
                'desc': event_obj.description,
                'start_time': start_time,
                'end_time': end_time,
                'location': event_obj.location,
            })

        # All FiveMinFun completions (history)
        five_min_completions = KidFiveMinFunCompletion.objects.filter(kid=kid)
        for comp in five_min_completions:
            five_min_obj = comp.five_min_fun
            event_date = comp.date_completed.isoformat()
            events.append({
                'id': five_min_obj.id,
                'date': event_date,
                'name': five_min_obj.name,
                'desc': five_min_obj.instructions,
                'start_time': 'Anytime',
                'end_time': 'Anytime',
                'location': 'N/A',  # No location for FiveMinFun
                'type': 'five_min_fun'  # Type for mark done
            })
        kid_events[kid.id] = events

        # All RoutineInstances (history since creation + up to 12 months future)
        future_limit = timezone.now().date() + timedelta(days=365)  # 12 months ahead
        routine_instances = RoutineInstance.objects.filter(
            kid=kid,
            date__lte=future_limit  # No lower bound: includes all history
        ).order_by('date')
        print(f"For kid {kid.id}: {routine_instances.count()} routine instances (up to +12 months)")
        for instance in routine_instances:
            if instance.assignment.routine:
                item_name = instance.assignment.routine.name
                item_desc = instance.assignment.routine.instructions
            else:
                item_name = instance.assignment.five_min_fun.name
                item_desc = instance.assignment.five_min_fun.instructions
            events.append({
                'id': instance.id,
                'date': instance.date.isoformat(),
                'name': item_name,
                'desc': item_desc,
                'start_time': 'Anytime',
                'end_time': 'Anytime',
                'location': 'N/A',
                'type': 'routine'  # Type to identify for mark done
            })
        kid_events[kid.id] = events

    # Build cg_events (all history/future, unchanged but confirmed)
    cg_events = {}
    for cg in caregivers:
        regs = EventRegistration.objects.filter(caregivers=cg)
        events = []
        for reg in regs:
            event_obj = reg.event
            event_date = event_obj.start_datetime.date().isoformat() if event_obj.start_datetime else timezone.now().date().isoformat()
            start_time = event_obj.start_datetime.strftime('%H:%M') if event_obj.start_datetime else 'Anytime'
            end_time = event_obj.end_datetime.strftime('%H:%M') if event_obj.end_datetime else 'Anytime'
            events.append({
                'id': event_obj.id,
                'date': event_date,
                'name': event_obj.name,
                'desc': event_obj.description,
                'start_time': start_time,
                'end_time': end_time,
                'location': event_obj.location,
            })
        cg_events[cg.id] = events

    # Pull all completed caregiver events for ticks (history)
    completed = {}
    for cg in caregivers:
        completions = CaregiverEventCompletion.objects.filter(
            caregiver=cg
        ).values_list('event_id', 'date_completed')
        completed[cg.id] = [(event_id, date.isoformat()) for event_id, date in completions]
    
    # All completed kid events, FiveMinFun, and Routines for ticks (history)
    kid_completed = {}
    for kid in kids:
        completions = KidEventCompletion.objects.filter(kid=kid).values_list('event_id', 'date_completed')
        five_min_completions = KidFiveMinFunCompletion.objects.filter(kid=kid).values_list('five_min_fun_id', 'date_completed')
        routine_completions = KidRoutineCompletion.objects.filter(kid=kid).values_list('routine_instance_id', 'date_completed')
        combined_completions = [(event_id, date.isoformat()) for event_id, date in completions]
        combined_completions += [(five_min_id, date.isoformat()) for five_min_id, date in five_min_completions]
        combined_completions += [(instance_id, date.isoformat()) for instance_id, date in routine_completions]
        kid_completed[kid.id] = combined_completions

    context = {
        'user': user,
        'kids': kids,
        'caregivers': caregivers,
        'kid_events': kid_events,
        'cg_events': cg_events,
        'completed_events': completed,
        'kid_completed': kid_completed,
    }

    return render(request, 'users/my_account.html', context)

def become_vendor(request):
    if request.method == 'POST':
        form = VendorSignupForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('vendor_dashboard')
    else:
        form = VendorSignupForm()
    return render(request, 'users/become_vendor.html', {'form': form})

@login_required
def vendor_dashboard(request):
    try:
        if request.user.userprofile.role != 'vendor':
            return redirect('login')
    except:
        messages.error(request, "Profile not found.")
        return redirect('login')

    vendor_profile = request.user.vendor_profile
    events = Event.objects.filter(vendor=request.user, is_active=True).order_by('-created_at')
    message = "Welcome to your Vendor Dashboard!" if vendor_profile.is_approved else "Pending for Mindset Playroom approval. This may take up to 7 business days."
    five_min_funs = FiveMinFun.objects.filter(vendor=request.user, is_active=True).order_by('-created_at')
    routines = Routine.objects.filter(vendor=request.user, is_active=True).order_by('-created_at')  # Fetch routines
 
    return render(request, 'users/vendor_dashboard.html', {
        'message': message,
        'vendor': vendor_profile,
        'events': events,
        'five_min_funs': five_min_funs,  
        'routines': routines,  
    })

@login_required
def manage_kids(request):
    if request.user.userprofile.role != 'caregiver':
        return redirect('dashboard')
    KidFormSet = modelformset_factory(KidProfile, form=KidProfileForm, extra=1, max_num=5, can_delete=True)
    queryset = KidProfile.objects.filter(caregiver=request.user)
    if request.method == "POST":
        formset = KidFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                instance.caregiver = request.user
                instance.save()
            for obj in formset.deleted_objects:
                obj.delete()
            return redirect('my_account')
    else:
        formset = KidFormSet(queryset=queryset)
    return render(request, 'users/manage_kids.html', {
        'formset': formset,
        'max_kids': 5
    })

def user_logout(request):
    logout(request)
    return redirect('login')