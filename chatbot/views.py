
#chatbot/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse, HttpResponse
from users.models import FamilyCaregiver, KidProfile, UserProfile
from events.models import FiveMinFun, KidFiveMinFunCompletion, Routine, RoadmapPoint, Level, Course, Event, RoutineInstance, KidRoutineCompletion, EventRegistration
from django.utils import timezone
from datetime import datetime
from collections import Counter
from django.db.models import Count, Q
import json
import pytz
import html  # Added for escaping
import requests  # Add this import for weather API calls

@login_required
def chat_view(request):
    try:
        profile = request.user.userprofile
        if profile.role != 'caregiver':
            return redirect('dashboard') if not request.headers.get('x-requested-with') == 'XMLHttpRequest' else JsonResponse({'error': 'Not authorized'}, status=403)
    except ObjectDoesNotExist:
        return redirect('login') if not request.headers.get('x-requested-with') == 'XMLHttpRequest' else JsonResponse({'error': 'Profile missing'}, status=400)

    # Get user's timezone and compute local today
    tz_str = profile.timezone_name if hasattr(profile, 'timezone_name') else 'UTC'
    if not tz_str:
        tz_str = 'UTC'
    try:
        user_tz = pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
        user_tz = pytz.UTC
    local_now = timezone.now().astimezone(user_tz)
    today_local = local_now.date()

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    # Initialize session if new chat or reset requested
    if 'chat_step' not in request.session or request.GET.get('reset'):
        request.session['chat_step'] = 'q1'
        request.session['selected_persons'] = []
        request.session['foundation_completed'] = False
        request.session['asked_where_to_start'] = False
        request.session['a2.5_substep'] = None
        request.session['prefer_format'] = None
        request.session['time_start'] = None
        request.session['time_end'] = None
        request.session['place'] = None
        request.session['unfinished_points'] = []
        request.session['current_suggest_index'] = 0

    step = request.session['chat_step']

    if request.method == 'POST':
        data = json.loads(request.body) if is_ajax else request.POST
        if step == 'q1':
            selected_caregivers = data.get('caregivers', [])
            selected_kids = data.get('kids', [])
            selected = []
            for cg_id in selected_caregivers:
                try:
                    cg = FamilyCaregiver.objects.get(id=int(cg_id), user=request.user)
                    selected.append({'type': 'caregiver', 'id': cg.id, 'name': cg.first_name})
                except (ValueError, FamilyCaregiver.DoesNotExist):
                    pass
            for kid_id in selected_kids:
                try:
                    kid = KidProfile.objects.get(id=int(kid_id), caregiver=request.user)
                    selected.append({'type': 'kid', 'id': kid.id, 'name': kid.first_name})
                except (ValueError, KidProfile.DoesNotExist):
                    pass
            if not selected:
                message = 'Please select at least one person.'
                return JsonResponse({'message': message, 'options': [], 'step': 'q1'}) if is_ajax else render(request, 'chatbot/chat.html', {'message': message, 'step': 'q1'})
            request.session['selected_persons'] = selected
            request.session['chat_step'] = 'q2_caregiver' if all(p['type'] == 'caregiver' for p in selected) else 'q2_kid'
            step = request.session['chat_step']

        elif step.startswith('q2'):
            choice = data.get('choice')
            if choice == 'where_to_start':
                request.session['asked_where_to_start'] = True
                request.session['chat_step'] = 'a2.1'
            elif choice == 'continue_journey':
                request.session['chat_step'] = 'a2.2'
            elif choice == 'set_routines':
                request.session['chat_step'] = 'a2.3'
            elif choice == 'see_routines':
                request.session['chat_step'] = 'a2.4'
            elif choice == 'plan_activities':
                request.session['a2.5_substep'] = 'prefer'
                request.session['chat_step'] = 'a2.5'
            elif choice == 'back':
                request.session['chat_step'] = 'q1'
            step = request.session['chat_step']

        elif step == 'a2.1':
            choice = data.get('choice')
            if choice == 'back':
                request.session['chat_step'] = 'q2_kid' if any(p['type'] == 'kid' for p in request.session['selected_persons']) else 'q2_caregiver'
            step = request.session['chat_step']

        elif step == 'a2.2':
            choice = data.get('choice')
            if choice == 'no_another':
                request.session['current_suggest_index'] += 1
            elif choice == 'back':
                request.session['chat_step'] = 'q2_kid' if any(p['type'] == 'kid' for p in request.session['selected_persons']) else 'q2_caregiver'
            step = request.session['chat_step']

        elif step == 'a2.3':
            choice = data.get('choice')
            if choice == 'back':
                request.session['chat_step'] = 'q2_kid' if any(p['type'] == 'kid' for p in request.session['selected_persons']) else 'q2_caregiver'
            step = request.session['chat_step']

        elif step == 'a2.4':
            choice = data.get('choice')
            if choice == 'back':
                request.session['chat_step'] = 'q2_kid' if any(p['type'] == 'kid' for p in request.session['selected_persons']) else 'q2_caregiver'
            step = request.session['chat_step']

        elif step == 'a2.5':
            substep = request.session['a2.5_substep']
            if substep == 'prefer':
                choice = data.get('choice')
                if choice in ['casual', 'formal']:
                    request.session['prefer_format'] = choice
                    request.session['a2.5_substep'] = 'time'
            elif substep == 'time':
                choice = data.get('choice')
                if choice == 'no':
                    request.session['time_start'] = None
                    request.session['time_end'] = None
                    request.session['a2.5_substep'] = 'place'
                elif choice == 'yes':
                    request.session['a2.5_substep'] = 'time_input'
            elif substep == 'time_input':
                start_time = data.get('start_time')
                end_time = data.get('end_time')
                choice = data.get('choice')
                if choice == 'back':
                    request.session['a2.5_substep'] = 'time'
                elif start_time and end_time:
                    request.session['time_start'] = start_time
                    request.session['time_end'] = end_time
                    request.session['a2.5_substep'] = 'place'

            elif substep == 'place':
                choice = data.get('choice')
                if choice == 'no':
                    request.session['place'] = None
                    request.session['a2.5_substep'] = 'results'
                elif choice == 'yes':
                    request.session['a2.5_substep'] = 'place_choice'
            elif substep == 'place_choice':
                choice = data.get('choice')
                if choice in ['indoor', 'outdoor']:
                    request.session['place'] = choice
                    request.session['a2.5_substep'] = 'results'

            if data.get('choice') == 'back':
                if substep == 'prefer':
                    request.session['chat_step'] = 'q2_kid' if any(p['type'] == 'kid' for p in request.session['selected_persons']) else 'q2_caregiver'
                    request.session['a2.5_substep'] = None
                else:
                    # Back to previous substep
                    if substep == 'time':
                        request.session['a2.5_substep'] = 'prefer'
                    elif substep == 'time_input':
                        request.session['a2.5_substep'] = 'time'
                    elif substep == 'place':
                        request.session['a2.5_substep'] = 'time'
                    elif substep == 'place_choice':
                        request.session['a2.5_substep'] = 'place'
                    elif substep == 'results':
                        request.session['a2.5_substep'] = 'place'
            
                    elif substep == 'results':
                        # Matching logic (screening and ranking, not point-based)
                        events = Event.objects.filter(is_active=True)
                        # Filter by format
                        prefer_format = request.session.get('prefer_format')
                        if prefer_format == 'casual':
                            events = events.filter(format_type='hangout')
                        elif prefer_format == 'formal':
                            events = events.filter(format_type__in=['workshop', 'course', 'project'])
                        # Time (with timezone conversion)
                        time_start = request.session.get('time_start')
                        time_end = request.session.get('time_end')
                        if time_start and time_end:
                            # Append seconds for parsing
                            start_str = time_start + ':00'
                            end_str = time_end + ':00'
                            # Parse to naive datetime (local time)
                            start_dt = datetime.fromisoformat(start_str)
                            end_dt = datetime.fromisoformat(end_str)
                            # Localize to user's timezone and convert to UTC
                            start_local = user_tz.localize(start_dt)
                            start_utc = start_local.astimezone(pytz.UTC)
                            end_local = user_tz.localize(end_dt)
                            end_utc = end_local.astimezone(pytz.UTC)
                            events = events.filter(start_datetime__gte=start_utc, end_datetime__lte=end_utc)
                        # Place (with improved weather check)
                        place = request.session.get('place')
                        if place:
                            events = events.filter(place=place)
                        # City for outdoor + weather check (using lat/lon)
                        if place == 'outdoor':
                            lat = profile.latitude
                            lon = profile.longitude
                            if lat is not None and lon is not None:
                                api_key = 'your_openweather_api_key_here'  # Replace with your actual key from openweathermap.org
                                is_future = start_utc > timezone.now() if time_start else False
                                if is_future:
                                    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}"
                                else:
                                    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
                                try:
                                    import requests  # Ensure imported at top if not
                                    resp = requests.get(url).json()
                                    if resp.get('cod') != 200 and resp.get('cod') != '200':
                                        raise ValueError("API error")
                                    if 'list' in resp:  # Forecast
                                        # Find closest to start_utc (or now if no time)
                                        target_ts = int(start_utc.timestamp()) if time_start else int(timezone.now().timestamp())
                                        closest = min(resp['list'], key=lambda x: abs(x['dt'] - target_ts))
                                        weather_main = closest['weather'][0]['main']
                                    else:  # Current
                                        weather_main = resp['weather'][0]['main']
                                    if weather_main in ['Rain', 'Snow', 'Thunderstorm']:
                                        message += '<br>Note: Bad weather today—suggesting indoor activities instead.'
                                        events = events.filter(place='indoor')
                                except Exception as e:
                                    print(f"Weather API error: {e}")  # Log for debug; skip suggestion on failure
                                    pass
                        # Age for kids
                        kid_groups = set()
                        if selected_kids:
                            for p in selected_kids:
                                kid = KidProfile.objects.get(id=p['id'])
                                age = (timezone.now().date() - kid.birthday).days // 365
                                if age <= 3:
                                    kid_groups.add('0-3')  # Adjust to match your AgeGroup.name in DB
                                elif age <= 10:
                                    kid_groups.add('3-10')
                                else:
                                    kid_groups.add('11+')
                            if kid_groups:
                                events = events.filter(age_groups__name__in=kid_groups).distinct()
                        # Pattern from past registrations (ranking)
                        past_regs = EventRegistration.objects.filter(kids__id__in=[p['id'] for p in selected_kids])
                        formats = [r.event.format_type for r in past_regs]
                        common_format = Counter(formats).most_common(1)[0][0] if formats else None
                        if common_format:
                            events = sorted(events, key=lambda e: 0 if e.format_type == common_format else 1)
                        # Message
                        if events:
                            message = 'Recommended activities:<br>' + '<br>'.join([
                                #f'{e.name} - {e.description} '
                                f'<button onclick="window.location.href=\'/events/{e.slug if e.slug else e.id}\'">{e.name}</button>'
                                for e in events
                            ])

                        else:
                            message = 'No matching activities found.'
                        options = [{'value': 'back', 'label': 'Back'}]

            step = request.session['chat_step']

    # Prepare response based on step
    message = ''
    options = []
    caregivers = []
    kids = []
    input_type = None

    selected_persons = request.session['selected_persons']
    selected_kids = [p for p in selected_persons if p['type'] == 'kid']

    if step == 'q1':
        message = 'Who do you want to ask about today?'
        caregivers = [{'id': cg.id, 'name': cg.first_name} for cg in FamilyCaregiver.objects.filter(user=request.user)]
        kids = [{'id': kid.id, 'name': kid.first_name} for kid in request.user.kids.all()]

    elif step.startswith('q2'):
        persons = ', '.join(p['name'] for p in selected_persons) or 'you'
        message = f'What do {persons} want to do today?'
        if not request.session['asked_where_to_start']:
            options.append({'value': 'where_to_start', 'label': 'Where to start?'})
        course = Course.objects.filter(is_active=True).first()
        unfinished = False
        if course and selected_kids:
            levels = course.levels.all()
            for person in selected_kids:
                kid = KidProfile.objects.get(id=person['id'])
                all_fmf_ids = []
                unfinished_points = []
                for level in levels:
                    points = level.points.order_by('position')
                    for p in points:
                        if p.five_min_fun:
                            all_fmf_ids.append(p.five_min_fun.id)
                            unfinished_points.append(p)
                completed = KidFiveMinFunCompletion.objects.filter(kid=kid, five_min_fun_id__in=all_fmf_ids).values_list('five_min_fun_id', flat=True).distinct()
                unfinished_ids = set(all_fmf_ids) - set(completed)
                if unfinished_ids:
                    unfinished = True
                    unfinished_points = [p for p in unfinished_points if p.five_min_fun.id in unfinished_ids]
                    unfinished_points.sort(key=lambda p: (p.level.number, p.position))
                    request.session['unfinished_points'] = [p.id for p in unfinished_points]
                    break
        if unfinished:
            options.append({'value': 'continue_journey', 'label': 'Continuing Foundation Journey'})
        options += [
            {'value': 'set_routines', 'label': 'Set Routines'},
            {'value': 'see_routines', 'label': 'See Routines Today'},
            {'value': 'plan_activities', 'label': 'Plan activities'},
            {'value': 'back', 'label': 'Back'}
        ]

    elif step == 'a2.1':
        course = Course.objects.filter(is_active=True).first()
        if course:
            first_level = course.levels.order_by('number').first()
            if first_level:
                first_point = first_level.points.order_by('position').first()
                if first_point and first_point.five_min_fun:
                    fmf = first_point.five_min_fun
                    message = f'Start with the Foundation Journey. Instructions: {course.description or "Explore the basics to build a strong mindset foundation."} First 5-Min Fun: {fmf.name}. Link: /events/five-min-fun/{fmf.slug or fmf.id}'
                else:
                    message = 'No first activity found in the journey.'
            else:
                message = 'No levels found in the journey.'
        else:
            message = 'No foundation journey course found.'
        options = [{'value': 'back', 'label': 'Got it'}]

    elif step == 'a2.2':
        unfinished_point_ids = request.session.get('unfinished_points', [])
        index = request.session.get('current_suggest_index', 0)
        if index >= len(unfinished_point_ids):
            message = 'No more unfinished activities in the journey!'
            options = [{'value': 'back', 'label': 'Back'}]
        else:
            point = RoadmapPoint.objects.get(id=unfinished_point_ids[index])
            fmf = point.five_min_fun
            message = f'Here is the next 5-Min Fun: {fmf.name}.<br>Instructions: {fmf.instructions}<br><button onclick="window.location.href=\'/events/five-min-fun/{fmf.slug or fmf.id}\'">Go Have Fun</button>'
            options = [{'value': 'no_another', 'label': 'No, I want another one'}, {'value': 'back', 'label': 'Back'}]

    elif step == 'a2.3':
        if not selected_kids:
            message = 'No kids selected to suggest routines.'
            options = [{'value': 'back', 'label': 'Back'}]
        else:
            kid_ids = [p['id'] for p in selected_kids]
            completed_fmf = KidFiveMinFunCompletion.objects.filter(kid_id__in=kid_ids).select_related('five_min_fun')
            completed_fmf_ids = [c.five_min_fun.id for c in completed_fmf]
            # Query Routines related to these FiveMinFun
            suggested_routines = Routine.objects.filter(assigned_five_min_funs__id__in=completed_fmf_ids, is_active=True).distinct()
            # Exclude already assigned
            assigned_routine_ids = RoutineInstance.objects.filter(kid_id__in=kid_ids, assignment__routine__isnull=False).values_list('assignment__routine_id', flat=True).distinct()
            suggested_routines = suggested_routines.exclude(id__in=assigned_routine_ids)
            # Priority: Order by number of related completed 5-min fun (descending)
            suggested_routines = suggested_routines.annotate(
                completed_count=Count('assigned_five_min_funs', filter=Q(assigned_five_min_funs__id__in=completed_fmf_ids))
            ).order_by('-completed_count')[:6]  # Top 6
            if suggested_routines:
                message = 'Suggested routines based on completed 5-Min Fun (prioritized by relevance):<br>' + '<br>'.join([f'<button onclick="window.open(\'/events/routine/{r.slug}/\', \'routine_popup\', \'width=600,height=700,scrollbars=yes,resizable=yes\')">{r.name}</button>' for r in suggested_routines]) + '<br><button onclick="window.open(\'/events/routine/list/\', \'routine_popup\', \'width=600,height=700,scrollbars=yes,resizable=yes\')">No I want other ones</button>'
                options = [{'value': 'back', 'label': 'Back'}]
            else:
                message = 'No new routines to suggest based on completed activities.'
                options = [{'value': 'back', 'label': 'Back'}]

    elif step == 'a2.4':
        if not selected_kids:
            message = 'No kids selected to show routines.'
        else:
            message = 'Routines set but not done today:<br><br>'
            has_unfinished = False
            for person in selected_kids:
                kid_id = person['id']
                kid_name = person['name']
                instances = RoutineInstance.objects.filter(kid_id=kid_id, date=today_local, completed=False)
                completed_ids = KidRoutineCompletion.objects.filter(routine_instance__kid_id=kid_id, routine_instance__date=today_local).values_list('routine_instance_id', flat=True)
                unfinished = instances.exclude(id__in=completed_ids)
                if unfinished:
                    has_unfinished = True
                    unfinished_html = []
                    for i in unfinished:
                        name = html.escape(i.assignment.routine.name if i.assignment.routine else i.assignment.five_min_fun.name)
                        unfinished_html.append(
                            f'<button onclick="window.location.href=\'/account/?open_modal=true&routine_instance_id={i.id}&date={today_local.isoformat()}&kid_id={kid_id}\'">{name}</button>'
                        )
                    kid_message = f"{kid_name}:<br>" + '<br>'.join(unfinished_html)
                    message += kid_message + '<br><br>'
                else:
                    message += f"{kid_name}: All done for today.<br><br>"
            if not has_unfinished:
                message = 'No unfinished routines for today.'
        options = [{'value': 'back', 'label': 'Back'}]

    elif step == 'a2.5':
        substep = request.session.get('a2.5_substep', 'prefer')
        if substep == 'prefer':
            message = 'Do you prefer: 1. casual activities (Hangouts) or 2. more formal (Workshops, Courses, Projects)?'
            options = [{'value': 'casual', 'label': 'Casual activities (Hangouts)'}, {'value': 'formal', 'label': 'More formal (Workshops, Courses, Projects)'}, {'value': 'back', 'label': 'Back'}]
        elif substep == 'time':
            message = 'Do you have a time preference?'
            options = [{'value': 'yes', 'label': 'Yes'}, {'value': 'no', 'label': 'No'}, {'value': 'back', 'label': 'Back'}]
        elif substep == 'time_input':
            message = 'Select start and end date/time'
            input_type = 'datetime'
            options = [{'value': 'back', 'label': 'Back'}]
        elif substep == 'place':
            message = 'Do you have place preference?'
            options = [{'value': 'yes', 'label': 'Yes'}, {'value': 'no', 'label': 'No'}, {'value': 'back', 'label': 'Back'}]
        elif substep == 'place_choice':
            message = 'Indoor or Outdoor?'
            options = [{'value': 'indoor', 'label': 'Indoor'}, {'value': 'outdoor', 'label': 'Outdoor'}, {'value': 'back', 'label': 'Back'}]
        elif substep == 'results':
            # Matching logic (screening and ranking, not point-based)
            events = Event.objects.filter(is_active=True)
            # Filter by format
            prefer_format = request.session.get('prefer_format')
            if prefer_format == 'casual':
                events = events.filter(format_type='hangout')
            elif prefer_format == 'formal':
                events = events.filter(format_type__in=['workshop', 'course', 'project'])
            # Time (with timezone conversion)
            time_start = request.session.get('time_start')
            time_end = request.session.get('time_end')
            if time_start and time_end:
                # Append seconds for parsing
                start_str = time_start + ':00'
                end_str = time_end + ':00'
                # Parse to naive datetime (local time)
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)
                # Localize to user's timezone and convert to UTC
                start_local = user_tz.localize(start_dt)
                start_utc = start_local.astimezone(pytz.UTC)
                end_local = user_tz.localize(end_dt)
                end_utc = end_local.astimezone(pytz.UTC)
                events = events.filter(start_datetime__gte=start_utc, end_datetime__lte=end_utc)
            # Place (with improved weather check)
            place = request.session.get('place')
            if place:
                events = events.filter(place=place)
            # City for outdoor + weather check (using lat/lon)
            if place == 'outdoor':
                lat = profile.latitude
                lon = profile.longitude
                if lat is not None and lon is not None:
                    api_key = 'your_openweather_api_key_here'  # Replace with your actual key from openweathermap.org
                    is_future = start_utc > timezone.now() if time_start else False
                    if is_future:
                        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}"
                    else:
                        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
                    try:
                        import requests  # Ensure imported at top if not
                        resp = requests.get(url).json()
                        if resp.get('cod') != 200 and resp.get('cod') != '200':
                            raise ValueError("API error")
                        if 'list' in resp:  # Forecast
                            # Find closest to start_utc (or now if no time)
                            target_ts = int(start_utc.timestamp()) if time_start else int(timezone.now().timestamp())
                            closest = min(resp['list'], key=lambda x: abs(x['dt'] - target_ts))
                            weather_main = closest['weather'][0]['main']
                        else:  # Current
                            weather_main = resp['weather'][0]['main']
                        if weather_main in ['Rain', 'Snow', 'Thunderstorm']:
                            message += '<br>Note: Bad weather today—suggesting indoor activities instead.'
                            events = events.filter(place='indoor')
                    except Exception as e:
                        print(f"Weather API error: {e}")  # Log for debug; skip suggestion on failure
                        pass
            # Age for kids
            kid_groups = set()
            if selected_kids:
                for p in selected_kids:
                    kid = KidProfile.objects.get(id=p['id'])
                    age = (timezone.now().date() - kid.birthday).days // 365
                    if age <= 3:
                        kid_groups.add('0-3')  # Adjust to match your AgeGroup.name in DB
                    elif age <= 10:
                        kid_groups.add('3-10')
                    else:
                        kid_groups.add('11+')
                if kid_groups:
                    events = events.filter(age_groups__name__in=kid_groups).distinct()
            # Pattern from past registrations (ranking)
            past_regs = EventRegistration.objects.filter(kids__id__in=[p['id'] for p in selected_kids])
            formats = [r.event.format_type for r in past_regs]
            common_format = Counter(formats).most_common(1)[0][0] if formats else None
            if common_format:
                events = sorted(events, key=lambda e: 0 if e.format_type == common_format else 1)
            # Message
            if events:
                message = 'Recommended activities:<br>' + '<br>'.join([
                    #f'{e.name} - {e.description} '
                    f'<button onclick="window.location.href=\'/events/{e.slug if e.slug else e.id}\'">{e.name}</button>'
                    for e in events
                ])

            else:
                message = 'No matching activities found.'
            options = [{'value': 'back', 'label': 'Back'}]

    if is_ajax:
        resp = {'message': message, 'options': options, 'step': step, 'caregivers': caregivers, 'kids': kids}
        if input_type:
            resp['input_type'] = input_type
        return JsonResponse(resp)
    else:
        context = {'message': message, 'options': [(opt['value'], opt['label']) for opt in options], 'step': step, 'caregivers': FamilyCaregiver.objects.filter(user=request.user), 'kids': request.user.kids.all()}
        return render(request, 'chatbot/chat.html', context)