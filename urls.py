from django.urls import path
from . import views

app_name = 'appointments'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Calendar view
    path('calendar/', views.calendar_view, name='calendar'),
    path('calendar/data/', views.calendar_data, name='calendar_data'),

    # Appointments list
    path('appointments/', views.appointments_list, name='appointments_list'),
    path('appointments/create/', views.appointment_create, name='appointment_create'),
    path('appointments/<int:pk>/', views.appointment_detail, name='appointment_detail'),
    path('appointments/<int:pk>/edit/', views.appointment_edit, name='appointment_edit'),
    path('appointments/<int:pk>/delete/', views.appointment_delete, name='appointment_delete'),

    # Appointment actions
    path('appointments/<int:pk>/confirm/', views.appointment_confirm, name='appointment_confirm'),
    path('appointments/<int:pk>/cancel/', views.appointment_cancel, name='appointment_cancel'),
    path('appointments/<int:pk>/complete/', views.appointment_complete, name='appointment_complete'),
    path('appointments/<int:pk>/no-show/', views.appointment_no_show, name='appointment_no_show'),
    path('appointments/<int:pk>/reschedule/', views.appointment_reschedule, name='appointment_reschedule'),

    # Availability
    path('availability/', views.check_availability, name='check_availability'),
    path('availability/slots/', views.get_available_slots, name='get_available_slots'),

    # Schedules
    path('schedules/', views.schedules_list, name='schedules_list'),
    path('schedules/create/', views.schedule_create, name='schedule_create'),
    path('schedules/<int:pk>/', views.schedule_detail, name='schedule_detail'),
    path('schedules/<int:pk>/edit/', views.schedule_edit, name='schedule_edit'),
    path('schedules/<int:pk>/delete/', views.schedule_delete, name='schedule_delete'),
    path('schedules/<int:pk>/slots/', views.schedule_slots, name='schedule_slots'),
    path('schedules/<int:pk>/slots/add/', views.add_time_slot, name='add_time_slot'),
    path('schedules/slots/<int:slot_id>/delete/', views.delete_time_slot, name='delete_time_slot'),

    # Blocked times
    path('blocked/', views.blocked_times_list, name='blocked_times_list'),
    path('blocked/create/', views.blocked_time_create, name='blocked_time_create'),
    path('blocked/<int:pk>/delete/', views.blocked_time_delete, name='blocked_time_delete'),

    # Recurring appointments
    path('recurring/', views.recurring_list, name='recurring_list'),
    path('recurring/create/', views.recurring_create, name='recurring_create'),
    path('recurring/<int:pk>/', views.recurring_detail, name='recurring_detail'),
    path('recurring/<int:pk>/delete/', views.recurring_delete, name='recurring_delete'),
    path('recurring/<int:pk>/generate/', views.recurring_generate, name='recurring_generate'),

    # Settings
    path('settings/', views.settings_view, name='settings'),
    path('settings/save/', views.settings_save, name='settings_save'),
    path('settings/toggle/', views.settings_toggle, name='settings_toggle'),
]
