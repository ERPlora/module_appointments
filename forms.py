"""Appointments forms."""

from datetime import datetime

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import (
    Appointment,
    Schedule,
    ScheduleTimeSlot,
    BlockedTime,
    RecurringAppointment,
    AppointmentsSettings,
)


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'customer_name', 'customer_phone', 'customer_email',
            'service_name', 'service_price',
            'staff_name', 'start_datetime', 'duration_minutes',
            'notes', 'internal_notes',
        ]
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'input'}),
            'customer_phone': forms.TextInput(attrs={'class': 'input'}),
            'customer_email': forms.EmailInput(attrs={'class': 'input'}),
            'service_name': forms.TextInput(attrs={'class': 'input'}),
            'service_price': forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'min': '0'}),
            'staff_name': forms.TextInput(attrs={'class': 'input'}),
            'start_datetime': forms.DateTimeInput(attrs={'class': 'input', 'type': 'datetime-local'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'input', 'min': '5'}),
            'notes': forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
            'internal_notes': forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
        }


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ['name', 'description', 'is_default', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input'}),
            'description': forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
            'is_default': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'toggle'}),
        }


class ScheduleTimeSlotForm(forms.ModelForm):
    class Meta:
        model = ScheduleTimeSlot
        fields = ['day_of_week', 'start_time', 'end_time', 'is_active']
        widgets = {
            'day_of_week': forms.Select(attrs={'class': 'select'}),
            'start_time': forms.TimeInput(attrs={'class': 'input', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'input', 'type': 'time'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'toggle'}),
        }


class BlockedTimeForm(forms.ModelForm):
    class Meta:
        model = BlockedTime
        fields = ['title', 'block_type', 'start_datetime', 'end_datetime', 'all_day', 'reason']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'input'}),
            'block_type': forms.Select(attrs={'class': 'select'}),
            'start_datetime': forms.DateTimeInput(attrs={'class': 'input', 'type': 'datetime-local'}),
            'end_datetime': forms.DateTimeInput(attrs={'class': 'input', 'type': 'datetime-local'}),
            'all_day': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'reason': forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
        }


class RecurringAppointmentForm(forms.ModelForm):
    class Meta:
        model = RecurringAppointment
        fields = [
            'customer_name', 'service_name', 'staff_name',
            'frequency', 'day_of_week', 'time', 'duration_minutes',
            'start_date', 'end_date', 'max_occurrences',
        ]
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'input'}),
            'service_name': forms.TextInput(attrs={'class': 'input'}),
            'staff_name': forms.TextInput(attrs={'class': 'input'}),
            'frequency': forms.Select(attrs={'class': 'select'}),
            'day_of_week': forms.Select(attrs={'class': 'select'}),
            'time': forms.TimeInput(attrs={'class': 'input', 'type': 'time'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'input', 'min': '5'}),
            'start_date': forms.DateInput(attrs={'class': 'input', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'input', 'type': 'date'}),
            'max_occurrences': forms.NumberInput(attrs={'class': 'input', 'min': '1'}),
        }


class AppointmentFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'input', 'placeholder': _('Search appointments...')
    }))
    status = forms.ChoiceField(required=False, choices=[('', _('All statuses'))] + Appointment.STATUS_CHOICES, widget=forms.Select(attrs={'class': 'select'}))
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={'class': 'input', 'type': 'date'}))


class AppointmentsSettingsForm(forms.ModelForm):
    class Meta:
        model = AppointmentsSettings
        fields = [
            'default_duration', 'min_booking_notice', 'max_advance_booking',
            'allow_overlapping', 'send_reminders', 'reminder_hours_before',
            'allow_customer_cancellation', 'cancellation_notice_hours',
            'calendar_start_hour', 'calendar_end_hour', 'slot_interval',
        ]
        widgets = {
            'default_duration': forms.NumberInput(attrs={'class': 'input', 'min': '5'}),
            'min_booking_notice': forms.NumberInput(attrs={'class': 'input', 'min': '0'}),
            'max_advance_booking': forms.NumberInput(attrs={'class': 'input', 'min': '1'}),
            'allow_overlapping': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'send_reminders': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'reminder_hours_before': forms.NumberInput(attrs={'class': 'input', 'min': '1'}),
            'allow_customer_cancellation': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'cancellation_notice_hours': forms.NumberInput(attrs={'class': 'input', 'min': '0'}),
            'calendar_start_hour': forms.NumberInput(attrs={'class': 'input', 'min': '0', 'max': '23'}),
            'calendar_end_hour': forms.NumberInput(attrs={'class': 'input', 'min': '1', 'max': '24'}),
            'slot_interval': forms.NumberInput(attrs={'class': 'input', 'min': '5'}),
        }
