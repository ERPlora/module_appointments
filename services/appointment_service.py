"""
Appointment Service

Business logic for appointment management.
"""
from datetime import datetime, timedelta, date, time
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Count
from django.db import transaction

from ..models import (
    AppointmentsConfig,
    Schedule,
    ScheduleTimeSlot,
    BlockedTime,
    Appointment,
    AppointmentHistory,
    RecurringAppointment,
)


class AppointmentService:
    """Service class for appointment business logic."""

    @staticmethod
    def get_config() -> AppointmentsConfig:
        """Get appointments configuration."""
        return AppointmentsConfig.get_config()

    # =========================================================================
    # APPOINTMENT CRUD
    # =========================================================================

    @staticmethod
    def create_appointment(
        customer_name: str,
        service_name: str,
        start_datetime: datetime,
        duration_minutes: int,
        customer_id: Optional[int] = None,
        customer_phone: str = '',
        customer_email: str = '',
        staff_id: Optional[int] = None,
        staff_name: str = '',
        service_id: Optional[int] = None,
        service_price: Decimal = Decimal('0.00'),
        notes: str = '',
        booked_online: bool = False,
        created_by_id: Optional[int] = None,
    ) -> Tuple[Optional[Appointment], Optional[str]]:
        """
        Create a new appointment.

        Returns:
            Tuple of (appointment, error_message)
        """
        config = AppointmentsConfig.get_config()

        # Validate booking notice
        min_notice = timedelta(minutes=config.min_booking_notice)
        if start_datetime < timezone.now() + min_notice:
            return None, f"Appointments must be booked at least {config.min_booking_notice} minutes in advance"

        # Validate advance booking
        max_advance = timedelta(days=config.max_advance_booking)
        if start_datetime > timezone.now() + max_advance:
            return None, f"Appointments cannot be booked more than {config.max_advance_booking} days in advance"

        # Check for conflicts
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        if not config.allow_overlapping and staff_id:
            conflict = AppointmentService.check_conflict(
                staff_id, start_datetime, end_datetime
            )
            if conflict:
                return None, f"Time slot conflicts with existing appointment: {conflict.appointment_number}"

        # Check blocked times
        blocked = AppointmentService.check_blocked_time(
            start_datetime, end_datetime, staff_id
        )
        if blocked:
            return None, f"Time slot is blocked: {blocked.title}"

        # Create appointment
        appointment = Appointment.objects.create(
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            staff_id=staff_id,
            staff_name=staff_name,
            service_id=service_id,
            service_name=service_name,
            service_price=service_price,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            duration_minutes=duration_minutes,
            notes=notes,
            booked_online=booked_online,
            created_by_id=created_by_id,
            status='pending',
        )

        # Log history
        AppointmentHistory.log(
            appointment,
            'created',
            f"Appointment created for {customer_name}",
            performed_by_id=created_by_id
        )

        return appointment, None

    @staticmethod
    def update_appointment(
        appointment: Appointment,
        **kwargs
    ) -> Tuple[bool, Optional[str]]:
        """Update an appointment."""
        old_values = {}

        # Track changes for history
        for field, value in kwargs.items():
            if hasattr(appointment, field):
                old_values[field] = getattr(appointment, field)
                setattr(appointment, field, value)

        # If datetime changed, recalculate end time
        if 'start_datetime' in kwargs or 'duration_minutes' in kwargs:
            appointment.end_datetime = (
                appointment.start_datetime +
                timedelta(minutes=appointment.duration_minutes)
            )

            # Check conflicts if staff assigned
            if appointment.staff_id:
                config = AppointmentsConfig.get_config()
                if not config.allow_overlapping:
                    conflict = AppointmentService.check_conflict(
                        appointment.staff_id,
                        appointment.start_datetime,
                        appointment.end_datetime,
                        exclude_id=appointment.id
                    )
                    if conflict:
                        return False, f"Time slot conflicts with: {conflict.appointment_number}"

        appointment.save()

        # Convert datetime objects to strings for JSON serialization
        def serialize_for_json(data):
            result = {}
            for key, value in data.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                else:
                    result[key] = value
            return result

        # Log history
        AppointmentHistory.log(
            appointment,
            'rescheduled' if 'start_datetime' in kwargs else 'note_added',
            'Appointment updated',
            old_value=serialize_for_json(old_values),
            new_value=serialize_for_json(kwargs)
        )

        return True, None

    @staticmethod
    def confirm_appointment(
        appointment: Appointment,
        confirmed_by_id: Optional[int] = None
    ) -> bool:
        """Confirm a pending appointment."""
        if appointment.confirm():
            AppointmentHistory.log(
                appointment,
                'confirmed',
                'Appointment confirmed',
                performed_by_id=confirmed_by_id
            )
            return True
        return False

    @staticmethod
    def cancel_appointment(
        appointment: Appointment,
        reason: str = '',
        cancelled_by_id: Optional[int] = None
    ) -> bool:
        """Cancel an appointment."""
        if appointment.cancel(reason):
            AppointmentHistory.log(
                appointment,
                'cancelled',
                f"Appointment cancelled: {reason}" if reason else "Appointment cancelled",
                performed_by_id=cancelled_by_id
            )
            return True
        return False

    @staticmethod
    def complete_appointment(
        appointment: Appointment,
        completed_by_id: Optional[int] = None
    ) -> bool:
        """Mark appointment as completed."""
        if appointment.complete():
            AppointmentHistory.log(
                appointment,
                'completed',
                'Appointment completed',
                performed_by_id=completed_by_id
            )
            return True
        return False

    @staticmethod
    def mark_no_show(
        appointment: Appointment,
        marked_by_id: Optional[int] = None
    ) -> bool:
        """Mark customer as no-show."""
        if appointment.mark_no_show():
            AppointmentHistory.log(
                appointment,
                'no_show',
                'Customer marked as no-show',
                performed_by_id=marked_by_id
            )
            return True
        return False

    @staticmethod
    def reschedule_appointment(
        appointment: Appointment,
        new_start_datetime: datetime,
        new_duration: Optional[int] = None,
        rescheduled_by_id: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """Reschedule an appointment to a new time."""
        config = AppointmentsConfig.get_config()
        duration = new_duration or appointment.duration_minutes
        new_end_datetime = new_start_datetime + timedelta(minutes=duration)

        # Check conflicts
        if appointment.staff_id and not config.allow_overlapping:
            conflict = AppointmentService.check_conflict(
                appointment.staff_id,
                new_start_datetime,
                new_end_datetime,
                exclude_id=appointment.id
            )
            if conflict:
                return False, f"Time slot conflicts with: {conflict.appointment_number}"

        # Check blocked times
        blocked = AppointmentService.check_blocked_time(
            new_start_datetime, new_end_datetime, appointment.staff_id
        )
        if blocked:
            return False, f"Time slot is blocked: {blocked.title}"

        old_datetime = appointment.start_datetime

        if appointment.reschedule(new_start_datetime, new_duration):
            AppointmentHistory.log(
                appointment,
                'rescheduled',
                f"Rescheduled from {old_datetime.strftime('%Y-%m-%d %H:%M')} to {new_start_datetime.strftime('%Y-%m-%d %H:%M')}",
                performed_by_id=rescheduled_by_id,
                old_value={'start_datetime': str(old_datetime)},
                new_value={'start_datetime': str(new_start_datetime)}
            )
            return True, None

        return False, "Cannot reschedule this appointment"

    # =========================================================================
    # AVAILABILITY & CONFLICTS
    # =========================================================================

    @staticmethod
    def check_conflict(
        staff_id: int,
        start_datetime: datetime,
        end_datetime: datetime,
        exclude_id: Optional[int] = None
    ) -> Optional[Appointment]:
        """Check if there's a conflicting appointment for the staff member."""
        query = Appointment.objects.filter(
            staff_id=staff_id,
            status__in=['pending', 'confirmed', 'in_progress'],
        ).filter(
            Q(start_datetime__lt=end_datetime) &
            Q(end_datetime__gt=start_datetime)
        )

        if exclude_id:
            query = query.exclude(id=exclude_id)

        return query.first()

    @staticmethod
    def check_blocked_time(
        start_datetime: datetime,
        end_datetime: datetime,
        staff_id: Optional[int] = None
    ) -> Optional[BlockedTime]:
        """Check if there's a blocked time period."""
        query = BlockedTime.objects.filter(
            start_datetime__lt=end_datetime,
            end_datetime__gt=start_datetime
        )

        if staff_id:
            query = query.filter(Q(staff_id__isnull=True) | Q(staff_id=staff_id))
        else:
            query = query.filter(staff_id__isnull=True)

        return query.first()

    @staticmethod
    def get_available_slots(
        target_date: date,
        duration_minutes: int,
        staff_id: Optional[int] = None,
        schedule: Optional[Schedule] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available time slots for a given date.

        Returns list of available slots with start time.
        """
        config = AppointmentsConfig.get_config()

        # Use default schedule if not provided
        if not schedule:
            schedule = Schedule.objects.filter(is_default=True, is_active=True).first()
            if not schedule:
                return []

        # Get time slots for the day of week
        day_of_week = target_date.weekday()
        time_slots = schedule.get_time_slots(day_of_week)

        if not time_slots:
            return []

        available_slots = []
        interval = timedelta(minutes=config.slot_interval)

        for slot in time_slots:
            current_time = timezone.make_aware(
                datetime.combine(target_date, slot.start_time)
            )
            slot_end = timezone.make_aware(
                datetime.combine(target_date, slot.end_time)
            )

            while current_time + timedelta(minutes=duration_minutes) <= slot_end:
                end_time = current_time + timedelta(minutes=duration_minutes)

                # Check if slot is available
                is_available = True

                # Check conflicts
                if staff_id:
                    if AppointmentService.check_conflict(staff_id, current_time, end_time):
                        is_available = False

                # Check blocked times
                if is_available:
                    if AppointmentService.check_blocked_time(current_time, end_time, staff_id):
                        is_available = False

                # Don't show past slots for today
                if is_available and target_date == timezone.now().date():
                    min_notice = timedelta(minutes=config.min_booking_notice)
                    if current_time < timezone.now() + min_notice:
                        is_available = False

                if is_available:
                    available_slots.append({
                        'start_time': current_time,
                        'end_time': end_time,
                        'formatted': current_time.strftime('%H:%M'),
                    })

                current_time += interval

        return available_slots

    # =========================================================================
    # SCHEDULE MANAGEMENT
    # =========================================================================

    @staticmethod
    def create_schedule(
        name: str,
        description: str = '',
        is_default: bool = False
    ) -> Schedule:
        """Create a new schedule."""
        return Schedule.objects.create(
            name=name,
            description=description,
            is_default=is_default,
            is_active=True
        )

    @staticmethod
    def add_time_slot(
        schedule: Schedule,
        day_of_week: int,
        start_time: time,
        end_time: time
    ) -> Tuple[Optional[ScheduleTimeSlot], Optional[str]]:
        """Add a time slot to a schedule."""
        if start_time >= end_time:
            return None, "End time must be after start time"

        # Check for overlapping slots
        existing = ScheduleTimeSlot.objects.filter(
            schedule=schedule,
            day_of_week=day_of_week,
            is_active=True
        ).filter(
            Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
        ).exists()

        if existing:
            return None, "Time slot overlaps with existing slot"

        slot = ScheduleTimeSlot.objects.create(
            schedule=schedule,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            is_active=True
        )

        return slot, None

    @staticmethod
    def remove_time_slot(slot: ScheduleTimeSlot) -> bool:
        """Remove a time slot from a schedule."""
        slot.delete()
        return True

    # =========================================================================
    # BLOCKED TIME MANAGEMENT
    # =========================================================================

    @staticmethod
    def create_blocked_time(
        title: str,
        start_datetime: datetime,
        end_datetime: datetime,
        block_type: str = 'other',
        staff_id: Optional[int] = None,
        reason: str = '',
        all_day: bool = False
    ) -> Tuple[Optional[BlockedTime], Optional[str]]:
        """Create a blocked time period."""
        if start_datetime >= end_datetime:
            return None, "End datetime must be after start datetime"

        blocked = BlockedTime.objects.create(
            title=title,
            block_type=block_type,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            all_day=all_day,
            staff_id=staff_id,
            reason=reason
        )

        return blocked, None

    @staticmethod
    def remove_blocked_time(blocked: BlockedTime) -> bool:
        """Remove a blocked time period."""
        blocked.delete()
        return True

    # =========================================================================
    # QUERIES
    # =========================================================================

    @staticmethod
    def get_appointments_for_date(
        target_date: date,
        staff_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Appointment]:
        """Get all appointments for a specific date."""
        query = Appointment.objects.filter(
            start_datetime__date=target_date
        )

        if staff_id:
            query = query.filter(staff_id=staff_id)

        if status:
            query = query.filter(status=status)

        return list(query.order_by('start_datetime'))

    @staticmethod
    def get_appointments_for_range(
        start_date: date,
        end_date: date,
        staff_id: Optional[int] = None
    ) -> List[Appointment]:
        """Get all appointments within a date range."""
        query = Appointment.objects.filter(
            start_datetime__date__gte=start_date,
            start_datetime__date__lte=end_date
        )

        if staff_id:
            query = query.filter(staff_id=staff_id)

        return list(query.order_by('start_datetime'))

    @staticmethod
    def get_upcoming_appointments(
        limit: int = 10,
        staff_id: Optional[int] = None
    ) -> List[Appointment]:
        """Get upcoming appointments."""
        query = Appointment.objects.filter(
            start_datetime__gte=timezone.now(),
            status__in=['pending', 'confirmed']
        )

        if staff_id:
            query = query.filter(staff_id=staff_id)

        return list(query.order_by('start_datetime')[:limit])

    @staticmethod
    def get_today_appointments(
        staff_id: Optional[int] = None
    ) -> List[Appointment]:
        """Get today's appointments."""
        return AppointmentService.get_appointments_for_date(
            timezone.now().date(),
            staff_id
        )

    @staticmethod
    def get_customer_appointments(
        customer_id: int,
        include_past: bool = False
    ) -> List[Appointment]:
        """Get appointments for a customer."""
        query = Appointment.objects.filter(customer_id=customer_id)

        if not include_past:
            query = query.filter(start_datetime__gte=timezone.now())

        return list(query.order_by('-start_datetime'))

    @staticmethod
    def get_pending_reminders() -> List[Appointment]:
        """Get appointments that need reminders sent."""
        config = AppointmentsConfig.get_config()

        if not config.send_reminders:
            return []

        reminder_time = timezone.now() + timedelta(hours=config.reminder_hours_before)

        return list(Appointment.objects.filter(
            status__in=['pending', 'confirmed'],
            reminder_sent=False,
            start_datetime__lte=reminder_time,
            start_datetime__gt=timezone.now()
        ))

    # =========================================================================
    # STATISTICS
    # =========================================================================

    @staticmethod
    def get_appointment_stats(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get appointment statistics."""
        if not start_date:
            start_date = timezone.now().date().replace(day=1)
        if not end_date:
            end_date = timezone.now().date()

        appointments = Appointment.objects.filter(
            start_datetime__date__gte=start_date,
            start_datetime__date__lte=end_date
        )

        total = appointments.count()
        completed = appointments.filter(status='completed').count()
        cancelled = appointments.filter(status='cancelled').count()
        no_shows = appointments.filter(status='no_show').count()

        # Revenue from completed appointments
        revenue = sum(
            a.service_price for a in appointments.filter(status='completed')
        )

        # By status
        by_status = {}
        for status, label in Appointment.STATUS_CHOICES:
            by_status[status] = appointments.filter(status=status).count()

        return {
            'total': total,
            'completed': completed,
            'cancelled': cancelled,
            'no_shows': no_shows,
            'completion_rate': (completed / total * 100) if total > 0 else 0,
            'cancellation_rate': (cancelled / total * 100) if total > 0 else 0,
            'no_show_rate': (no_shows / total * 100) if total > 0 else 0,
            'revenue': revenue,
            'by_status': by_status,
            'start_date': start_date,
            'end_date': end_date,
        }

    # =========================================================================
    # RECURRING APPOINTMENTS
    # =========================================================================

    @staticmethod
    def create_recurring_appointment(
        customer_name: str,
        service_name: str,
        frequency: str,
        time_of_day: time,
        duration_minutes: int,
        start_date: date,
        customer_id: Optional[int] = None,
        service_id: Optional[int] = None,
        staff_id: Optional[int] = None,
        staff_name: str = '',
        day_of_week: Optional[int] = None,
        end_date: Optional[date] = None,
        max_occurrences: Optional[int] = None
    ) -> RecurringAppointment:
        """Create a recurring appointment template."""
        return RecurringAppointment.objects.create(
            customer_id=customer_id,
            customer_name=customer_name,
            service_id=service_id,
            service_name=service_name,
            staff_id=staff_id,
            staff_name=staff_name,
            frequency=frequency,
            day_of_week=day_of_week,
            time=time_of_day,
            duration_minutes=duration_minutes,
            start_date=start_date,
            end_date=end_date,
            max_occurrences=max_occurrences,
            is_active=True
        )

    @staticmethod
    @transaction.atomic
    def generate_recurring_instances(
        recurring: RecurringAppointment,
        until_date: date,
        created_by_id: Optional[int] = None
    ) -> List[Appointment]:
        """Generate actual appointments from a recurring template."""
        appointments = recurring.generate_appointments(until_date)
        created = []

        for appointment in appointments:
            # Check if appointment already exists
            existing = Appointment.objects.filter(
                customer_id=recurring.customer_id,
                service_id=recurring.service_id,
                start_datetime=appointment.start_datetime
            ).exists()

            if not existing:
                appointment.created_by_id = created_by_id
                appointment.save()
                created.append(appointment)

                AppointmentHistory.log(
                    appointment,
                    'created',
                    'Created from recurring appointment',
                    performed_by_id=created_by_id
                )

        return created
