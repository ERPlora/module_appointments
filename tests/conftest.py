"""
Pytest configuration and fixtures for appointments module tests.
"""
import pytest
from datetime import datetime, timedelta, time, date
from decimal import Decimal
from django.utils import timezone


@pytest.fixture(autouse=True)
def disable_debug_toolbar(settings):
    """Disable debug toolbar for tests."""
    settings.DEBUG_TOOLBAR_CONFIG = {'SHOW_TOOLBAR_CALLBACK': lambda request: False}
    settings.DEBUG = False
    if hasattr(settings, 'INSTALLED_APPS'):
        settings.INSTALLED_APPS = [
            app for app in settings.INSTALLED_APPS if 'debug_toolbar' not in app
        ]
    if hasattr(settings, 'MIDDLEWARE'):
        settings.MIDDLEWARE = [
            m for m in settings.MIDDLEWARE if 'debug_toolbar' not in m
        ]


@pytest.fixture
def config(db):
    """Create default appointments configuration."""
    from appointments.models import AppointmentsConfig
    return AppointmentsConfig.get_config()


@pytest.fixture
def schedule(db):
    """Create a default schedule."""
    from appointments.models import Schedule
    return Schedule.objects.create(
        name="Business Hours",
        description="Standard business hours",
        is_default=True,
        is_active=True
    )


@pytest.fixture
def schedule_with_slots(schedule):
    """Create a schedule with time slots."""
    from appointments.models import ScheduleTimeSlot

    # Monday to Friday 9:00-13:00 and 14:00-18:00
    for day in range(5):  # Monday=0 to Friday=4
        ScheduleTimeSlot.objects.create(
            schedule=schedule,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(13, 0),
            is_active=True
        )
        ScheduleTimeSlot.objects.create(
            schedule=schedule,
            day_of_week=day,
            start_time=time(14, 0),
            end_time=time(18, 0),
            is_active=True
        )

    return schedule


@pytest.fixture
def time_slot(schedule):
    """Create a single time slot."""
    from appointments.models import ScheduleTimeSlot
    return ScheduleTimeSlot.objects.create(
        schedule=schedule,
        day_of_week=0,  # Monday
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_active=True
    )


@pytest.fixture
def appointment_data():
    """Sample appointment data."""
    future_time = timezone.now() + timedelta(days=7, hours=2)
    return {
        'customer_name': 'John Doe',
        'customer_phone': '+1234567890',
        'customer_email': 'john@example.com',
        'service_name': 'Haircut',
        'service_price': Decimal('25.00'),
        'start_datetime': future_time,
        'duration_minutes': 60,
        'staff_name': 'Jane Smith',
        'notes': 'Regular customer',
    }


@pytest.fixture
def appointment(db, appointment_data):
    """Create a sample appointment."""
    from appointments.models import Appointment

    start_dt = appointment_data['start_datetime']
    end_dt = start_dt + timedelta(minutes=appointment_data['duration_minutes'])

    return Appointment.objects.create(
        customer_name=appointment_data['customer_name'],
        customer_phone=appointment_data['customer_phone'],
        customer_email=appointment_data['customer_email'],
        service_name=appointment_data['service_name'],
        service_price=appointment_data['service_price'],
        start_datetime=start_dt,
        end_datetime=end_dt,
        duration_minutes=appointment_data['duration_minutes'],
        staff_name=appointment_data['staff_name'],
        notes=appointment_data['notes'],
        status='pending'
    )


@pytest.fixture
def confirmed_appointment(appointment):
    """Create a confirmed appointment."""
    appointment.status = 'confirmed'
    appointment.save()
    return appointment


@pytest.fixture
def past_appointment(db):
    """Create a past appointment."""
    from appointments.models import Appointment

    past_time = timezone.now() - timedelta(days=1, hours=2)

    return Appointment.objects.create(
        customer_name='Past Customer',
        service_name='Past Service',
        start_datetime=past_time,
        end_datetime=past_time + timedelta(hours=1),
        duration_minutes=60,
        status='confirmed'
    )


@pytest.fixture
def blocked_time(db):
    """Create a blocked time period."""
    from appointments.models import BlockedTime

    start = timezone.now() + timedelta(days=3)
    end = start + timedelta(hours=4)

    return BlockedTime.objects.create(
        title='Holiday',
        block_type='holiday',
        start_datetime=start,
        end_datetime=end,
        reason='National holiday'
    )


@pytest.fixture
def recurring_appointment(db):
    """Create a recurring appointment template."""
    from appointments.models import RecurringAppointment

    return RecurringAppointment.objects.create(
        customer_name='Regular Customer',
        service_name='Weekly Service',
        frequency='weekly',
        day_of_week=1,  # Tuesday
        time=time(10, 0),
        duration_minutes=60,
        start_date=timezone.now().date(),
        is_active=True
    )


@pytest.fixture
def authenticated_session():
    """Create an authenticated session dictionary."""
    return {
        'local_user_id': 1,
        'is_authenticated': True,
    }


@pytest.fixture
def client_with_session(client, authenticated_session):
    """Create a Django test client with authenticated session."""
    session = client.session
    for key, value in authenticated_session.items():
        session[key] = value
    session.save()
    return client
