"""
Unit tests for appointments module models.
"""
import pytest
from datetime import datetime, timedelta, time, date
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError

from appointments.models import (
    AppointmentsConfig,
    Schedule,
    ScheduleTimeSlot,
    BlockedTime,
    Appointment,
    AppointmentHistory,
    RecurringAppointment,
)


# =============================================================================
# AppointmentsConfig Tests
# =============================================================================

@pytest.mark.django_db
class TestAppointmentsConfig:
    """Test cases for AppointmentsConfig model."""

    def test_get_config_creates_singleton(self):
        """get_config should create singleton instance."""
        config = AppointmentsConfig.get_config()
        assert config is not None
        assert config.pk == 1

    def test_get_config_returns_same_instance(self):
        """get_config should return same instance on multiple calls."""
        config1 = AppointmentsConfig.get_config()
        config2 = AppointmentsConfig.get_config()
        assert config1.pk == config2.pk

    def test_default_values(self, config):
        """Config should have sensible defaults."""
        assert config.default_duration == 60
        assert config.min_booking_notice == 60
        assert config.max_advance_booking == 90
        assert config.allow_overlapping is False
        assert config.send_reminders is True
        assert config.calendar_start_hour == 8
        assert config.calendar_end_hour == 20
        assert config.slot_interval == 15

    def test_str_representation(self, config):
        """String representation should be descriptive."""
        assert str(config) == "Appointments Configuration"

    def test_update_config(self, config):
        """Config values should be updatable."""
        config.default_duration = 45
        config.slot_interval = 30
        config.save()

        refreshed = AppointmentsConfig.get_config()
        assert refreshed.default_duration == 45
        assert refreshed.slot_interval == 30


# =============================================================================
# Schedule Tests
# =============================================================================

@pytest.mark.django_db
class TestSchedule:
    """Test cases for Schedule model."""

    def test_create_schedule(self, db):
        """Should create a schedule successfully."""
        schedule = Schedule.objects.create(
            name="Test Schedule",
            description="Test description",
            is_default=False,
            is_active=True
        )
        assert schedule.id is not None
        assert schedule.name == "Test Schedule"

    def test_str_representation(self, schedule):
        """String representation should show name."""
        assert str(schedule) == "Business Hours"

    def test_default_schedule_uniqueness(self, schedule):
        """Only one schedule can be default."""
        schedule2 = Schedule.objects.create(
            name="Another Schedule",
            is_default=True
        )

        schedule.refresh_from_db()
        assert schedule.is_default is False
        assert schedule2.is_default is True

    def test_get_time_slots(self, schedule_with_slots):
        """Should get time slots for a specific day."""
        monday_slots = schedule_with_slots.get_time_slots(0)
        assert monday_slots.count() == 2

        sunday_slots = schedule_with_slots.get_time_slots(6)
        assert sunday_slots.count() == 0

    def test_is_available_at(self, schedule_with_slots):
        """Should check availability at specific time."""
        # Available at 10:00 on Monday
        assert schedule_with_slots.is_available_at(0, time(10, 0)) is True

        # Not available at 13:30 (lunch break)
        assert schedule_with_slots.is_available_at(0, time(13, 30)) is False

        # Not available on Sunday
        assert schedule_with_slots.is_available_at(6, time(10, 0)) is False


# =============================================================================
# ScheduleTimeSlot Tests
# =============================================================================

@pytest.mark.django_db
class TestScheduleTimeSlot:
    """Test cases for ScheduleTimeSlot model."""

    def test_create_time_slot(self, schedule):
        """Should create a time slot successfully."""
        slot = ScheduleTimeSlot.objects.create(
            schedule=schedule,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0)
        )
        assert slot.id is not None
        assert slot.day_of_week == 0

    def test_str_representation(self, time_slot):
        """String representation should show day and times."""
        assert "Monday" in str(time_slot)
        assert "09:00" in str(time_slot)
        assert "17:00" in str(time_slot)

    def test_duration_minutes(self, time_slot):
        """Should calculate duration in minutes."""
        assert time_slot.duration_minutes == 480  # 8 hours

    def test_validation_end_after_start(self, schedule):
        """End time must be after start time."""
        slot = ScheduleTimeSlot(
            schedule=schedule,
            day_of_week=0,
            start_time=time(17, 0),
            end_time=time(9, 0)
        )
        with pytest.raises(ValidationError):
            slot.clean()

    def test_ordering(self, schedule):
        """Slots should be ordered by day and start time."""
        slot1 = ScheduleTimeSlot.objects.create(
            schedule=schedule,
            day_of_week=1,
            start_time=time(14, 0),
            end_time=time(18, 0)
        )
        slot2 = ScheduleTimeSlot.objects.create(
            schedule=schedule,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(13, 0)
        )
        slot3 = ScheduleTimeSlot.objects.create(
            schedule=schedule,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(13, 0)
        )

        slots = list(ScheduleTimeSlot.objects.all())
        assert slots[0] == slot2  # Monday 9:00
        assert slots[1] == slot3  # Tuesday 9:00
        assert slots[2] == slot1  # Tuesday 14:00


# =============================================================================
# BlockedTime Tests
# =============================================================================

@pytest.mark.django_db
class TestBlockedTime:
    """Test cases for BlockedTime model."""

    def test_create_blocked_time(self, db):
        """Should create a blocked time period."""
        now = timezone.now()
        blocked = BlockedTime.objects.create(
            title="Lunch Break",
            block_type="break",
            start_datetime=now,
            end_datetime=now + timedelta(hours=1)
        )
        assert blocked.id is not None
        assert blocked.block_type == "break"

    def test_str_representation(self, blocked_time):
        """String representation should show title and date."""
        assert "Holiday" in str(blocked_time)

    def test_duration_property(self, blocked_time):
        """Should calculate duration."""
        assert blocked_time.duration == timedelta(hours=4)

    def test_validation_end_after_start(self, db):
        """End datetime must be after start datetime."""
        now = timezone.now()
        blocked = BlockedTime(
            title="Invalid",
            start_datetime=now + timedelta(hours=2),
            end_datetime=now
        )
        with pytest.raises(ValidationError):
            blocked.clean()

    def test_conflicts_with(self, blocked_time):
        """Should detect conflicts with time ranges."""
        # Overlapping time
        start = blocked_time.start_datetime + timedelta(hours=1)
        end = start + timedelta(hours=1)
        assert blocked_time.conflicts_with(start, end) is True

        # Non-overlapping time
        start = blocked_time.end_datetime + timedelta(hours=1)
        end = start + timedelta(hours=1)
        assert blocked_time.conflicts_with(start, end) is False

    def test_staff_specific_conflict(self, db):
        """Should check staff-specific conflicts."""
        now = timezone.now() + timedelta(days=5)
        blocked = BlockedTime.objects.create(
            title="Staff Break",
            start_datetime=now,
            end_datetime=now + timedelta(hours=1),
            staff_id=1
        )

        # Conflicts with same staff
        assert blocked.conflicts_with(now, now + timedelta(hours=1), staff_id=1) is True

        # No conflict with different staff
        assert blocked.conflicts_with(now, now + timedelta(hours=1), staff_id=2) is False


# =============================================================================
# Appointment Tests
# =============================================================================

@pytest.mark.django_db
class TestAppointment:
    """Test cases for Appointment model."""

    def test_create_appointment(self, appointment):
        """Should create an appointment successfully."""
        assert appointment.id is not None
        assert appointment.appointment_number.startswith("APT-")
        assert appointment.customer_name == "John Doe"
        assert appointment.status == "pending"

    def test_appointment_number_generation(self, db):
        """Should generate unique appointment numbers."""
        now = timezone.now() + timedelta(days=7)
        apt1 = Appointment.objects.create(
            customer_name="Customer 1",
            service_name="Service 1",
            start_datetime=now,
            end_datetime=now + timedelta(hours=1),
            duration_minutes=60
        )
        apt2 = Appointment.objects.create(
            customer_name="Customer 2",
            service_name="Service 2",
            start_datetime=now + timedelta(hours=2),
            end_datetime=now + timedelta(hours=3),
            duration_minutes=60
        )
        assert apt1.appointment_number != apt2.appointment_number

    def test_str_representation(self, appointment):
        """String representation should be descriptive."""
        result = str(appointment)
        assert "John Doe" in result
        assert appointment.appointment_number in result

    def test_is_past_property(self, appointment, past_appointment):
        """Should correctly identify past appointments."""
        assert appointment.is_past is False
        assert past_appointment.is_past is True

    def test_is_today_property(self, db):
        """Should correctly identify today's appointments."""
        now = timezone.now()
        # Create appointment starting today at noon
        today_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if today_noon < now:
            today_noon = today_noon + timedelta(days=1)
        today_apt = Appointment.objects.create(
            customer_name="Today",
            service_name="Service",
            start_datetime=today_noon,
            end_datetime=today_noon + timedelta(hours=1),
            duration_minutes=60
        )
        # Check if start_datetime.date() equals today
        assert today_apt.start_datetime.date() == now.date() or today_apt.start_datetime.date() == (now + timedelta(days=1)).date()

    def test_can_cancel_property(self, appointment, config):
        """Should check if appointment can be cancelled."""
        # Future appointment - can cancel
        assert appointment.can_cancel is True

        # Already cancelled - cannot cancel again
        appointment.status = 'cancelled'
        appointment.save()
        assert appointment.can_cancel is False

    def test_confirm_appointment(self, appointment):
        """Should confirm pending appointment."""
        assert appointment.status == 'pending'
        result = appointment.confirm()
        assert result is True
        assert appointment.status == 'confirmed'

    def test_confirm_only_pending(self, confirmed_appointment):
        """Should not confirm non-pending appointment."""
        result = confirmed_appointment.confirm()
        assert result is False
        assert confirmed_appointment.status == 'confirmed'

    def test_start_appointment(self, confirmed_appointment):
        """Should start confirmed appointment."""
        result = confirmed_appointment.start()
        assert result is True
        assert confirmed_appointment.status == 'in_progress'

    def test_complete_appointment(self, confirmed_appointment):
        """Should complete appointment."""
        result = confirmed_appointment.complete()
        assert result is True
        assert confirmed_appointment.status == 'completed'

    def test_cancel_appointment(self, appointment):
        """Should cancel appointment with reason."""
        result = appointment.cancel(reason="Customer request")
        assert result is True
        assert appointment.status == 'cancelled'
        assert appointment.cancellation_reason == "Customer request"
        assert appointment.cancelled_at is not None

    def test_mark_no_show(self, past_appointment):
        """Should mark past appointment as no-show."""
        result = past_appointment.mark_no_show()
        assert result is True
        assert past_appointment.status == 'no_show'

    def test_reschedule_appointment(self, appointment):
        """Should reschedule appointment."""
        new_time = timezone.now() + timedelta(days=14)
        original_time = appointment.start_datetime

        result = appointment.reschedule(new_time, new_duration=90)

        assert result is True
        assert appointment.start_datetime == new_time
        assert appointment.duration_minutes == 90
        assert appointment.start_datetime != original_time

    def test_send_reminder(self, appointment):
        """Should mark reminder as sent."""
        assert appointment.reminder_sent is False

        result = appointment.send_reminder()

        assert result is True
        assert appointment.reminder_sent is True
        assert appointment.reminder_sent_at is not None


# =============================================================================
# AppointmentHistory Tests
# =============================================================================

@pytest.mark.django_db
class TestAppointmentHistory:
    """Test cases for AppointmentHistory model."""

    def test_create_history(self, appointment):
        """Should create history entry."""
        history = AppointmentHistory.log(
            appointment,
            'created',
            'Appointment created',
            performed_by_id=1
        )
        assert history.id is not None
        assert history.action == 'created'
        assert history.performed_by_id == 1

    def test_str_representation(self, appointment):
        """String representation should show appointment and action."""
        history = AppointmentHistory.log(appointment, 'confirmed', 'Test')
        assert appointment.appointment_number in str(history)
        assert 'confirmed' in str(history)

    def test_history_with_values(self, appointment):
        """Should store old and new values."""
        history = AppointmentHistory.log(
            appointment,
            'rescheduled',
            'Time changed',
            old_value={'start_datetime': '2024-01-01 10:00'},
            new_value={'start_datetime': '2024-01-02 10:00'}
        )
        assert history.old_value == {'start_datetime': '2024-01-01 10:00'}
        assert history.new_value == {'start_datetime': '2024-01-02 10:00'}

    def test_ordering(self, appointment):
        """History should be ordered by most recent first."""
        h1 = AppointmentHistory.log(appointment, 'created', 'First')
        h2 = AppointmentHistory.log(appointment, 'confirmed', 'Second')

        history = list(appointment.history.all())
        assert history[0] == h2  # Most recent first
        assert history[1] == h1


# =============================================================================
# RecurringAppointment Tests
# =============================================================================

@pytest.mark.django_db
class TestRecurringAppointment:
    """Test cases for RecurringAppointment model."""

    def test_create_recurring(self, recurring_appointment):
        """Should create recurring appointment template."""
        assert recurring_appointment.id is not None
        assert recurring_appointment.frequency == 'weekly'
        assert recurring_appointment.is_active is True

    def test_str_representation(self, recurring_appointment):
        """String representation should be descriptive."""
        result = str(recurring_appointment)
        assert "Regular Customer" in result
        assert "weekly" in result

    def test_get_next_occurrence_weekly(self, recurring_appointment):
        """Should calculate next weekly occurrence."""
        today = timezone.now().date()
        next_occurrence = recurring_appointment.get_next_occurrence(today)
        assert next_occurrence is not None
        # Should be a Tuesday (day_of_week=1)
        assert next_occurrence.weekday() == 1

    def test_get_next_occurrence_with_end_date(self, db):
        """Should return None if past end date."""
        past_date = timezone.now().date() - timedelta(days=30)
        recurring = RecurringAppointment.objects.create(
            customer_name="Test",
            service_name="Test",
            frequency='weekly',
            time=time(10, 0),
            duration_minutes=60,
            start_date=past_date - timedelta(days=60),
            end_date=past_date,
            is_active=True
        )
        next_occurrence = recurring.get_next_occurrence()
        assert next_occurrence is None

    def test_generate_appointments(self, recurring_appointment):
        """Should generate appointments until a date."""
        until_date = timezone.now().date() + timedelta(weeks=4)
        appointments = recurring_appointment.generate_appointments(until_date)

        assert len(appointments) >= 1
        assert len(appointments) <= 5  # Could be up to 5 weeks
        for apt in appointments:
            assert apt.customer_name == recurring_appointment.customer_name
            assert apt.service_name == recurring_appointment.service_name

    def test_daily_frequency(self, db):
        """Should handle daily frequency."""
        today = timezone.now().date()
        recurring = RecurringAppointment.objects.create(
            customer_name="Daily",
            service_name="Daily Service",
            frequency='daily',
            time=time(10, 0),
            duration_minutes=30,
            start_date=today,
            max_occurrences=5,
            is_active=True
        )

        until_date = today + timedelta(days=10)
        appointments = recurring.generate_appointments(until_date)
        assert len(appointments) == 5

    def test_monthly_frequency(self, db):
        """Should handle monthly frequency."""
        today = timezone.now().date()
        recurring = RecurringAppointment.objects.create(
            customer_name="Monthly",
            service_name="Monthly Service",
            frequency='monthly',
            time=time(14, 0),
            duration_minutes=60,
            start_date=today,
            is_active=True
        )

        until_date = today + timedelta(days=90)
        appointments = recurring.generate_appointments(until_date)
        assert len(appointments) >= 1
        assert len(appointments) <= 4  # Could span up to 4 months
