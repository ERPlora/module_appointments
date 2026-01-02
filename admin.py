from django.contrib import admin
from .models import (
    AppointmentsConfig,
    Schedule,
    ScheduleTimeSlot,
    BlockedTime,
    Appointment,
    AppointmentHistory,
    RecurringAppointment,
)


@admin.register(AppointmentsConfig)
class AppointmentsConfigAdmin(admin.ModelAdmin):
    list_display = ['default_duration', 'min_booking_notice', 'max_advance_booking']


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_default', 'is_active']
    list_filter = ['is_active', 'is_default']


@admin.register(ScheduleTimeSlot)
class ScheduleTimeSlotAdmin(admin.ModelAdmin):
    list_display = ['schedule', 'day_of_week', 'start_time', 'end_time']
    list_filter = ['schedule', 'day_of_week']


@admin.register(BlockedTime)
class BlockedTimeAdmin(admin.ModelAdmin):
    list_display = ['title', 'block_type', 'start_datetime', 'end_datetime']
    list_filter = ['block_type']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['appointment_number', 'customer_name', 'service_name', 'start_datetime', 'status']
    list_filter = ['status', 'start_datetime']
    search_fields = ['appointment_number', 'customer_name', 'customer_phone']


@admin.register(AppointmentHistory)
class AppointmentHistoryAdmin(admin.ModelAdmin):
    list_display = ['appointment', 'action', 'created_at']
    list_filter = ['action']


@admin.register(RecurringAppointment)
class RecurringAppointmentAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'service_name', 'frequency', 'is_active']
    list_filter = ['frequency', 'is_active']
