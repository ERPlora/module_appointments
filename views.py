"""
Appointments Module Views

Views for appointment management.
"""
import json
from datetime import datetime, timedelta, date, time
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.utils import timezone
from django.db.models import Q, Count

from apps.accounts.decorators import login_required
from apps.modules_runtime.decorators import module_view

from .models import (
    AppointmentsConfig,
    Schedule,
    ScheduleTimeSlot,
    BlockedTime,
    Appointment,
    AppointmentHistory,
    RecurringAppointment,
)
from .services import AppointmentService


# =============================================================================
# DASHBOARD
# =============================================================================

@login_required
@module_view("appointments", "dashboard")
def dashboard(request):
    """Dashboard with appointment overview."""
    today = timezone.now().date()

    # Today's appointments
    today_appointments = AppointmentService.get_today_appointments()

    # Upcoming appointments
    upcoming = AppointmentService.get_upcoming_appointments(limit=5)

    # Statistics
    stats = AppointmentService.get_appointment_stats()

    # Pending confirmations
    pending_count = Appointment.objects.filter(status='pending').count()

    return {
        'today_appointments': today_appointments,
        'upcoming_appointments': upcoming,
        'stats': stats,
        'pending_count': pending_count,
        'today': today,
    }


# =============================================================================
# CALENDAR
# =============================================================================

@login_required
@module_view("appointments", "calendar")
def calendar_view(request):
    """Calendar view for appointments."""
    config = AppointmentsConfig.get_config()

    return {
        'config': config,
        'calendar_start_hour': config.calendar_start_hour,
        'calendar_end_hour': config.calendar_end_hour,
    }


@login_required
@require_GET
def calendar_data(request):
    """Get calendar data for a date range (API endpoint for calendar JS)."""
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    staff_id = request.GET.get('staff_id')

    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else timezone.now().date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else start_date + timedelta(days=7)
    except (ValueError, TypeError):
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=7)

    appointments = AppointmentService.get_appointments_for_range(
        start_date, end_date,
        staff_id=int(staff_id) if staff_id else None
    )

    events = []
    for apt in appointments:
        color_map = {
            'pending': '#FFA500',
            'confirmed': '#3B82F6',
            'in_progress': '#8B5CF6',
            'completed': '#10B981',
            'cancelled': '#6B7280',
            'no_show': '#EF4444',
        }

        events.append({
            'id': apt.id,
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
        })

    return JsonResponse({'events': events})


# =============================================================================
# APPOINTMENTS LIST
# =============================================================================

@login_required
@module_view("appointments", "appointments")
def appointments_list(request):
    """List all appointments with filters."""
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')

    queryset = Appointment.objects.all()

    if search:
        queryset = queryset.filter(
            Q(customer_name__icontains=search) |
            Q(customer_phone__icontains=search) |
            Q(appointment_number__icontains=search) |
            Q(service_name__icontains=search)
        )

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            queryset = queryset.filter(start_datetime__date=filter_date)
        except ValueError:
            pass

    appointments = queryset.order_by('-start_datetime')[:50]

    return {
        'appointments': appointments,
        'search': search,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'status_choices': Appointment.STATUS_CHOICES,
    }


@login_required
def appointment_create(request):
    """Create a new appointment."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

            start_datetime = timezone.make_aware(
                datetime.strptime(data.get('start_datetime'), '%Y-%m-%dT%H:%M')
            )

            appointment, error = AppointmentService.create_appointment(
                customer_name=data.get('customer_name'),
                service_name=data.get('service_name'),
                start_datetime=start_datetime,
                duration_minutes=int(data.get('duration_minutes', 60)),
                customer_id=int(data['customer_id']) if data.get('customer_id') else None,
                customer_phone=data.get('customer_phone', ''),
                customer_email=data.get('customer_email', ''),
                staff_id=int(data['staff_id']) if data.get('staff_id') else None,
                staff_name=data.get('staff_name', ''),
                service_id=int(data['service_id']) if data.get('service_id') else None,
                service_price=Decimal(data.get('service_price', '0')),
                notes=data.get('notes', ''),
                created_by_id=request.session.get('local_user_id'),
            )

            if error:
                return JsonResponse({'success': False, 'error': error}, status=400)

            return JsonResponse({
                'success': True,
                'appointment_id': appointment.id,
                'appointment_number': appointment.appointment_number
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    config = AppointmentsConfig.get_config()

    return render(request, 'appointments/appointment_form.html', {
        'mode': 'create',
        'config': config,
    })


@login_required
def appointment_detail(request, pk):
    """View appointment details."""
    appointment = get_object_or_404(Appointment, pk=pk)
    history = appointment.history.all()[:20]

    return render(request, 'appointments/appointment_detail.html', {
        'appointment': appointment,
        'history': history,
    })


@login_required
def appointment_edit(request, pk):
    """Edit an appointment."""
    appointment = get_object_or_404(Appointment, pk=pk)

    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

            update_data = {}
            if data.get('customer_name'):
                update_data['customer_name'] = data['customer_name']
            if data.get('customer_phone'):
                update_data['customer_phone'] = data['customer_phone']
            if data.get('customer_email'):
                update_data['customer_email'] = data['customer_email']
            if data.get('notes'):
                update_data['notes'] = data['notes']
            if data.get('internal_notes'):
                update_data['internal_notes'] = data['internal_notes']

            if data.get('start_datetime'):
                update_data['start_datetime'] = timezone.make_aware(
                    datetime.strptime(data['start_datetime'], '%Y-%m-%dT%H:%M')
                )
            if data.get('duration_minutes'):
                update_data['duration_minutes'] = int(data['duration_minutes'])

            success, error = AppointmentService.update_appointment(appointment, **update_data)

            if not success:
                return JsonResponse({'success': False, 'error': error}, status=400)

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return render(request, 'appointments/appointment_form.html', {
        'mode': 'edit',
        'appointment': appointment,
    })


@login_required
@require_POST
def appointment_delete(request, pk):
    """Delete an appointment."""
    appointment = get_object_or_404(Appointment, pk=pk)

    # Log before delete
    AppointmentHistory.log(
        appointment,
        'cancelled',
        'Appointment deleted',
        performed_by_id=request.session.get('local_user_id')
    )

    appointment.delete()

    return JsonResponse({'success': True})


# =============================================================================
# APPOINTMENT ACTIONS
# =============================================================================

@login_required
@require_POST
def appointment_confirm(request, pk):
    """Confirm a pending appointment."""
    appointment = get_object_or_404(Appointment, pk=pk)
    user_id = request.session.get('local_user_id')

    success = AppointmentService.confirm_appointment(appointment, user_id)

    if success:
        return JsonResponse({'success': True, 'status': appointment.status})
    return JsonResponse({'success': False, 'error': 'Cannot confirm this appointment'}, status=400)


@login_required
@require_POST
def appointment_cancel(request, pk):
    """Cancel an appointment."""
    appointment = get_object_or_404(Appointment, pk=pk)
    user_id = request.session.get('local_user_id')

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        reason = data.get('reason', '')
    except:
        reason = ''

    success = AppointmentService.cancel_appointment(appointment, reason, user_id)

    if success:
        return JsonResponse({'success': True, 'status': appointment.status})
    return JsonResponse({'success': False, 'error': 'Cannot cancel this appointment'}, status=400)


@login_required
@require_POST
def appointment_complete(request, pk):
    """Mark appointment as completed."""
    appointment = get_object_or_404(Appointment, pk=pk)
    user_id = request.session.get('local_user_id')

    success = AppointmentService.complete_appointment(appointment, user_id)

    if success:
        return JsonResponse({'success': True, 'status': appointment.status})
    return JsonResponse({'success': False, 'error': 'Cannot complete this appointment'}, status=400)


@login_required
@require_POST
def appointment_no_show(request, pk):
    """Mark customer as no-show."""
    appointment = get_object_or_404(Appointment, pk=pk)
    user_id = request.session.get('local_user_id')

    success = AppointmentService.mark_no_show(appointment, user_id)

    if success:
        return JsonResponse({'success': True, 'status': appointment.status})
    return JsonResponse({'success': False, 'error': 'Cannot mark as no-show'}, status=400)


@login_required
@require_POST
def appointment_reschedule(request, pk):
    """Reschedule an appointment."""
    appointment = get_object_or_404(Appointment, pk=pk)
    user_id = request.session.get('local_user_id')

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

        new_datetime = timezone.make_aware(
            datetime.strptime(data.get('start_datetime'), '%Y-%m-%dT%H:%M')
        )
        new_duration = int(data['duration_minutes']) if data.get('duration_minutes') else None

        success, error = AppointmentService.reschedule_appointment(
            appointment, new_datetime, new_duration, user_id
        )

        if success:
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': error}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# =============================================================================
# AVAILABILITY
# =============================================================================

@login_required
@require_GET
def check_availability(request):
    """Check availability page."""
    return render(request, 'appointments/availability.html', {
        'config': AppointmentsConfig.get_config(),
    })


@login_required
@require_GET
def get_available_slots(request):
    """Get available time slots for a date."""
    date_str = request.GET.get('date')
    duration = int(request.GET.get('duration', 60))
    staff_id = request.GET.get('staff_id')

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid date'}, status=400)

    slots = AppointmentService.get_available_slots(
        target_date,
        duration,
        staff_id=int(staff_id) if staff_id else None
    )

    return JsonResponse({'slots': slots})


# =============================================================================
# SCHEDULES
# =============================================================================

@login_required
@module_view("appointments", "schedules")
def schedules_list(request):
    """List all schedules."""
    schedules = Schedule.objects.all().prefetch_related('time_slots')

    return {
        'schedules': schedules,
        'days_of_week': Schedule.DAYS_OF_WEEK,
    }


@login_required
def schedule_create(request):
    """Create a new schedule."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

            schedule = AppointmentService.create_schedule(
                name=data.get('name'),
                description=data.get('description', ''),
                is_default=data.get('is_default', False)
            )

            return JsonResponse({
                'success': True,
                'schedule_id': schedule.id
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return render(request, 'appointments/schedule_form.html', {
        'mode': 'create',
        'days_of_week': Schedule.DAYS_OF_WEEK,
    })


@login_required
def schedule_detail(request, pk):
    """View schedule details with time slots."""
    schedule = get_object_or_404(Schedule, pk=pk)
    time_slots = schedule.time_slots.all().order_by('day_of_week', 'start_time')

    # Group by day
    slots_by_day = {}
    for day, day_name in Schedule.DAYS_OF_WEEK:
        slots_by_day[day] = {
            'name': day_name,
            'slots': [s for s in time_slots if s.day_of_week == day]
        }

    return render(request, 'appointments/schedule_detail.html', {
        'schedule': schedule,
        'slots_by_day': slots_by_day,
        'days_of_week': Schedule.DAYS_OF_WEEK,
    })


@login_required
def schedule_edit(request, pk):
    """Edit a schedule."""
    schedule = get_object_or_404(Schedule, pk=pk)

    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

            schedule.name = data.get('name', schedule.name)
            schedule.description = data.get('description', schedule.description)
            schedule.is_default = data.get('is_default', schedule.is_default)
            schedule.is_active = data.get('is_active', schedule.is_active)
            schedule.save()

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return render(request, 'appointments/schedule_form.html', {
        'mode': 'edit',
        'schedule': schedule,
        'days_of_week': Schedule.DAYS_OF_WEEK,
    })


@login_required
@require_POST
def schedule_delete(request, pk):
    """Delete a schedule."""
    schedule = get_object_or_404(Schedule, pk=pk)
    schedule.delete()

    return JsonResponse({'success': True})


@login_required
def schedule_slots(request, pk):
    """Manage time slots for a schedule."""
    schedule = get_object_or_404(Schedule, pk=pk)
    time_slots = schedule.time_slots.all().order_by('day_of_week', 'start_time')

    return render(request, 'appointments/schedule_slots.html', {
        'schedule': schedule,
        'time_slots': time_slots,
        'days_of_week': Schedule.DAYS_OF_WEEK,
    })


@login_required
@require_POST
def add_time_slot(request, pk):
    """Add a time slot to a schedule."""
    schedule = get_object_or_404(Schedule, pk=pk)

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

        day_of_week = int(data.get('day_of_week'))
        start_time = datetime.strptime(data.get('start_time'), '%H:%M').time()
        end_time = datetime.strptime(data.get('end_time'), '%H:%M').time()

        slot, error = AppointmentService.add_time_slot(
            schedule, day_of_week, start_time, end_time
        )

        if error:
            return JsonResponse({'success': False, 'error': error}, status=400)

        return JsonResponse({
            'success': True,
            'slot_id': slot.id
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def delete_time_slot(request, slot_id):
    """Delete a time slot."""
    slot = get_object_or_404(ScheduleTimeSlot, pk=slot_id)
    AppointmentService.remove_time_slot(slot)

    return JsonResponse({'success': True})


# =============================================================================
# BLOCKED TIMES
# =============================================================================

@login_required
def blocked_times_list(request):
    """List blocked time periods."""
    blocked_times = BlockedTime.objects.filter(
        end_datetime__gte=timezone.now()
    ).order_by('start_datetime')

    return render(request, 'appointments/blocked_times.html', {
        'blocked_times': blocked_times,
        'block_types': BlockedTime.BLOCK_TYPE_CHOICES,
    })


@login_required
def blocked_time_create(request):
    """Create a blocked time period."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

            start_datetime = timezone.make_aware(
                datetime.strptime(data.get('start_datetime'), '%Y-%m-%dT%H:%M')
            )
            end_datetime = timezone.make_aware(
                datetime.strptime(data.get('end_datetime'), '%Y-%m-%dT%H:%M')
            )

            blocked, error = AppointmentService.create_blocked_time(
                title=data.get('title'),
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                block_type=data.get('block_type', 'other'),
                staff_id=int(data['staff_id']) if data.get('staff_id') else None,
                reason=data.get('reason', ''),
                all_day=data.get('all_day', False)
            )

            if error:
                return JsonResponse({'success': False, 'error': error}, status=400)

            return JsonResponse({
                'success': True,
                'blocked_id': blocked.id
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return render(request, 'appointments/blocked_time_form.html', {
        'block_types': BlockedTime.BLOCK_TYPE_CHOICES,
    })


@login_required
@require_POST
def blocked_time_delete(request, pk):
    """Delete a blocked time period."""
    blocked = get_object_or_404(BlockedTime, pk=pk)
    AppointmentService.remove_blocked_time(blocked)

    return JsonResponse({'success': True})


# =============================================================================
# RECURRING APPOINTMENTS
# =============================================================================

@login_required
def recurring_list(request):
    """List recurring appointment templates."""
    recurring = RecurringAppointment.objects.filter(is_active=True)

    return render(request, 'appointments/recurring_list.html', {
        'recurring_appointments': recurring,
        'frequencies': RecurringAppointment.FREQUENCY_CHOICES,
    })


@login_required
def recurring_create(request):
    """Create a recurring appointment template."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

            start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
            time_of_day = datetime.strptime(data.get('time'), '%H:%M').time()
            end_date = None
            if data.get('end_date'):
                end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()

            recurring = AppointmentService.create_recurring_appointment(
                customer_name=data.get('customer_name'),
                service_name=data.get('service_name'),
                frequency=data.get('frequency'),
                time_of_day=time_of_day,
                duration_minutes=int(data.get('duration_minutes', 60)),
                start_date=start_date,
                customer_id=int(data['customer_id']) if data.get('customer_id') else None,
                service_id=int(data['service_id']) if data.get('service_id') else None,
                staff_id=int(data['staff_id']) if data.get('staff_id') else None,
                staff_name=data.get('staff_name', ''),
                day_of_week=int(data['day_of_week']) if data.get('day_of_week') else None,
                end_date=end_date,
                max_occurrences=int(data['max_occurrences']) if data.get('max_occurrences') else None
            )

            return JsonResponse({
                'success': True,
                'recurring_id': recurring.id
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return render(request, 'appointments/recurring_form.html', {
        'frequencies': RecurringAppointment.FREQUENCY_CHOICES,
        'days_of_week': Schedule.DAYS_OF_WEEK,
    })


@login_required
def recurring_detail(request, pk):
    """View recurring appointment details."""
    recurring = get_object_or_404(RecurringAppointment, pk=pk)

    # Get generated appointments
    generated = Appointment.objects.filter(
        customer_id=recurring.customer_id,
        service_id=recurring.service_id,
    ).order_by('-start_datetime')[:10]

    return render(request, 'appointments/recurring_detail.html', {
        'recurring': recurring,
        'generated_appointments': generated,
    })


@login_required
@require_POST
def recurring_delete(request, pk):
    """Delete a recurring appointment template."""
    recurring = get_object_or_404(RecurringAppointment, pk=pk)
    recurring.is_active = False
    recurring.save()

    return JsonResponse({'success': True})


@login_required
@require_POST
def recurring_generate(request, pk):
    """Generate appointments from a recurring template."""
    recurring = get_object_or_404(RecurringAppointment, pk=pk)
    user_id = request.session.get('local_user_id')

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        until_date = datetime.strptime(data.get('until_date'), '%Y-%m-%d').date()

        appointments = AppointmentService.generate_recurring_instances(
            recurring, until_date, user_id
        )

        return JsonResponse({
            'success': True,
            'count': len(appointments)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# =============================================================================
# SETTINGS
# =============================================================================

@login_required
@module_view("appointments", "settings")
def settings_view(request):
    """Module settings page."""
    config = AppointmentsConfig.get_config()

    return {
        'config': config,
    }


@login_required
@require_POST
def settings_save(request):
    """Save module settings."""
    config = AppointmentsConfig.get_config()

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

        if 'default_duration' in data:
            config.default_duration = int(data['default_duration'])
        if 'min_booking_notice' in data:
            config.min_booking_notice = int(data['min_booking_notice'])
        if 'max_advance_booking' in data:
            config.max_advance_booking = int(data['max_advance_booking'])
        if 'reminder_hours_before' in data:
            config.reminder_hours_before = int(data['reminder_hours_before'])
        if 'cancellation_notice_hours' in data:
            config.cancellation_notice_hours = int(data['cancellation_notice_hours'])
        if 'calendar_start_hour' in data:
            config.calendar_start_hour = int(data['calendar_start_hour'])
        if 'calendar_end_hour' in data:
            config.calendar_end_hour = int(data['calendar_end_hour'])
        if 'slot_interval' in data:
            config.slot_interval = int(data['slot_interval'])

        config.save()

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def settings_toggle(request):
    """Toggle boolean settings."""
    config = AppointmentsConfig.get_config()

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

        field = data.get('field')
        valid_fields = [
            'allow_overlapping', 'send_reminders',
            'allow_customer_cancellation'
        ]

        if field not in valid_fields:
            return JsonResponse({'success': False, 'error': 'Invalid field'}, status=400)

        current_value = getattr(config, field)
        setattr(config, field, not current_value)
        config.save()

        return JsonResponse({
            'success': True,
            'value': getattr(config, field)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
