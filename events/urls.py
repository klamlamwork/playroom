
#events/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Specific paths first (non-dynamic)
    path('list/', views.event_list, name='event_list'),
    path('create/', views.create_event, name='create_event'),
    path('mark_caregiver_event_completed/', views.mark_caregiver_event_completed, name='mark_caregiver_event_completed'),
    path('mark_kid_event_completed/', views.mark_kid_event_completed, name='mark_kid_event_completed'),
    path('mark_kid_routine_completed/', views.mark_kid_routine_completed, name='mark_kid_routine_completed'),  # NEW: Added missing path
    path('<int:event_id>/manage/', views.manage_event, name='manage_event'),
    path('<int:event_id>/delete/', views.delete_event, name='delete_event'),
    path('five-min-fun/create/', views.create_five_min_fun, name='create_five_min_fun'),
    path('five-min-fun/<int:five_min_fun_id>/manage/', views.manage_five_min_fun, name='manage_five_min_fun'),
    path('five-min-fun/<int:five_min_fun_id>/delete/', views.delete_five_min_fun, name='delete_five_min_fun'),
    path('five-min-fun/<int:five_min_fun_id>/assign/', views.assign_five_min_fun_to_routine, name='assign_five_min_fun_to_routine'),
    path('mark_kid_five_min_fun_completed/', views.mark_kid_five_min_fun_completed, name='mark_kid_five_min_fun_completed'),

    # NEW for Vendor Routines
    path('routine/create/', views.create_routine, name='create_routine'),
    path('routine/<int:routine_id>/manage/', views.manage_routine, name='manage_routine'),
    path('routine/<int:routine_id>/delete/', views.delete_routine, name='delete_routine'),
    path('routine/list/', views.routine_list, name='routine_list'),

    # NEW: Popup for routine assignment from Five Min Fun (PLACED HERE to avoid dynamic slug conflicts)
    path('assign_routine_from_fun/<int:fun_id>/<int:routine_id>/', views.assign_routine_from_fun, name='assign_routine_from_fun'),

    # Dynamic paths last (they can catch anything)
    path('<slug:slug>/', views.event_detail, name='event_detail'),
    path('five-min-fun/<str:slug>/', views.five_min_fun_detail, name='five_min_fun_detail'),
    path('routine/<str:slug>/', views.routine_detail, name='routine_detail'),
]

urlpatterns += [
    path('get_routine_instance/<int:instance_id>/', views.get_routine_instance, name='get_routine_instance'),
]