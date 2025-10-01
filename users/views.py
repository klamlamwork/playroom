
#  users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from .forms import CaregiverSignupForm, KidFormSet, VendorSignupForm, KidProfileForm, CaregiverForm
from .models import KidProfile, FamilyCaregiver
from events.models import Event, EventRegistration, CaregiverEventCompletion, KidEventCompletion, FiveMinFun, KidFiveMinFunCompletion, RoutineInstance, KidRoutineCompletion, Routine, Course, Level, RoadmapPoint
from django.forms import modelformset_factory
from django.contrib import messages
from datetime import date, timedelta
from collections import defaultdict
import calendar as py_calendar
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.contrib.auth import logout
from events.forms import RoutineCreateForm
import json  # Added for JSON serialization
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .utils import get_current_utc  # NEW: Still import if needed elsewhere, but not used in registration views anymore
import pytz

def homepage(request):
    context = {
        'now': timezone.now(),  # <-- ADD THIS: For base.html footer date
    }
    return render(request, 'homepage.html', context)

def signup_step1(request):
    if request.method == 'POST':
        form = CaregiverSignupForm(request.POST)
        if form.is_valid():
            user = form.save()  # Now save handles date_joined internally
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
    account_start = timezone.localtime(user.date_joined).date()

    # FIXED: Explicitly get user's timezone from profile (fallback to 'UTC')
    try:
        tz_str = user.userprofile.timezone_name
    except AttributeError:
        tz_str = 'UTC'
    if not tz_str:
        tz_str = 'UTC'
    try:
        user_tz = pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
        user_tz = pytz.UTC

    # Build kid_events: Add RoutineInstances (EXTENDED: All history + 12 months future)
    kid_events = {}
    for kid in kids:
        events = []
        # All registrations (past/future/history)
        regs = EventRegistration.objects.filter(kids=kid)
        for reg in regs:
            event_obj = reg.event
            if event_obj.format_type != '5-min-play' and event_obj.start_datetime:
                local_start = event_obj.start_datetime.astimezone(user_tz)
                local_end = event_obj.end_datetime.astimezone(user_tz)
                event_date = local_start.date().isoformat()
                start_time = local_start.strftime('%H:%M') if event_obj.start_datetime else 'Anytime'
                end_time = local_end.strftime('%H:%M') if event_obj.end_datetime else 'Anytime'
                events.append({
                    'id': event_obj.id,
                    'date': event_date,
                    'name': event_obj.name,
                    'desc': event_obj.description,
                    'start_time': start_time,
                    'end_time': end_time,
                    'location': event_obj.location,
                    'type': 'event',  #Type for mark done logic
                    'utc_start': event_obj.start_datetime.isoformat() if event_obj.start_datetime else ''  # FIXED: Add UTC start ISO for JS check
                })
        # All 5-min plays from completions (history)
        completions = KidEventCompletion.objects.filter(kid=kid)
        for comp in completions:
            event_obj = comp.event
            if event_obj.format_type != '5-min-play':  # FIXED: Skip non-5-min-play to avoid duplicates with reg entries
                continue
            local_completed = comp.created_at.astimezone(user_tz)
            event_date = local_completed.date().isoformat()
            local_start = event_obj.start_datetime.astimezone(user_tz) if event_obj.start_datetime else None
            local_end = event_obj.end_datetime.astimezone(user_tz) if event_obj.end_datetime else None
            start_time = local_start.strftime('%H:%M') if local_start else 'Anytime'
            end_time = local_end.strftime('%H:%M') if local_end else 'Anytime'
            events.append({
                'id': event_obj.id,
                'date': event_date,
                'name': event_obj.name,
                'desc': event_obj.description,
                'start_time': start_time,
                'end_time': end_time,
                'location': event_obj.location,
                'utc_start': event_obj.start_datetime.isoformat() if event_obj.start_datetime else ''  # FIXED: Add for 5-min-play if has time, else ''
            })

        # All FiveMinFun completions (history)
        five_min_completions = KidFiveMinFunCompletion.objects.filter(kid=kid)
        for comp in five_min_completions:
            five_min_obj = comp.five_min_fun
            # FIXED: Explicit conversion
            local_completed = comp.created_at.astimezone(user_tz)
            event_date = local_completed.date().isoformat()
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
        # FIXED: Explicit now in user_tz
        local_now = timezone.now().astimezone(user_tz)
        future_limit = local_now.date() + timedelta(days=365)  # 12 months ahead
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
            local_start = event_obj.start_datetime.astimezone(user_tz) if event_obj.start_datetime else timezone.now().astimezone(user_tz)
            local_end = event_obj.end_datetime.astimezone(user_tz) if event_obj.end_datetime else local_start
            event_date = local_start.date().isoformat()
            start_time = local_start.strftime('%H:%M') if event_obj.start_datetime else 'Anytime'
            end_time = local_end.strftime('%H:%M') if event_obj.end_datetime else 'Anytime'
            events.append({
                'id': event_obj.id,
                'date': event_date,
                'name': event_obj.name,
                'desc': event_obj.description,
                'start_time': start_time,
                'end_time': end_time,
                'location': event_obj.location,
                'utc_start': event_obj.start_datetime.isoformat() if event_obj.start_datetime else ''  # FIXED: Add for caregiver events too
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
        routine_completions = KidRoutineCompletion.objects.filter(kid=kid).values_list('routine_instance__id', 'routine_instance__date')
        combined_completions = [(event_id, date.isoformat()) for event_id, date in completions]
        combined_completions += [(five_min_id, date.isoformat()) for five_min_id, date in five_min_completions]
        combined_completions += [(instance_id, date.isoformat()) for instance_id, date in routine_completions]
        kid_completed[kid.id] = combined_completions

    # NEW: Fetch course, levels, points, and kid completions for the journey
    course = Course.objects.filter(is_active=True).first()  # Fetch the universal course
    levels = []
    level_points = {}
    kid_completions = defaultdict(set)
    if course:
        levels_qs = course.levels.prefetch_related(
            'points__five_min_fun__super_powers',
            'points__five_min_fun__routines'
        ).all()
        levels = [{'id': l.id, 'number': l.number, 'title': l.title, 'description': l.description} for l in levels_qs]
        level_points = {}
        relevant_fmf_ids = set()
        for level in levels_qs:
            points_list = []
            for p in level.points.all().select_related('five_min_fun'):
                if not p.five_min_fun:
                    continue
                relevant_fmf_ids.add(p.five_min_fun.id)
                point_dict = {
                    'id': p.id,
                    'position': p.position,
                    'five_min_fun': {
                        'id': p.five_min_fun.id,
                        'name': p.five_min_fun.name,
                        'instructions': p.five_min_fun.instructions,
                        'slug': p.five_min_fun.slug,
                        'photo': p.five_min_fun.photo,
                        'audio': p.five_min_fun.audio if p.five_min_fun.audio else None,
                        'place': p.five_min_fun.place,
                        'place_display': p.five_min_fun.get_place_display(),
                        'super_powers': [sp.name for sp in p.five_min_fun.super_powers.all()],
                        'routines': [{'id': r.id, 'name': r.name} for r in p.five_min_fun.routines.all()],
                    },
                }
                points_list.append(point_dict)
            level_points[level.id] = points_list
        # Fetch all completions for user's kids on these FiveMinFun (any date, to check "ever completed")
        completions = KidFiveMinFunCompletion.objects.filter(
            kid__caregiver=user,
            five_min_fun_id__in=relevant_fmf_ids
        ).values_list('kid_id', 'five_min_fun_id').distinct()  # distinct to avoid date duplicates
        for kid_id, fmf_id in completions:
            kid_completions[kid_id].add(fmf_id)

    # Verification prints (add your data here if needed for testing)
    print("Course:", course)
    print("Levels count:", len(levels))
    for level in levels:
        print(f"Level {level['number']}: {level['title']}")
        points = level_points.get(level['id'], [])
        print(f"Points for level {level['id']}:", [p['position'] for p in points])
    print("Kid completions:", kid_completions)

    context = {
        'user': user,
        'kids': kids,
        'caregivers': caregivers,
        'kid_events': kid_events,
        'cg_events': cg_events,
        'completed_events': completed,
        'kid_completed': kid_completed,
        # NEW: Add journey data to context
        'course': course,
        'levels_json': json.dumps(levels),
        'level_points_json': json.dumps(level_points),
        'kid_completions_json': json.dumps({k: list(v) for k, v in kid_completions.items()}),
        # FIXED: Pass user's timezone string to template for JS use
        'user_timezone': tz_str,
    }
    
    return render(request, 'users/my_account.html', context)
def become_vendor(request):
    if request.method == 'POST':
        form = VendorSignupForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()  # Now save handles date_joined and created_at internally
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
    message = "Thank You for Empowering Kids & Caregivers!" if vendor_profile.is_approved else "Pending for Mindset Playroom approval. This may take up to 7 business days."
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

def nominatim_proxy(request):
    query = request.GET.get('q')
    if not query:
        return JsonResponse({'error': 'No query provided'}, status=400)

    url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&addressdetails=1&limit=10&accept-language=en"  # Added &accept-language=en to force English output
    headers = {
        'User-Agent': 'MindsetPlayroomApp/1.0 (contact: klamlamwork@gmail.com)',  # Ensure real email
        'Referer': request.build_absolute_uri('/')
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return JsonResponse(response.json(), safe=False)
    except requests.RequestException as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def set_timezone(request):
    if request.method == 'POST':
        tzname = request.POST.get('timezone')
        if tzname:
            request.session['user_timezone'] = tzname
            return HttpResponse('OK')
    return HttpResponse('Invalid request', status=400)

def get_current_utc_view(request):
    return JsonResponse({'utc_now': get_current_utc().isoformat()})