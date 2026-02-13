"""Appointments URL Configuration."""

from django.urls import path
from . import views

app_name = 'appointments'

urlpatterns = [
    # Dashboard
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Calendar
    path('calendar/', views.calendar_view, name='calendar'),
    path('calendar/data/', views.calendar_data, name='calendar_data'),

    # Appointments list
    path('list/', views.appointments_list, name='list'),
    path('create/', views.appointment_create, name='create'),
    path('<uuid:pk>/', views.appointment_detail, name='detail'),
    path('<uuid:pk>/edit/', views.appointment_edit, name='edit'),
    path('<uuid:pk>/delete/', views.appointment_delete, name='delete'),

    # Appointment actions
    path('<uuid:pk>/confirm/', views.appointment_confirm, name='confirm'),
    path('<uuid:pk>/start/', views.appointment_start, name='start'),
    path('<uuid:pk>/cancel/', views.appointment_cancel, name='cancel'),
    path('<uuid:pk>/complete/', views.appointment_complete, name='complete'),
    path('<uuid:pk>/no-show/', views.appointment_no_show, name='no_show'),
    path('<uuid:pk>/reschedule/', views.appointment_reschedule, name='reschedule'),

    # Availability
    path('availability/', views.check_availability, name='availability'),
    path('availability/slots/', views.get_available_slots, name='available_slots'),

    # Schedules
    path('schedules/', views.schedules_list, name='schedules'),
    path('schedules/add/', views.schedule_add, name='schedule_add'),
    path('schedules/<uuid:pk>/', views.schedule_detail, name='schedule_detail'),
    path('schedules/<uuid:pk>/edit/', views.schedule_edit, name='schedule_edit'),
    path('schedules/<uuid:pk>/delete/', views.schedule_delete, name='schedule_delete'),
    path('schedules/<uuid:pk>/slots/add/', views.add_time_slot, name='add_time_slot'),
    path('schedules/slots/<uuid:pk>/delete/', views.delete_time_slot, name='delete_time_slot'),

    # Blocked times
    path('blocked/', views.blocked_times_list, name='blocked_list'),
    path('blocked/add/', views.blocked_time_add, name='blocked_add'),
    path('blocked/<uuid:pk>/delete/', views.blocked_time_delete, name='blocked_delete'),

    # Recurring appointments
    path('recurring/', views.recurring_list, name='recurring_list'),
    path('recurring/add/', views.recurring_add, name='recurring_add'),
    path('recurring/<uuid:pk>/', views.recurring_detail, name='recurring_detail'),
    path('recurring/<uuid:pk>/delete/', views.recurring_delete, name='recurring_delete'),
    path('recurring/<uuid:pk>/generate/', views.recurring_generate, name='recurring_generate'),

    # Settings
    path('settings/', views.settings, name='settings'),
    path('settings/save/', views.settings_save, name='settings_save'),
    path('settings/toggle/', views.settings_toggle, name='settings_toggle'),
    path('settings/input/', views.settings_input, name='settings_input'),
    path('settings/reset/', views.settings_reset, name='settings_reset'),
]
