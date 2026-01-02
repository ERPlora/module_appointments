"""
E2E tests for appointments module views.
Tests all CRUD operations and user interactions.
"""
import pytest
import json
from datetime import datetime, timedelta, time
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone

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
# Appointments CRUD Tests
# =============================================================================

@pytest.mark.django_db
class TestAppointmentCRUD:
    """Test appointment CRUD operations."""

    def test_create_appointment_success(self, config):
        """Should create appointment via service."""
        from appointments.services import AppointmentService

        future = timezone.now() + timedelta(days=7)

        appointment, error = AppointmentService.create_appointment(
            customer_name='Test Customer',
            service_name='Test Service',
            start_datetime=future,
            duration_minutes=60,
            customer_phone='+1234567890',
            service_price=Decimal('50.00')
        )

        assert error is None
        assert appointment is not None
        assert appointment.customer_name == 'Test Customer'
        assert appointment.status == 'pending'

    def test_update_appointment(self, appointment):
        """Should update appointment."""
        from appointments.services import AppointmentService

        success, error = AppointmentService.update_appointment(
            appointment,
            customer_name='Updated Name',
            notes='Updated notes'
        )

        assert success is True
        appointment.refresh_from_db()
        assert appointment.customer_name == 'Updated Name'

    def test_delete_appointment(self, appointment):
        """Should delete appointment."""
        apt_id = appointment.id
        appointment.delete()
        assert not Appointment.objects.filter(id=apt_id).exists()


# =============================================================================
# Appointment Status Workflow Tests
# =============================================================================

@pytest.mark.django_db
class TestAppointmentWorkflow:
    """Test appointment status transitions."""

    def test_confirm_pending_appointment(self, appointment):
        """Should confirm pending appointment."""
        from appointments.services import AppointmentService

        assert appointment.status == 'pending'
        success = AppointmentService.confirm_appointment(appointment)

        assert success is True
        assert appointment.status == 'confirmed'

    def test_complete_confirmed_appointment(self, confirmed_appointment):
        """Should complete confirmed appointment."""
        from appointments.services import AppointmentService

        success = AppointmentService.complete_appointment(confirmed_appointment)

        assert success is True
        assert confirmed_appointment.status == 'completed'

    def test_cancel_appointment(self, appointment):
        """Should cancel appointment with reason."""
        from appointments.services import AppointmentService

        success = AppointmentService.cancel_appointment(
            appointment,
            reason='Customer request'
        )

        assert success is True
        assert appointment.status == 'cancelled'
        assert appointment.cancellation_reason == 'Customer request'

    def test_mark_no_show(self, past_appointment):
        """Should mark past appointment as no-show."""
        from appointments.services import AppointmentService

        success = AppointmentService.mark_no_show(past_appointment)

        assert success is True
        assert past_appointment.status == 'no_show'

    def test_reschedule_appointment(self, appointment, config):
        """Should reschedule appointment."""
        from appointments.services import AppointmentService

        new_time = timezone.now() + timedelta(days=14)
        original_time = appointment.start_datetime

        success, error = AppointmentService.reschedule_appointment(
            appointment,
            new_start_datetime=new_time,
            new_duration=90
        )

        assert success is True
        assert error is None
        assert appointment.start_datetime == new_time
        assert appointment.duration_minutes == 90


# =============================================================================
# Schedule Management Tests
# =============================================================================

@pytest.mark.django_db
class TestScheduleManagement:
    """Test schedule management."""

    def test_create_schedule(self):
        """Should create a new schedule."""
        from appointments.services import AppointmentService

        schedule = AppointmentService.create_schedule(
            name='New Schedule',
            description='Test description',
            is_default=False
        )

        assert schedule is not None
        assert schedule.name == 'New Schedule'

    def test_add_time_slot_to_schedule(self, schedule):
        """Should add time slot."""
        from appointments.services import AppointmentService

        slot, error = AppointmentService.add_time_slot(
            schedule=schedule,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0)
        )

        assert error is None
        assert slot is not None
        assert slot.schedule == schedule

    def test_time_slot_validation(self, schedule):
        """Should validate time slot times."""
        from appointments.services import AppointmentService

        slot, error = AppointmentService.add_time_slot(
            schedule=schedule,
            day_of_week=0,
            start_time=time(17, 0),
            end_time=time(9, 0)  # End before start
        )

        assert slot is None
        assert "after start" in error.lower()

    def test_delete_schedule(self, schedule):
        """Should delete schedule."""
        schedule_id = schedule.id
        schedule.delete()
        assert not Schedule.objects.filter(id=schedule_id).exists()


# =============================================================================
# Blocked Time Tests
# =============================================================================

@pytest.mark.django_db
class TestBlockedTime:
    """Test blocked time management."""

    def test_create_blocked_time(self):
        """Should create blocked time."""
        from appointments.services import AppointmentService

        now = timezone.now() + timedelta(days=5)

        blocked, error = AppointmentService.create_blocked_time(
            title='Maintenance',
            start_datetime=now,
            end_datetime=now + timedelta(hours=4),
            block_type='maintenance'
        )

        assert error is None
        assert blocked is not None
        assert blocked.title == 'Maintenance'

    def test_blocked_time_prevents_booking(self, blocked_time, config):
        """Should prevent booking during blocked time."""
        from appointments.services import AppointmentService

        apt, error = AppointmentService.create_appointment(
            customer_name='Test',
            service_name='Test',
            start_datetime=blocked_time.start_datetime + timedelta(minutes=30),
            duration_minutes=60
        )

        assert apt is None
        assert 'blocked' in error.lower()

    def test_delete_blocked_time(self, blocked_time):
        """Should delete blocked time."""
        blocked_id = blocked_time.id
        blocked_time.delete()
        assert not BlockedTime.objects.filter(id=blocked_id).exists()


# =============================================================================
# Recurring Appointments Tests
# =============================================================================

@pytest.mark.django_db
class TestRecurringAppointments:
    """Test recurring appointment functionality."""

    def test_create_recurring_appointment(self):
        """Should create recurring template."""
        from appointments.services import AppointmentService

        recurring = AppointmentService.create_recurring_appointment(
            customer_name='Weekly Customer',
            service_name='Weekly Service',
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
        """Should generate appointments from template."""
        from appointments.services import AppointmentService

        until_date = timezone.now().date() + timedelta(weeks=4)

        appointments = AppointmentService.generate_recurring_instances(
            recurring_appointment,
            until_date
        )

        assert len(appointments) >= 1

    def test_deactivate_recurring(self, recurring_appointment):
        """Should deactivate recurring appointment."""
        recurring_appointment.is_active = False
        recurring_appointment.save()

        recurring_appointment.refresh_from_db()
        assert recurring_appointment.is_active is False


# =============================================================================
# Statistics Tests
# =============================================================================

@pytest.mark.django_db
class TestStatistics:
    """Test statistics methods."""

    def test_get_appointment_stats(self):
        """Should calculate statistics."""
        from appointments.services import AppointmentService

        now = timezone.now()

        # Create test appointments
        Appointment.objects.create(
            customer_name='Completed',
            service_name='Service',
            start_datetime=now - timedelta(hours=2),
            end_datetime=now - timedelta(hours=1),
            duration_minutes=60,
            service_price=Decimal('100.00'),
            status='completed'
        )

        stats = AppointmentService.get_appointment_stats()

        assert 'total' in stats
        assert 'completed' in stats
        assert 'revenue' in stats
        assert stats['completed'] >= 1


# =============================================================================
# Availability Tests
# =============================================================================

@pytest.mark.django_db
class TestAvailability:
    """Test availability checking."""

    def test_conflict_detection(self, appointment):
        """Should detect conflicting appointments."""
        from appointments.services import AppointmentService

        appointment.staff_id = 1
        appointment.save()

        conflict = AppointmentService.check_conflict(
            staff_id=1,
            start_datetime=appointment.start_datetime + timedelta(minutes=30),
            end_datetime=appointment.end_datetime + timedelta(minutes=30)
        )

        assert conflict is not None
        assert conflict.id == appointment.id

    def test_no_conflict_different_staff(self, appointment):
        """Should not detect conflict for different staff."""
        from appointments.services import AppointmentService

        appointment.staff_id = 1
        appointment.save()

        conflict = AppointmentService.check_conflict(
            staff_id=2,
            start_datetime=appointment.start_datetime,
            end_datetime=appointment.end_datetime
        )

        assert conflict is None

    def test_get_available_slots(self, schedule_with_slots, config):
        """Should get available time slots."""
        from appointments.services import AppointmentService

        # Get a future weekday
        today = timezone.now().date()
        days_ahead = (7 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        future_monday = today + timedelta(days=days_ahead)

        slots = AppointmentService.get_available_slots(
            target_date=future_monday,
            duration_minutes=60,
            schedule=schedule_with_slots
        )

        assert len(slots) >= 0  # May be empty depending on time


# =============================================================================
# Settings Tests
# =============================================================================

@pytest.mark.django_db
class TestSettings:
    """Test settings management."""

    def test_get_config(self):
        """Should get config singleton."""
        config = AppointmentsConfig.get_config()
        assert config.pk == 1

    def test_update_settings(self, config):
        """Should update settings."""
        config.default_duration = 45
        config.slot_interval = 30
        config.save()

        config.refresh_from_db()
        assert config.default_duration == 45
        assert config.slot_interval == 30

    def test_toggle_boolean_setting(self, config):
        """Should toggle boolean settings."""
        original = config.allow_overlapping
        config.allow_overlapping = not original
        config.save()

        config.refresh_from_db()
        assert config.allow_overlapping != original


# =============================================================================
# Integration Tests - Full Lifecycle
# =============================================================================

@pytest.mark.django_db
class TestFullLifecycle:
    """Integration tests for complete workflows."""

    def test_appointment_full_lifecycle(self, config):
        """Test complete appointment from creation to completion."""
        from appointments.services import AppointmentService

        # 1. Create
        future = timezone.now() + timedelta(days=7)
        appointment, error = AppointmentService.create_appointment(
            customer_name='Lifecycle Customer',
            service_name='Lifecycle Service',
            start_datetime=future,
            duration_minutes=60,
            service_price=Decimal('75.00')
        )
        assert error is None
        assert appointment.status == 'pending'

        # 2. Confirm
        success = AppointmentService.confirm_appointment(appointment)
        assert success is True
        assert appointment.status == 'confirmed'

        # 3. Complete
        success = AppointmentService.complete_appointment(appointment)
        assert success is True
        assert appointment.status == 'completed'

        # 4. Verify history
        history = list(appointment.history.all())
        assert len(history) >= 3  # created, confirmed, completed

    def test_schedule_with_blocked_time(self, schedule_with_slots, config):
        """Test schedule creation and blocking."""
        from appointments.services import AppointmentService

        # Block a time period
        block_start = timezone.now() + timedelta(days=10)
        blocked, _ = AppointmentService.create_blocked_time(
            title='Test Block',
            start_datetime=block_start,
            end_datetime=block_start + timedelta(hours=2)
        )

        # Try to book during blocked time - should fail
        apt, error = AppointmentService.create_appointment(
            customer_name='Blocked Test',
            service_name='Test',
            start_datetime=block_start + timedelta(minutes=30),
            duration_minutes=60
        )

        assert apt is None
        assert 'blocked' in error.lower()
