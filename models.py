"""Appointments models."""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models.base import HubBaseModel


class AppointmentsSettings(HubBaseModel):
    """Per-hub appointments configuration."""

    # Booking settings
    default_duration = models.PositiveIntegerField(default=60, help_text=_('Default duration in minutes'))
    min_booking_notice = models.PositiveIntegerField(default=60, help_text=_('Minimum notice for booking (minutes)'))
    max_advance_booking = models.PositiveIntegerField(default=90, help_text=_('Maximum days in advance'))

    # Overlap settings
    allow_overlapping = models.BooleanField(default=False, help_text=_('Allow overlapping appointments for same staff'))

    # Reminder settings
    send_reminders = models.BooleanField(default=True)
    reminder_hours_before = models.PositiveIntegerField(default=24)

    # Cancellation settings
    allow_customer_cancellation = models.BooleanField(default=True)
    cancellation_notice_hours = models.PositiveIntegerField(default=24)

    # Calendar display settings
    calendar_start_hour = models.PositiveIntegerField(default=8)
    calendar_end_hour = models.PositiveIntegerField(default=20)
    slot_interval = models.PositiveIntegerField(default=15, help_text=_('Time slot interval in minutes'))

    class Meta(HubBaseModel.Meta):
        db_table = 'appointments_settings'
        verbose_name = _('Appointments Settings')
        verbose_name_plural = _('Appointments Settings')
        unique_together = [('hub_id',)]

    def __str__(self):
        return f'Appointments Settings (Hub {self.hub_id})'

    @classmethod
    def get_settings(cls, hub_id):
        settings, _ = cls.all_objects.get_or_create(hub_id=hub_id)
        return settings


class Schedule(HubBaseModel):
    """Working schedule template for staff/service availability."""

    DAYS_OF_WEEK = [
        (0, _('Monday')),
        (1, _('Tuesday')),
        (2, _('Wednesday')),
        (3, _('Thursday')),
        (4, _('Friday')),
        (5, _('Saturday')),
        (6, _('Sunday')),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'appointments_schedule'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            Schedule.objects.filter(hub_id=self.hub_id, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def get_time_slots(self, day_of_week):
        return self.time_slots.filter(day_of_week=day_of_week, is_active=True)

    def is_available_at(self, day_of_week, time):
        for slot in self.get_time_slots(day_of_week):
            if slot.start_time <= time <= slot.end_time:
                return True
        return False


class ScheduleTimeSlot(HubBaseModel):
    """Time slot within a schedule."""

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='time_slots')
    day_of_week = models.PositiveSmallIntegerField(choices=Schedule.DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'appointments_schedule_timeslot'
        ordering = ['day_of_week', 'start_time']
        unique_together = [('schedule', 'day_of_week', 'start_time')]

    def __str__(self):
        day_name = dict(Schedule.DAYS_OF_WEEK).get(self.day_of_week, '')
        return f"{day_name}: {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError(_('End time must be after start time'))

    @property
    def duration_minutes(self):
        start_dt = timezone.datetime.combine(timezone.datetime.today(), self.start_time)
        end_dt = timezone.datetime.combine(timezone.datetime.today(), self.end_time)
        return int((end_dt - start_dt).total_seconds() / 60)


class BlockedTime(HubBaseModel):
    """Blocked time periods (holidays, breaks, vacations)."""

    BLOCK_TYPE_CHOICES = [
        ('holiday', _('Holiday')),
        ('vacation', _('Vacation')),
        ('break', _('Break')),
        ('maintenance', _('Maintenance')),
        ('other', _('Other')),
    ]

    title = models.CharField(max_length=200)
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPE_CHOICES, default='other')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    all_day = models.BooleanField(default=False)

    # Optional: block for specific staff
    staff = models.ForeignKey(
        'accounts.LocalUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='blocked_times'
    )

    reason = models.TextField(blank=True)
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=200, blank=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'appointments_blocked_time'
        ordering = ['start_datetime']

    def __str__(self):
        return f"{self.title} ({self.start_datetime.date()})"

    def clean(self):
        if self.start_datetime and self.end_datetime and self.start_datetime >= self.end_datetime:
            raise ValidationError(_('End datetime must be after start datetime'))

    @property
    def duration(self):
        return self.end_datetime - self.start_datetime

    def conflicts_with(self, start_dt, end_dt, staff=None):
        if self.staff_id is not None and staff is not None:
            if self.staff_id != staff.pk:
                return False
        return self.start_datetime < end_dt and self.end_datetime > start_dt


class Appointment(HubBaseModel):
    """An appointment/booking."""

    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('confirmed', _('Confirmed')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
        ('no_show', _('No Show')),
    ]

    appointment_number = models.CharField(max_length=20, blank=True)

    # Customer (FK to customers module)
    customer = models.ForeignKey(
        'customers.Customer', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='appointments'
    )
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=50, blank=True)
    customer_email = models.EmailField(blank=True)

    # Staff (FK to LocalUser)
    staff = models.ForeignKey(
        'accounts.LocalUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='appointments'
    )
    staff_name = models.CharField(max_length=200, blank=True)

    # Service (FK to services module)
    service = models.ForeignKey(
        'services.Service', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='appointments'
    )
    service_name = models.CharField(max_length=200)
    service_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Timing
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Additional info
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    # Reminder tracking
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    # Source
    booked_online = models.BooleanField(default=False)

    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'appointments_appointment'
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['hub_id', 'start_datetime', 'status']),
            models.Index(fields=['hub_id', 'customer_id']),
            models.Index(fields=['hub_id', 'staff_id', 'start_datetime']),
        ]

    def __str__(self):
        return f"{self.appointment_number} - {self.customer_name} ({self.start_datetime.strftime('%Y-%m-%d %H:%M')})"

    def save(self, *args, **kwargs):
        if not self.appointment_number:
            self.appointment_number = self._generate_number()
        if not self.end_datetime and self.start_datetime and self.duration_minutes:
            self.end_datetime = self.start_datetime + timedelta(minutes=self.duration_minutes)
        super().save(*args, **kwargs)

    def _generate_number(self):
        today = timezone.now()
        prefix = f"APT-{today.strftime('%Y%m%d')}"
        last = Appointment.all_objects.filter(
            hub_id=self.hub_id,
            appointment_number__startswith=prefix,
        ).order_by('-appointment_number').first()
        if last and last.appointment_number:
            try:
                seq = int(last.appointment_number.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}-{seq:04d}"

    @property
    def is_past(self):
        return self.end_datetime < timezone.now()

    @property
    def is_today(self):
        return self.start_datetime.date() == timezone.now().date()

    @property
    def can_cancel(self):
        if self.status in ['cancelled', 'completed', 'no_show']:
            return False
        return self.start_datetime > timezone.now()

    @property
    def can_start(self):
        return self.status == 'confirmed' and not self.is_past

    @property
    def can_confirm(self):
        return self.status == 'pending' and not self.is_past

    @property
    def can_complete(self):
        return self.status in ['confirmed', 'in_progress']

    @property
    def status_class(self):
        return {
            'pending': 'warning',
            'confirmed': 'info',
            'in_progress': 'primary',
            'completed': 'success',
            'cancelled': 'neutral',
            'no_show': 'danger',
        }.get(self.status, 'neutral')

    def confirm(self):
        if self.status == 'pending':
            self.status = 'confirmed'
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    def start(self):
        if self.status == 'confirmed':
            self.status = 'in_progress'
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    def complete(self):
        if self.status in ['confirmed', 'in_progress']:
            self.status = 'completed'
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    def cancel(self, reason=''):
        if self.status not in ['cancelled', 'completed']:
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
            self.cancellation_reason = reason
            self.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'updated_at'])
            return True
        return False

    def mark_no_show(self):
        if self.status in ['pending', 'confirmed'] and self.is_past:
            self.status = 'no_show'
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    def reschedule(self, new_start, new_duration=None):
        if self.status in ['pending', 'confirmed']:
            self.start_datetime = new_start
            if new_duration:
                self.duration_minutes = new_duration
            self.end_datetime = self.start_datetime + timedelta(minutes=self.duration_minutes)
            self.save(update_fields=['start_datetime', 'end_datetime', 'duration_minutes', 'updated_at'])
            return True
        return False

    @classmethod
    def get_for_date(cls, hub_id, date):
        return cls.objects.filter(
            hub_id=hub_id, is_deleted=False,
            start_datetime__date=date,
        ).exclude(status='cancelled').order_by('start_datetime')

    @classmethod
    def get_upcoming(cls, hub_id, limit=10):
        return cls.objects.filter(
            hub_id=hub_id, is_deleted=False,
            start_datetime__gte=timezone.now(),
            status__in=['pending', 'confirmed'],
        ).order_by('start_datetime')[:limit]


class AppointmentHistory(HubBaseModel):
    """Audit log for appointment changes."""

    ACTION_CHOICES = [
        ('created', _('Created')),
        ('confirmed', _('Confirmed')),
        ('started', _('Started')),
        ('rescheduled', _('Rescheduled')),
        ('cancelled', _('Cancelled')),
        ('completed', _('Completed')),
        ('no_show', _('Marked No Show')),
        ('note_added', _('Note Added')),
    ]

    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        'accounts.LocalUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+'
    )
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'appointments_history'
        ordering = ['-created_at']
        verbose_name_plural = _('Appointment histories')

    def __str__(self):
        return f"{self.appointment.appointment_number} - {self.action}"

    @classmethod
    def log(cls, appointment, action, description='', performed_by=None, old_value=None, new_value=None):
        return cls.objects.create(
            hub_id=appointment.hub_id,
            appointment=appointment,
            action=action,
            description=description,
            performed_by=performed_by,
            old_value=old_value,
            new_value=new_value,
        )


class RecurringAppointment(HubBaseModel):
    """Template for recurring appointments."""

    FREQUENCY_CHOICES = [
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('biweekly', _('Every 2 Weeks')),
        ('monthly', _('Monthly')),
    ]

    # Customer
    customer = models.ForeignKey(
        'customers.Customer', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='recurring_appointments'
    )
    customer_name = models.CharField(max_length=200)

    # Service/Staff
    service = models.ForeignKey(
        'services.Service', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='recurring_appointments'
    )
    service_name = models.CharField(max_length=200)
    staff = models.ForeignKey(
        'accounts.LocalUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='recurring_appointments'
    )
    staff_name = models.CharField(max_length=200, blank=True)

    # Recurrence
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    day_of_week = models.PositiveSmallIntegerField(choices=Schedule.DAYS_OF_WEEK, null=True, blank=True)
    time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()

    # Range
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    max_occurrences = models.PositiveIntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'appointments_recurring'
        ordering = ['customer_name', 'start_date']

    def __str__(self):
        return f"{self.customer_name} - {self.service_name} ({self.frequency})"

    def get_next_occurrence(self, after_date=None):
        if after_date is None:
            after_date = timezone.now().date()
        if self.end_date and after_date > self.end_date:
            return None

        current = max(self.start_date, after_date)

        if self.frequency == 'daily':
            return current
        elif self.frequency == 'weekly':
            if self.day_of_week is not None:
                days_ahead = self.day_of_week - current.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return current + timedelta(days=days_ahead)
        elif self.frequency == 'biweekly':
            if self.day_of_week is not None:
                days_ahead = self.day_of_week - current.weekday()
                if days_ahead <= 0:
                    days_ahead += 14
                return current + timedelta(days=days_ahead)
        elif self.frequency == 'monthly':
            next_month = current.replace(day=self.start_date.day)
            if next_month <= current:
                if current.month == 12:
                    next_month = current.replace(year=current.year + 1, month=1, day=self.start_date.day)
                else:
                    next_month = current.replace(month=current.month + 1, day=self.start_date.day)
            return next_month

        return current
