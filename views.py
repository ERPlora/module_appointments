"""Appointments views."""

import json
from datetime import datetime, timedelta

from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from apps.accounts.decorators import login_required
from apps.core.htmx import htmx_view
from apps.modules_runtime.navigation import with_module_nav

from .models import (
    AppointmentsSettings,
    Schedule,
    ScheduleTimeSlot,
    BlockedTime,
    Appointment,
    AppointmentHistory,
    RecurringAppointment,
)
from .forms import (
    AppointmentForm,
    ScheduleForm,
    ScheduleTimeSlotForm,
    BlockedTimeForm,
    RecurringAppointmentForm,
    AppointmentFilterForm,
    AppointmentsSettingsForm,
)


def _hub(request):
    return request.session.get('hub_id')


def _employee(request):
    from apps.accounts.models import LocalUser
    uid = request.session.get('local_user_id')
    if uid:
        return LocalUser.objects.filter(pk=uid).first()
    return None


def _log(appointment, action, description='', performed_by=None, old_value=None, new_value=None):
    AppointmentHistory.log(appointment, action, description, performed_by, old_value, new_value)


# =============================================================================
# Dashboard
# =============================================================================

@login_required
@with_module_nav('appointments', 'dashboard')
@htmx_view('appointments/pages/dashboard.html', 'appointments/partials/dashboard.html')
def index(request):
    return dashboard(request)


@login_required
@with_module_nav('appointments', 'dashboard')
@htmx_view('appointments/pages/dashboard.html', 'appointments/partials/dashboard.html')
def dashboard(request):
    """Dashboard with appointment overview."""
    hub = _hub(request)
    today = timezone.now().date()

    today_appointments = Appointment.get_for_date(hub, today)
    upcoming = Appointment.get_upcoming(hub, limit=5)

    all_apts = Appointment.objects.filter(hub_id=hub, is_deleted=False)
    stats = {
        'today': today_appointments.count(),
        'pending': all_apts.filter(status='pending').count(),
        'confirmed': all_apts.filter(status='confirmed', start_datetime__date=today).count(),
        'completed_today': all_apts.filter(status='completed', start_datetime__date=today).count(),
        'this_week': all_apts.filter(
            start_datetime__date__gte=today,
            start_datetime__date__lte=today + timedelta(days=7),
        ).exclude(status='cancelled').count(),
    }

    return {
        'today_appointments': today_appointments,
        'upcoming_appointments': upcoming,
        'stats': stats,
        'today': today,
    }


# =============================================================================
# Calendar
# =============================================================================

@login_required
@with_module_nav('appointments', 'calendar')
@htmx_view('appointments/pages/calendar.html', 'appointments/partials/calendar.html')
def calendar_view(request):
    """Calendar view."""
    hub = _hub(request)
    settings = AppointmentsSettings.get_settings(hub)
    return {
        'settings': settings,
        'calendar_start_hour': settings.calendar_start_hour,
        'calendar_end_hour': settings.calendar_end_hour,
    }


@login_required
@require_GET
def calendar_data(request):
    """Calendar data API for JS calendar."""
    hub = _hub(request)
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    staff_id = request.GET.get('staff')

    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else timezone.now().date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else start_date + timedelta(days=7)
    except (ValueError, TypeError):
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=7)

    appointments = Appointment.objects.filter(
        hub_id=hub, is_deleted=False,
        start_datetime__date__gte=start_date,
        start_datetime__date__lte=end_date,
    ).exclude(status='cancelled')

    if staff_id:
        appointments = appointments.filter(staff_id=staff_id)

    color_map = {
        'pending': '#FFA500',
        'confirmed': '#3B82F6',
        'in_progress': '#8B5CF6',
        'completed': '#10B981',
        'cancelled': '#6B7280',
        'no_show': '#EF4444',
    }

    events = [{
        'id': str(apt.pk),
        'title': f"{apt.customer_name} - {apt.service_name}",
        'start': apt.start_datetime.isoformat(),
        'end': apt.end_datetime.isoformat(),
        'color': color_map.get(apt.status, '#3B82F6'),
        'extendedProps': {
            'status': apt.status,
            'customer_name': apt.customer_name,
            'customer_phone': apt.customer_phone,
            'service_name': apt.service_name,
            'staff_name': apt.staff_name,
            'appointment_number': apt.appointment_number,
        }
    } for apt in appointments]

    return JsonResponse({'events': events})


# =============================================================================
# Appointments List & CRUD
# =============================================================================

@login_required
@with_module_nav('appointments', 'appointments')
@htmx_view('appointments/pages/list.html', 'appointments/partials/list.html')
def appointments_list(request):
    """List appointments with filters."""
    hub = _hub(request)
    appointments = Appointment.objects.filter(hub_id=hub, is_deleted=False)

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    date_str = request.GET.get('date', '')

    if q:
        appointments = appointments.filter(
            Q(customer_name__icontains=q) | Q(customer_phone__icontains=q) |
            Q(appointment_number__icontains=q) | Q(service_name__icontains=q)
        )
    if status:
        appointments = appointments.filter(status=status)
    if date_str:
        try:
            filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            appointments = appointments.filter(start_datetime__date=filter_date)
        except ValueError:
            pass

    appointments = appointments.order_by('-start_datetime')[:50]
    filter_form = AppointmentFilterForm(request.GET)

    return {
        'appointments': appointments,
        'filter_form': filter_form,
        'q': q,
        'status_choices': Appointment.STATUS_CHOICES,
    }


@login_required
@with_module_nav('appointments', 'appointments')
@htmx_view('appointments/pages/detail.html', 'appointments/partials/detail.html')
def appointment_detail(request, pk):
    """Appointment detail with history."""
    hub = _hub(request)
    apt = Appointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not apt:
        return JsonResponse({'error': 'Not found'}, status=404)

    history = apt.history.all()[:20]
    return {'appointment': apt, 'history': history}


@login_required
@with_module_nav('appointments', 'appointments')
@htmx_view('appointments/pages/form.html', 'appointments/partials/form.html')
def appointment_create(request):
    """Create an appointment."""
    hub = _hub(request)
    employee = _employee(request)

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            apt = form.save(commit=False)
            apt.hub_id = hub
            apt.save()
            _log(apt, 'created', 'Appointment created', performed_by=employee)
            return JsonResponse({
                'success': True,
                'id': str(apt.pk),
                'appointment_number': apt.appointment_number,
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    form = AppointmentForm()
    settings = AppointmentsSettings.get_settings(hub)
    return {'form': form, 'mode': 'create', 'settings': settings}


@login_required
@with_module_nav('appointments', 'appointments')
@htmx_view('appointments/pages/form.html', 'appointments/partials/form.html')
def appointment_edit(request, pk):
    """Edit an appointment."""
    hub = _hub(request)
    apt = Appointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not apt:
        return JsonResponse({'error': 'Not found'}, status=404)

    if request.method == 'POST':
        form = AppointmentForm(request.POST, instance=apt)
        if form.is_valid():
            form.save()
            _log(apt, 'rescheduled', 'Appointment updated', performed_by=_employee(request))
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    form = AppointmentForm(instance=apt)
    return {'form': form, 'appointment': apt, 'mode': 'edit'}


@login_required
@require_POST
def appointment_delete(request, pk):
    """Soft delete an appointment."""
    hub = _hub(request)
    apt = Appointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not apt:
        return JsonResponse({'error': 'Not found'}, status=404)

    _log(apt, 'cancelled', 'Appointment deleted', performed_by=_employee(request))
    apt.is_deleted = True
    apt.deleted_at = timezone.now()
    apt.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    return JsonResponse({'success': True})


# =============================================================================
# Appointment Actions
# =============================================================================

@login_required
@require_POST
def appointment_confirm(request, pk):
    hub = _hub(request)
    apt = Appointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not apt:
        return JsonResponse({'error': 'Not found'}, status=404)

    if apt.confirm():
        _log(apt, 'confirmed', performed_by=_employee(request))
        return JsonResponse({'success': True, 'status': apt.status})
    return JsonResponse({'error': 'Cannot confirm'}, status=400)


@login_required
@require_POST
def appointment_start(request, pk):
    hub = _hub(request)
    apt = Appointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not apt:
        return JsonResponse({'error': 'Not found'}, status=404)

    if apt.start():
        _log(apt, 'started', performed_by=_employee(request))
        return JsonResponse({'success': True, 'status': apt.status})
    return JsonResponse({'error': 'Cannot start'}, status=400)


@login_required
@require_POST
def appointment_cancel(request, pk):
    hub = _hub(request)
    apt = Appointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not apt:
        return JsonResponse({'error': 'Not found'}, status=404)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}
    reason = data.get('reason', '')

    if apt.cancel(reason):
        _log(apt, 'cancelled', reason, performed_by=_employee(request))
        return JsonResponse({'success': True, 'status': apt.status})
    return JsonResponse({'error': 'Cannot cancel'}, status=400)


@login_required
@require_POST
def appointment_complete(request, pk):
    hub = _hub(request)
    apt = Appointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not apt:
        return JsonResponse({'error': 'Not found'}, status=404)

    if apt.complete():
        _log(apt, 'completed', performed_by=_employee(request))
        return JsonResponse({'success': True, 'status': apt.status})
    return JsonResponse({'error': 'Cannot complete'}, status=400)


@login_required
@require_POST
def appointment_no_show(request, pk):
    hub = _hub(request)
    apt = Appointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not apt:
        return JsonResponse({'error': 'Not found'}, status=404)

    if apt.mark_no_show():
        _log(apt, 'no_show', performed_by=_employee(request))
        return JsonResponse({'success': True, 'status': apt.status})
    return JsonResponse({'error': 'Cannot mark as no-show'}, status=400)


@login_required
@require_POST
def appointment_reschedule(request, pk):
    hub = _hub(request)
    apt = Appointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not apt:
        return JsonResponse({'error': 'Not found'}, status=404)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = request.POST.dict()

    new_dt_str = data.get('start_datetime')
    if not new_dt_str:
        return JsonResponse({'error': 'start_datetime required'}, status=400)

    new_datetime = timezone.make_aware(datetime.strptime(new_dt_str, '%Y-%m-%dT%H:%M'))
    new_duration = int(data['duration_minutes']) if data.get('duration_minutes') else None

    old_dt = apt.start_datetime.isoformat()
    if apt.reschedule(new_datetime, new_duration):
        _log(apt, 'rescheduled', f'From {old_dt}', performed_by=_employee(request),
             old_value={'start_datetime': old_dt}, new_value={'start_datetime': new_datetime.isoformat()})
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Cannot reschedule'}, status=400)


# =============================================================================
# Availability
# =============================================================================

@login_required
@with_module_nav('appointments', 'calendar')
@htmx_view('appointments/pages/availability.html', 'appointments/partials/availability.html')
def check_availability(request):
    hub = _hub(request)
    settings = AppointmentsSettings.get_settings(hub)
    return {'settings': settings}


@login_required
@require_GET
def get_available_slots(request):
    """Get available time slots for a date."""
    hub = _hub(request)
    date_str = request.GET.get('date')
    duration = int(request.GET.get('duration', 60))
    staff_id = request.GET.get('staff')

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid date'}, status=400)

    settings = AppointmentsSettings.get_settings(hub)

    # Get default schedule
    schedule = Schedule.objects.filter(hub_id=hub, is_deleted=False, is_default=True, is_active=True).first()
    if not schedule:
        schedule = Schedule.objects.filter(hub_id=hub, is_deleted=False, is_active=True).first()

    if not schedule:
        return JsonResponse({'slots': []})

    day_of_week = target_date.weekday()
    time_slots = schedule.get_time_slots(day_of_week)

    # Get existing appointments
    existing = Appointment.objects.filter(
        hub_id=hub, is_deleted=False,
        start_datetime__date=target_date,
        status__in=['pending', 'confirmed', 'in_progress'],
    )
    if staff_id:
        existing = existing.filter(staff_id=staff_id)

    # Get blocked times
    blocked = BlockedTime.objects.filter(
        hub_id=hub, is_deleted=False,
        start_datetime__date__lte=target_date,
        end_datetime__date__gte=target_date,
    )
    if staff_id:
        blocked = blocked.filter(Q(staff_id__isnull=True) | Q(staff_id=staff_id))

    slots = []
    interval = timedelta(minutes=settings.slot_interval)
    apt_duration = timedelta(minutes=duration)

    for ts in time_slots:
        current_time = timezone.make_aware(datetime.combine(target_date, ts.start_time))
        end_time = timezone.make_aware(datetime.combine(target_date, ts.end_time))

        while current_time + apt_duration <= end_time:
            slot_end = current_time + apt_duration

            # Check conflicts
            is_available = True
            for apt in existing:
                if current_time < apt.end_datetime and slot_end > apt.start_datetime:
                    is_available = False
                    break

            if is_available:
                for bt in blocked:
                    if bt.conflicts_with(current_time, slot_end):
                        is_available = False
                        break

            if is_available:
                slots.append({
                    'start': current_time.strftime('%H:%M'),
                    'end': slot_end.strftime('%H:%M'),
                })

            current_time += interval

    return JsonResponse({'slots': slots})


# =============================================================================
# Schedules
# =============================================================================

@login_required
@with_module_nav('appointments', 'schedules')
@htmx_view('appointments/pages/schedules.html', 'appointments/partials/schedules.html')
def schedules_list(request):
    hub = _hub(request)
    schedules = Schedule.objects.filter(hub_id=hub, is_deleted=False).prefetch_related('time_slots')
    return {'schedules': schedules, 'days_of_week': Schedule.DAYS_OF_WEEK}


@login_required
@with_module_nav('appointments', 'schedules')
@htmx_view('appointments/pages/schedule_detail.html', 'appointments/partials/schedule_detail.html')
def schedule_detail(request, pk):
    hub = _hub(request)
    schedule = Schedule.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not schedule:
        return JsonResponse({'error': 'Not found'}, status=404)

    time_slots = schedule.time_slots.filter(is_deleted=False).order_by('day_of_week', 'start_time')
    slots_by_day = {}
    for day, day_name in Schedule.DAYS_OF_WEEK:
        slots_by_day[day] = {
            'name': str(day_name),
            'slots': [s for s in time_slots if s.day_of_week == day],
        }

    return {'schedule': schedule, 'slots_by_day': slots_by_day, 'days_of_week': Schedule.DAYS_OF_WEEK}


@login_required
def schedule_add(request):
    hub = _hub(request)
    if request.method == 'POST':
        form = ScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.hub_id = hub
            schedule.save()
            return JsonResponse({'success': True, 'id': str(schedule.pk), 'name': schedule.name})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    form = ScheduleForm()
    return JsonResponse({'form': 'render'})


@login_required
def schedule_edit(request, pk):
    hub = _hub(request)
    schedule = Schedule.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not schedule:
        return JsonResponse({'error': 'Not found'}, status=404)

    if request.method == 'POST':
        form = ScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    form = ScheduleForm(instance=schedule)
    return JsonResponse({'form': 'render'})


@login_required
@require_POST
def schedule_delete(request, pk):
    hub = _hub(request)
    schedule = Schedule.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not schedule:
        return JsonResponse({'error': 'Not found'}, status=404)

    schedule.is_deleted = True
    schedule.deleted_at = timezone.now()
    schedule.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def add_time_slot(request, pk):
    hub = _hub(request)
    schedule = Schedule.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not schedule:
        return JsonResponse({'error': 'Not found'}, status=404)

    form = ScheduleTimeSlotForm(request.POST)
    if form.is_valid():
        slot = form.save(commit=False)
        slot.hub_id = hub
        slot.schedule = schedule
        slot.save()
        return JsonResponse({'success': True, 'id': str(slot.pk)})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
def delete_time_slot(request, pk):
    hub = _hub(request)
    slot = ScheduleTimeSlot.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not slot:
        return JsonResponse({'error': 'Not found'}, status=404)

    slot.is_deleted = True
    slot.deleted_at = timezone.now()
    slot.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    return JsonResponse({'success': True})


# =============================================================================
# Blocked Times
# =============================================================================

@login_required
@with_module_nav('appointments', 'schedules')
@htmx_view('appointments/pages/blocked.html', 'appointments/partials/blocked.html')
def blocked_times_list(request):
    hub = _hub(request)
    blocked = BlockedTime.objects.filter(
        hub_id=hub, is_deleted=False,
        end_datetime__gte=timezone.now(),
    ).order_by('start_datetime')

    return {'blocked_times': blocked, 'block_types': BlockedTime.BLOCK_TYPE_CHOICES}


@login_required
def blocked_time_add(request):
    hub = _hub(request)
    if request.method == 'POST':
        form = BlockedTimeForm(request.POST)
        if form.is_valid():
            bt = form.save(commit=False)
            bt.hub_id = hub
            bt.save()
            return JsonResponse({'success': True, 'id': str(bt.pk)})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    form = BlockedTimeForm()
    return JsonResponse({'form': 'render'})


@login_required
@require_POST
def blocked_time_delete(request, pk):
    hub = _hub(request)
    bt = BlockedTime.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not bt:
        return JsonResponse({'error': 'Not found'}, status=404)

    bt.is_deleted = True
    bt.deleted_at = timezone.now()
    bt.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    return JsonResponse({'success': True})


# =============================================================================
# Recurring Appointments
# =============================================================================

@login_required
@with_module_nav('appointments', 'recurring')
@htmx_view('appointments/pages/recurring.html', 'appointments/partials/recurring.html')
def recurring_list(request):
    hub = _hub(request)
    recurring = RecurringAppointment.objects.filter(hub_id=hub, is_deleted=False, is_active=True)
    return {'recurring_appointments': recurring, 'frequencies': RecurringAppointment.FREQUENCY_CHOICES}


@login_required
def recurring_add(request):
    hub = _hub(request)
    if request.method == 'POST':
        form = RecurringAppointmentForm(request.POST)
        if form.is_valid():
            recurring = form.save(commit=False)
            recurring.hub_id = hub
            recurring.save()
            return JsonResponse({'success': True, 'id': str(recurring.pk)})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    form = RecurringAppointmentForm()
    return JsonResponse({'form': 'render'})


@login_required
@with_module_nav('appointments', 'recurring')
@htmx_view('appointments/pages/recurring_detail.html', 'appointments/partials/recurring_detail.html')
def recurring_detail(request, pk):
    hub = _hub(request)
    recurring = RecurringAppointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not recurring:
        return JsonResponse({'error': 'Not found'}, status=404)

    generated = Appointment.objects.filter(
        hub_id=hub, is_deleted=False,
        customer_id=recurring.customer_id,
        service_id=recurring.service_id,
    ).order_by('-start_datetime')[:10]

    return {'recurring': recurring, 'generated_appointments': generated}


@login_required
@require_POST
def recurring_delete(request, pk):
    hub = _hub(request)
    recurring = RecurringAppointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not recurring:
        return JsonResponse({'error': 'Not found'}, status=404)

    recurring.is_active = False
    recurring.save(update_fields=['is_active', 'updated_at'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def recurring_generate(request, pk):
    """Generate appointments from a recurring template."""
    hub = _hub(request)
    recurring = RecurringAppointment.objects.filter(hub_id=hub, is_deleted=False, pk=pk).first()
    if not recurring:
        return JsonResponse({'error': 'Not found'}, status=404)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = request.POST.dict()

    until_str = data.get('until_date')
    if not until_str:
        return JsonResponse({'error': 'until_date required'}, status=400)

    until_date = datetime.strptime(until_str, '%Y-%m-%d').date()
    employee = _employee(request)

    # Generate occurrences
    current_date = recurring.start_date
    count = 0
    occurrences_count = 0

    while current_date <= until_date:
        if recurring.end_date and current_date > recurring.end_date:
            break
        if recurring.max_occurrences and count >= recurring.max_occurrences:
            break

        start_dt = timezone.make_aware(datetime.combine(current_date, recurring.time))

        # Check no duplicate
        exists = Appointment.objects.filter(
            hub_id=hub, is_deleted=False,
            start_datetime=start_dt,
            customer_id=recurring.customer_id,
            service_id=recurring.service_id,
        ).exists()

        if not exists:
            apt = Appointment.objects.create(
                hub_id=hub,
                customer=recurring.customer,
                customer_name=recurring.customer_name,
                service=recurring.service,
                service_name=recurring.service_name,
                staff=recurring.staff,
                staff_name=recurring.staff_name,
                start_datetime=start_dt,
                duration_minutes=recurring.duration_minutes,
                status='pending',
            )
            _log(apt, 'created', f'Generated from recurring #{recurring.pk}', performed_by=employee)
            occurrences_count += 1

        count += 1

        if recurring.frequency == 'daily':
            current_date += timedelta(days=1)
        elif recurring.frequency == 'weekly':
            current_date += timedelta(weeks=1)
        elif recurring.frequency == 'biweekly':
            current_date += timedelta(weeks=2)
        elif recurring.frequency == 'monthly':
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

    return JsonResponse({'success': True, 'count': occurrences_count})


# =============================================================================
# Settings
# =============================================================================

@login_required
@with_module_nav('appointments', 'settings')
@htmx_view('appointments/pages/settings.html', 'appointments/partials/settings.html')
def settings(request):
    hub = _hub(request)
    s = AppointmentsSettings.get_settings(hub)
    form = AppointmentsSettingsForm(instance=s)
    return {'settings': s, 'form': form}


@login_required
@require_POST
def settings_save(request):
    hub = _hub(request)
    s = AppointmentsSettings.get_settings(hub)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = request.POST.dict()

    int_fields = [
        'default_duration', 'min_booking_notice', 'max_advance_booking',
        'reminder_hours_before', 'cancellation_notice_hours',
        'calendar_start_hour', 'calendar_end_hour', 'slot_interval',
    ]
    for field in int_fields:
        if field in data:
            setattr(s, field, int(data[field]))

    s.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
def settings_toggle(request):
    hub = _hub(request)
    s = AppointmentsSettings.get_settings(hub)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = request.POST.dict()

    field = data.get('field', '')
    toggleable = ['allow_overlapping', 'send_reminders', 'allow_customer_cancellation']

    if field not in toggleable:
        return JsonResponse({'error': 'Invalid field'}, status=400)

    setattr(s, field, not getattr(s, field))
    s.save()
    return JsonResponse({'success': True, 'value': getattr(s, field)})


@login_required
@require_POST
def settings_input(request):
    hub = _hub(request)
    s = AppointmentsSettings.get_settings(hub)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = request.POST.dict()

    field = data.get('field', '')
    value = data.get('value', '')

    int_fields = [
        'default_duration', 'min_booking_notice', 'max_advance_booking',
        'reminder_hours_before', 'cancellation_notice_hours',
        'calendar_start_hour', 'calendar_end_hour', 'slot_interval',
    ]

    if field in int_fields:
        setattr(s, field, int(value))
    else:
        return JsonResponse({'error': 'Invalid field'}, status=400)

    s.save()
    return JsonResponse({'success': True, 'value': getattr(s, field)})


@login_required
@require_POST
def settings_reset(request):
    hub = _hub(request)
    s = AppointmentsSettings.get_settings(hub)

    s.default_duration = 60
    s.min_booking_notice = 60
    s.max_advance_booking = 90
    s.allow_overlapping = False
    s.send_reminders = True
    s.reminder_hours_before = 24
    s.allow_customer_cancellation = True
    s.cancellation_notice_hours = 24
    s.calendar_start_hour = 8
    s.calendar_end_hour = 20
    s.slot_interval = 15
    s.save()

    return JsonResponse({'success': True})
