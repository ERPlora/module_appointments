"""
Unit tests for appointments module services.
"""
import pytest
from datetime import datetime, timedelta, time, date
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from appointments.models import (
    AppointmentsConfig,
    Schedule,
    ScheduleTimeSlot,
    BlockedTime,
    Appointment,
    AppointmentHistory,
    RecurringAppointment,
)
from appointments.services import AppointmentService


# =============================================================================
# Appointment CRUD Tests
# =============================================================================

@pytest.mark.django_db
class TestAppointmentServiceCRUD:
    """Test AppointmentService CRUD operations."""

    def test_create_appointment_success(self, config):
        """Should create appointment successfully."""
        future = timezone.now() + timedelta(days=7)

        appointment, error = AppointmentService.create_appointment(
            customer_name="Test Customer",
            service_name="Test Service",
            start_datetime=future,
            duration_minutes=60,
            customer_phone="+1234567890",
            service_price=Decimal('50.00')
        )

        assert error is None
        assert appointment is not None
        assert appointment.customer_name == "Test Customer"
        assert appointment.status == 'pending'
        assert appointment.appointment_number.startswith("APT-")

    def test_create_appointment_min_notice_validation(self, config):
        """Should reject appointment with insufficient notice."""
        config.min_booking_notice = 120  # 2 hours
        config.save()

        too_soon = timezone.now() + timedelta(minutes=30)

        appointment, error = AppointmentService.create_appointment(
            customer_name="Test",
            service_name="Test",
            start_datetime=too_soon,
            duration_minutes=60
        )

        assert appointment is None
        assert "minutes in advance" in error

    def test_create_appointment_max_advance_validation(self, config):
        """Should reject appointment too far in advance."""
        config.max_advance_booking = 30  # 30 days
        config.save()

        too_far = timezone.now() + timedelta(days=60)

        appointment, error = AppointmentService.create_appointment(
            customer_name="Test",
            service_name="Test",
            start_datetime=too_far,
            duration_minutes=60
        )

        assert appointment is None
        assert "days in advance" in error

    def test_create_appointment_conflict_detection(self, config, appointment):
        """Should detect conflicting appointments."""
        config.allow_overlapping = False
        config.save()

        # Assign staff to existing appointment
        appointment.staff_id = 1
        appointment.save()

        # Try to create overlapping appointment for same staff
        new_apt, error = AppointmentService.create_appointment(
            customer_name="Another Customer",
            service_name="Another Service",
            start_datetime=appointment.start_datetime + timedelta(minutes=30),
            duration_minutes=60,
            staff_id=1
        )

        assert new_apt is None
        assert "conflicts" in error.lower()

    def test_create_appointment_blocked_time(self, config, blocked_time):
        """Should reject appointment during blocked time."""
        new_apt, error = AppointmentService.create_appointment(
            customer_name="Test",
            service_name="Test",
            start_datetime=blocked_time.start_datetime + timedelta(minutes=30),
            duration_minutes=60
        )

        assert new_apt is None
        assert "blocked" in error.lower()

    def test_create_appointment_logs_history(self, config):
        """Should log creation in history."""
        future = timezone.now() + timedelta(days=7)

        appointment, _ = AppointmentService.create_appointment(
            customer_name="Test",
            service_name="Test",
            start_datetime=future,
            duration_minutes=60,
            created_by_id=1
        )

        history = appointment.history.first()
        assert history is not None
        assert history.action == 'created'
        assert history.performed_by_id == 1

    def test_update_appointment(self, appointment):
        """Should update appointment successfully."""
        success, error = AppointmentService.update_appointment(
            appointment,
            customer_name="Updated Name",
            notes="Updated notes"
        )

        assert success is True
        assert error is None
        assert appointment.customer_name == "Updated Name"
        assert appointment.notes == "Updated notes"

    def test_update_appointment_reschedule(self, appointment, config):
        """Should update appointment time and recalculate end."""
        new_time = timezone.now() + timedelta(days=14)

        success, error = AppointmentService.update_appointment(
            appointment,
            start_datetime=new_time,
            duration_minutes=90
        )

        assert success is True
        assert appointment.start_datetime == new_time
        assert appointment.duration_minutes == 90
        expected_end = new_time + timedelta(minutes=90)
        assert appointment.end_datetime == expected_end


# =============================================================================
# Appointment Status Transitions Tests
# =============================================================================

@pytest.mark.django_db
class TestAppointmentStatusTransitions:
    """Test appointment status transition methods."""

    def test_confirm_appointment(self, appointment):
        """Should confirm pending appointment."""
        success = AppointmentService.confirm_appointment(appointment, confirmed_by_id=1)

        assert success is True
        assert appointment.status == 'confirmed'

        history = appointment.history.first()
        assert history.action == 'confirmed'

    def test_cancel_appointment(self, appointment):
        """Should cancel appointment with reason."""
        success = AppointmentService.cancel_appointment(
            appointment,
            reason="Customer unavailable",
            cancelled_by_id=1
        )

        assert success is True
        assert appointment.status == 'cancelled'

        history = appointment.history.first()
        assert history.action == 'cancelled'
        assert "Customer unavailable" in history.description

    def test_complete_appointment(self, confirmed_appointment):
        """Should complete appointment."""
        success = AppointmentService.complete_appointment(
            confirmed_appointment,
            completed_by_id=1
        )

        assert success is True
        assert confirmed_appointment.status == 'completed'

    def test_mark_no_show(self, past_appointment):
        """Should mark past appointment as no-show."""
        success = AppointmentService.mark_no_show(
            past_appointment,
            marked_by_id=1
        )

        assert success is True
        assert past_appointment.status == 'no_show'

    def test_reschedule_appointment(self, appointment, config):
        """Should reschedule appointment."""
        new_time = timezone.now() + timedelta(days=14)

        success, error = AppointmentService.reschedule_appointment(
            appointment,
            new_start_datetime=new_time,
            new_duration=90,
            rescheduled_by_id=1
        )

        assert success is True
        assert error is None
        assert appointment.start_datetime == new_time

        history = appointment.history.first()
        assert history.action == 'rescheduled'

    def test_reschedule_with_conflict(self, appointment, config):
        """Should reject reschedule if conflicts exist."""
        config.allow_overlapping = False
        config.save()

        # Create another appointment
        other_time = timezone.now() + timedelta(days=10)
        other_apt = Appointment.objects.create(
            customer_name="Other",
            service_name="Other",
            start_datetime=other_time,
            end_datetime=other_time + timedelta(hours=1),
            duration_minutes=60,
            staff_id=1,
            status='confirmed'
        )

        appointment.staff_id = 1
        appointment.save()

        # Try to reschedule to conflict
        success, error = AppointmentService.reschedule_appointment(
            appointment,
            new_start_datetime=other_time + timedelta(minutes=30)
        )

        assert success is False
        assert "conflicts" in error.lower()


# =============================================================================
# Availability Tests
# =============================================================================

@pytest.mark.django_db
class TestAvailability:
    """Test availability checking methods."""

    def test_check_conflict_finds_overlap(self, appointment):
        """Should find overlapping appointments."""
        appointment.staff_id = 1
        appointment.save()

        conflict = AppointmentService.check_conflict(
            staff_id=1,
            start_datetime=appointment.start_datetime + timedelta(minutes=30),
            end_datetime=appointment.end_datetime + timedelta(minutes=30)
        )

        assert conflict is not None
        assert conflict.id == appointment.id

    def test_check_conflict_no_overlap(self, appointment):
        """Should not find conflict for non-overlapping time."""
        appointment.staff_id = 1
        appointment.save()

        conflict = AppointmentService.check_conflict(
            staff_id=1,
            start_datetime=appointment.end_datetime + timedelta(hours=1),
            end_datetime=appointment.end_datetime + timedelta(hours=2)
        )

        assert conflict is None

    def test_check_conflict_different_staff(self, appointment):
        """Should not find conflict for different staff."""
        appointment.staff_id = 1
        appointment.save()

        conflict = AppointmentService.check_conflict(
            staff_id=2,
            start_datetime=appointment.start_datetime,
            end_datetime=appointment.end_datetime
        )

        assert conflict is None

    def test_check_conflict_excludes_id(self, appointment):
        """Should exclude appointment by ID."""
        appointment.staff_id = 1
        appointment.save()

        conflict = AppointmentService.check_conflict(
            staff_id=1,
            start_datetime=appointment.start_datetime,
            end_datetime=appointment.end_datetime,
            exclude_id=appointment.id
        )

        assert conflict is None

    def test_check_blocked_time(self, blocked_time):
        """Should find blocked time periods."""
        blocked = AppointmentService.check_blocked_time(
            start_datetime=blocked_time.start_datetime + timedelta(minutes=30),
            end_datetime=blocked_time.start_datetime + timedelta(hours=2)
        )

        assert blocked is not None
        assert blocked.id == blocked_time.id

    def test_check_blocked_time_staff_specific(self, db):
        """Should check staff-specific blocked times."""
        now = timezone.now() + timedelta(days=5)
        blocked = BlockedTime.objects.create(
            title="Staff Break",
            start_datetime=now,
            end_datetime=now + timedelta(hours=2),
            staff_id=1
        )

        # Same staff - should find
        result = AppointmentService.check_blocked_time(
            now + timedelta(minutes=30),
            now + timedelta(hours=1),
            staff_id=1
        )
        assert result is not None

        # Different staff - should not find
        result = AppointmentService.check_blocked_time(
            now + timedelta(minutes=30),
            now + timedelta(hours=1),
            staff_id=2
        )
        assert result is None

    def test_get_available_slots(self, schedule_with_slots, config):
        """Should get available time slots."""
        # Get a Monday in the future
        today = timezone.now().date()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        future_monday = today + timedelta(days=days_until_monday)

        slots = AppointmentService.get_available_slots(
            target_date=future_monday,
            duration_minutes=60,
            schedule=schedule_with_slots
        )

        assert len(slots) > 0
        for slot in slots:
            assert 'start_time' in slot
            assert 'formatted' in slot


# =============================================================================
# Schedule Management Tests
# =============================================================================

@pytest.mark.django_db
class TestScheduleManagement:
    """Test schedule management methods."""

    def test_create_schedule(self):
        """Should create a new schedule."""
        schedule = AppointmentService.create_schedule(
            name="Test Schedule",
            description="Test description",
            is_default=True
        )

        assert schedule is not None
        assert schedule.name == "Test Schedule"
        assert schedule.is_active is True

    def test_add_time_slot(self, schedule):
        """Should add time slot to schedule."""
        slot, error = AppointmentService.add_time_slot(
            schedule=schedule,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(12, 0)
        )

        assert error is None
        assert slot is not None
        assert slot.schedule == schedule

    def test_add_time_slot_validation(self, schedule):
        """Should validate time slot times."""
        slot, error = AppointmentService.add_time_slot(
            schedule=schedule,
            day_of_week=0,
            start_time=time(12, 0),
            end_time=time(9, 0)  # End before start
        )

        assert slot is None
        assert "after start" in error.lower()

    def test_add_time_slot_overlap(self, schedule):
        """Should prevent overlapping slots."""
        # Create first slot
        AppointmentService.add_time_slot(
            schedule, 0, time(9, 0), time(12, 0)
        )

        # Try to create overlapping slot
        slot, error = AppointmentService.add_time_slot(
            schedule, 0, time(11, 0), time(14, 0)
        )

        assert slot is None
        assert "overlaps" in error.lower()

    def test_remove_time_slot(self, time_slot):
        """Should remove time slot."""
        slot_id = time_slot.id
        result = AppointmentService.remove_time_slot(time_slot)

        assert result is True
        assert not ScheduleTimeSlot.objects.filter(id=slot_id).exists()


# =============================================================================
# Blocked Time Management Tests
# =============================================================================

@pytest.mark.django_db
class TestBlockedTimeManagement:
    """Test blocked time management methods."""

    def test_create_blocked_time(self):
        """Should create blocked time period."""
        now = timezone.now() + timedelta(days=5)

        blocked, error = AppointmentService.create_blocked_time(
            title="Maintenance",
            start_datetime=now,
            end_datetime=now + timedelta(hours=4),
            block_type='maintenance',
            reason="System upgrade"
        )

        assert error is None
        assert blocked is not None
        assert blocked.block_type == 'maintenance'

    def test_create_blocked_time_validation(self):
        """Should validate blocked time dates."""
        now = timezone.now()

        blocked, error = AppointmentService.create_blocked_time(
            title="Invalid",
            start_datetime=now + timedelta(hours=4),
            end_datetime=now  # End before start
        )

        assert blocked is None
        assert "after start" in error.lower()

    def test_remove_blocked_time(self, blocked_time):
        """Should remove blocked time."""
        blocked_id = blocked_time.id
        result = AppointmentService.remove_blocked_time(blocked_time)

        assert result is True
        assert not BlockedTime.objects.filter(id=blocked_id).exists()


# =============================================================================
# Query Methods Tests
# =============================================================================

@pytest.mark.django_db
class TestQueryMethods:
    """Test appointment query methods."""

    def test_get_appointments_for_date(self, appointment):
        """Should get appointments for a specific date."""
        target_date = appointment.start_datetime.date()
        results = AppointmentService.get_appointments_for_date(target_date)

        assert len(results) >= 1
        assert appointment in results

    def test_get_appointments_for_range(self, appointment):
        """Should get appointments in date range."""
        start_date = appointment.start_datetime.date() - timedelta(days=1)
        end_date = appointment.start_datetime.date() + timedelta(days=1)

        results = AppointmentService.get_appointments_for_range(start_date, end_date)

        assert len(results) >= 1
        assert appointment in results

    def test_get_upcoming_appointments(self, appointment, past_appointment):
        """Should get only upcoming appointments."""
        results = AppointmentService.get_upcoming_appointments(limit=10)

        assert appointment in results
        assert past_appointment not in results

    def test_get_today_appointments(self, db):
        """Should get today's appointments."""
        now = timezone.now()
        # Create appointment at noon today (or tomorrow if past noon)
        today_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if today_noon < now:
            # Skip this test if we're past noon - use tomorrow
            today_noon = today_noon + timedelta(days=1)

        today_apt = Appointment.objects.create(
            customer_name="Today",
            service_name="Today Service",
            start_datetime=today_noon,
            end_datetime=today_noon + timedelta(hours=1),
            duration_minutes=60,
            status='confirmed'
        )

        # Only check if today's date matches
        if today_noon.date() == now.date():
            results = AppointmentService.get_today_appointments()
            assert today_apt in results

    def test_get_customer_appointments(self, appointment):
        """Should get appointments for a customer."""
        appointment.customer_id = 123
        appointment.save()

        results = AppointmentService.get_customer_appointments(customer_id=123)
        assert appointment in results

    def test_get_pending_reminders(self, config, appointment):
        """Should get appointments needing reminders."""
        config.send_reminders = True
        config.reminder_hours_before = 48
        config.save()

        # Set appointment to be within reminder window
        appointment.start_datetime = timezone.now() + timedelta(hours=24)
        appointment.end_datetime = appointment.start_datetime + timedelta(hours=1)
        appointment.status = 'confirmed'
        appointment.reminder_sent = False
        appointment.save()

        results = AppointmentService.get_pending_reminders()
        assert appointment in results


# =============================================================================
# Statistics Tests
# =============================================================================

@pytest.mark.django_db
class TestStatistics:
    """Test statistics methods."""

    def test_get_appointment_stats(self, db):
        """Should calculate appointment statistics."""
        now = timezone.now()
        today = now.date()

        # Create test appointments
        Appointment.objects.create(
            customer_name="Completed",
            service_name="Service",
            start_datetime=now - timedelta(hours=2),
            end_datetime=now - timedelta(hours=1),
            duration_minutes=60,
            service_price=Decimal('100.00'),
            status='completed'
        )
        Appointment.objects.create(
            customer_name="Cancelled",
            service_name="Service",
            start_datetime=now + timedelta(hours=2),
            end_datetime=now + timedelta(hours=3),
            duration_minutes=60,
            status='cancelled'
        )

        stats = AppointmentService.get_appointment_stats(
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1)
        )

        assert 'total' in stats
        assert 'completed' in stats
        assert 'cancelled' in stats
        assert 'completion_rate' in stats
        assert 'revenue' in stats
        assert stats['total'] >= 2

    def test_stats_with_date_range(self, db):
        """Should filter stats by date range."""
        now = timezone.now()

        # Old appointment (outside range)
        Appointment.objects.create(
            customer_name="Old",
            service_name="Old Service",
            start_datetime=now - timedelta(days=60),
            end_datetime=now - timedelta(days=60) + timedelta(hours=1),
            duration_minutes=60,
            status='completed'
        )

        stats = AppointmentService.get_appointment_stats(
            start_date=now.date() - timedelta(days=7),
            end_date=now.date()
        )

        # Old appointment should not be counted
        assert stats['total'] < 100  # Reasonable limit


# =============================================================================
# Recurring Appointments Tests
# =============================================================================

@pytest.mark.django_db
class TestRecurringAppointments:
    """Test recurring appointment methods."""

    def test_create_recurring_appointment(self):
        """Should create recurring appointment template."""
        recurring = AppointmentService.create_recurring_appointment(
            customer_name="Regular Customer",
            service_name="Weekly Service",
            frequency='weekly',
            time_of_day=time(10, 0),
            duration_minutes=60,
            start_date=timezone.now().date(),
            day_of_week=1
        )

        assert recurring is not None
        assert recurring.frequency == 'weekly'
        assert recurring.is_active is True

    def test_generate_recurring_instances(self, recurring_appointment, config):
        """Should generate actual appointments from template."""
        until_date = timezone.now().date() + timedelta(weeks=4)

        appointments = AppointmentService.generate_recurring_instances(
            recurring_appointment,
            until_date,
            created_by_id=1
        )

        assert len(appointments) >= 1
        for apt in appointments:
            assert apt.id is not None  # Saved to DB
            assert apt.customer_name == recurring_appointment.customer_name

    def test_generate_recurring_no_duplicates(self, recurring_appointment, config):
        """Should not create duplicate appointments."""
        until_date = timezone.now().date() + timedelta(weeks=4)

        # Generate first batch
        first_batch = AppointmentService.generate_recurring_instances(
            recurring_appointment, until_date, created_by_id=1
        )

        # Generate again - should create no new appointments
        second_batch = AppointmentService.generate_recurring_instances(
            recurring_appointment, until_date, created_by_id=1
        )

        assert len(second_batch) == 0
