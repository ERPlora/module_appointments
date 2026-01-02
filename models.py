from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid
from datetime import timedelta


class AppointmentsConfig(models.Model):
    """Singleton configuration for appointments module."""

    # Booking settings
    default_duration = models.PositiveIntegerField(
        default=60,
        help_text="Default appointment duration in minutes"
    )
    min_booking_notice = models.PositiveIntegerField(
        default=60,
        help_text="Minimum notice required for booking (minutes)"
    )
    max_advance_booking = models.PositiveIntegerField(
        default=90,
        help_text="Maximum days in advance for booking"
    )

    # Overlap settings
    allow_overlapping = models.BooleanField(
        default=False,
        help_text="Allow overlapping appointments for same staff"
    )

    # Reminder settings
    send_reminders = models.BooleanField(default=True)
    reminder_hours_before = models.PositiveIntegerField(
        default=24,
        help_text="Hours before appointment to send reminder"
    )

    # Cancellation settings
    allow_customer_cancellation = models.BooleanField(default=True)
    cancellation_notice_hours = models.PositiveIntegerField(
        default=24,
        help_text="Minimum hours notice for cancellation"
    )

    # Display settings
    calendar_start_hour = models.PositiveIntegerField(default=8)
    calendar_end_hour = models.PositiveIntegerField(default=20)
    slot_interval = models.PositiveIntegerField(
        default=15,
        help_text="Time slot interval in minutes"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Appointments Configuration'
        verbose_name_plural = 'Appointments Configuration'

    def __str__(self):
        return "Appointments Configuration"

    @classmethod
    def get_config(cls):
        """Get or create singleton configuration."""
        config, _ = cls.objects.get_or_create(pk=1)
        return config


class Schedule(models.Model):
    """Working schedule template for staff/service availability."""

    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            Schedule.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def get_time_slots(self, day_of_week):
        """Get all time slots for a specific day."""
        return self.time_slots.filter(day_of_week=day_of_week, is_active=True)

    def is_available_at(self, day_of_week, time):
        """Check if schedule is available at a specific day and time."""
        slots = self.get_time_slots(day_of_week)
        for slot in slots:
            if slot.start_time <= time <= slot.end_time:
                return True
        return False


class ScheduleTimeSlot(models.Model):
    """Time slot within a schedule (e.g., Monday 9:00-13:00)."""

    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='time_slots'
    )
    day_of_week = models.PositiveSmallIntegerField(choices=Schedule.DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']
        unique_together = ['schedule', 'day_of_week', 'start_time']

    def __str__(self):
        day_name = dict(Schedule.DAYS_OF_WEEK).get(self.day_of_week)
        return f"{day_name}: {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")

    @property
    def duration_minutes(self):
        """Get duration in minutes."""
        start_dt = timezone.datetime.combine(timezone.datetime.today(), self.start_time)
        end_dt = timezone.datetime.combine(timezone.datetime.today(), self.end_time)
        return int((end_dt - start_dt).total_seconds() / 60)


class BlockedTime(models.Model):
    """Blocked time periods (holidays, breaks, vacations)."""

    BLOCK_TYPE_CHOICES = [
        ('holiday', 'Holiday'),
        ('vacation', 'Vacation'),
        ('break', 'Break'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=200)
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPE_CHOICES, default='other')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    all_day = models.BooleanField(default=False)

    # Optional: block for specific staff only (null = all staff)
    staff_id = models.PositiveIntegerField(null=True, blank=True)

    reason = models.TextField(blank=True)
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=200, blank=True)  # iCal RRULE format

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_datetime']

    def __str__(self):
        return f"{self.title} ({self.start_datetime.date()})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_datetime >= self.end_datetime:
            raise ValidationError("End datetime must be after start datetime")

    @property
    def duration(self):
        """Get duration as timedelta."""
        return self.end_datetime - self.start_datetime

    def conflicts_with(self, start_dt, end_dt, staff_id=None):
        """Check if this block conflicts with a time range."""
        # Check staff match (null means all staff)
        if self.staff_id is not None and staff_id is not None:
            if self.staff_id != staff_id:
                return False

        # Check time overlap
        return self.start_datetime < end_dt and self.end_datetime > start_dt


class Appointment(models.Model):
    """An appointment/booking."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]

    # Unique identifier
    appointment_number = models.CharField(max_length=20, unique=True, blank=True)

    # Customer (reference to customers module)
    customer_id = models.PositiveIntegerField(null=True, blank=True)
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=50, blank=True)
    customer_email = models.EmailField(blank=True)

    # Staff (reference to staff module)
    staff_id = models.PositiveIntegerField(null=True, blank=True)
    staff_name = models.CharField(max_length=200, blank=True)

    # Service (reference to services module)
    service_id = models.PositiveIntegerField(null=True, blank=True)
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
    created_by_id = models.PositiveIntegerField(null=True, blank=True)

    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['start_datetime', 'status']),
            models.Index(fields=['customer_id']),
            models.Index(fields=['staff_id', 'start_datetime']),
        ]

    def __str__(self):
        return f"{self.appointment_number} - {self.customer_name} ({self.start_datetime.strftime('%Y-%m-%d %H:%M')})"

    def save(self, *args, **kwargs):
        if not self.appointment_number:
            self.appointment_number = self.generate_appointment_number()
        if not self.end_datetime and self.start_datetime and self.duration_minutes:
            self.end_datetime = self.start_datetime + timedelta(minutes=self.duration_minutes)
        super().save(*args, **kwargs)

    @staticmethod
    def generate_appointment_number():
        """Generate unique appointment number."""
        today = timezone.now()
        prefix = today.strftime('%Y%m%d')
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f"APT-{prefix}-{random_suffix}"

    @property
    def is_past(self):
        """Check if appointment is in the past."""
        return self.end_datetime < timezone.now()

    @property
    def is_today(self):
        """Check if appointment is today."""
        return self.start_datetime.date() == timezone.now().date()

    @property
    def can_cancel(self):
        """Check if appointment can still be cancelled."""
        if self.status in ['cancelled', 'completed', 'no_show']:
            return False
        config = AppointmentsConfig.get_config()
        min_notice = timedelta(hours=config.cancellation_notice_hours)
        return self.start_datetime > timezone.now() + min_notice

    @property
    def can_start(self):
        """Check if appointment can be started."""
        return self.status == 'confirmed' and not self.is_past

    def confirm(self):
        """Confirm the appointment."""
        if self.status == 'pending':
            self.status = 'confirmed'
            self.save()
            return True
        return False

    def start(self):
        """Start the appointment (in progress)."""
        if self.status == 'confirmed':
            self.status = 'in_progress'
            self.save()
            return True
        return False

    def complete(self):
        """Mark appointment as completed."""
        if self.status in ['confirmed', 'in_progress']:
            self.status = 'completed'
            self.save()
            return True
        return False

    def cancel(self, reason=''):
        """Cancel the appointment."""
        if self.status not in ['cancelled', 'completed']:
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
            self.cancellation_reason = reason
            self.save()
            return True
        return False

    def mark_no_show(self):
        """Mark customer as no-show."""
        if self.status in ['pending', 'confirmed'] and self.is_past:
            self.status = 'no_show'
            self.save()
            return True
        return False

    def reschedule(self, new_start_datetime, new_duration=None):
        """Reschedule the appointment."""
        if self.status in ['pending', 'confirmed']:
            self.start_datetime = new_start_datetime
            if new_duration:
                self.duration_minutes = new_duration
            self.end_datetime = self.start_datetime + timedelta(minutes=self.duration_minutes)
            self.save()
            return True
        return False

    def send_reminder(self):
        """Mark reminder as sent."""
        if not self.reminder_sent:
            self.reminder_sent = True
            self.reminder_sent_at = timezone.now()
            self.save()
            return True
        return False


class AppointmentHistory(models.Model):
    """History/audit log for appointment changes."""

    ACTION_CHOICES = [
        ('created', 'Created'),
        ('confirmed', 'Confirmed'),
        ('rescheduled', 'Rescheduled'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('no_show', 'Marked No Show'),
        ('note_added', 'Note Added'),
    ]

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    performed_by_id = models.PositiveIntegerField(null=True, blank=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Appointment histories'

    def __str__(self):
        return f"{self.appointment.appointment_number} - {self.action}"

    @classmethod
    def log(cls, appointment, action, description='', performed_by_id=None, old_value=None, new_value=None):
        """Create a history entry."""
        return cls.objects.create(
            appointment=appointment,
            action=action,
            description=description,
            performed_by_id=performed_by_id,
            old_value=old_value,
            new_value=new_value
        )


class RecurringAppointment(models.Model):
    """Template for recurring appointments."""

    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Every 2 Weeks'),
        ('monthly', 'Monthly'),
    ]

    # Customer info
    customer_id = models.PositiveIntegerField(null=True, blank=True)
    customer_name = models.CharField(max_length=200)

    # Service/Staff
    service_id = models.PositiveIntegerField(null=True, blank=True)
    service_name = models.CharField(max_length=200)
    staff_id = models.PositiveIntegerField(null=True, blank=True)
    staff_name = models.CharField(max_length=200, blank=True)

    # Recurrence
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    day_of_week = models.PositiveSmallIntegerField(
        choices=Schedule.DAYS_OF_WEEK,
        null=True,
        blank=True
    )
    time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()

    # Range
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    max_occurrences = models.PositiveIntegerField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['customer_name', 'start_date']

    def __str__(self):
        return f"{self.customer_name} - {self.service_name} ({self.frequency})"

    def get_next_occurrence(self, after_date=None):
        """Get the next occurrence date."""
        from datetime import date
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
            # Same day of month
            next_month = current.replace(day=self.start_date.day)
            if next_month <= current:
                if current.month == 12:
                    next_month = current.replace(year=current.year + 1, month=1, day=self.start_date.day)
                else:
                    next_month = current.replace(month=current.month + 1, day=self.start_date.day)
            return next_month

        return current

    def generate_appointments(self, until_date):
        """Generate appointment instances until a date."""
        appointments = []
        current_date = self.start_date
        count = 0

        while current_date <= until_date:
            if self.end_date and current_date > self.end_date:
                break
            if self.max_occurrences and count >= self.max_occurrences:
                break

            start_dt = timezone.make_aware(
                timezone.datetime.combine(current_date, self.time)
            )

            appointment = Appointment(
                customer_id=self.customer_id,
                customer_name=self.customer_name,
                service_id=self.service_id,
                service_name=self.service_name,
                staff_id=self.staff_id,
                staff_name=self.staff_name,
                start_datetime=start_dt,
                duration_minutes=self.duration_minutes,
                status='pending'
            )
            appointments.append(appointment)
            count += 1

            # Calculate next occurrence
            if self.frequency == 'daily':
                current_date += timedelta(days=1)
            elif self.frequency == 'weekly':
                current_date += timedelta(weeks=1)
            elif self.frequency == 'biweekly':
                current_date += timedelta(weeks=2)
            elif self.frequency == 'monthly':
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)

        return appointments
