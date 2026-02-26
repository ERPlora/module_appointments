"""AI tools for the Appointments module."""
from assistant.tools import AssistantTool, register_tool


@register_tool
class ListAppointments(AssistantTool):
    name = "list_appointments"
    description = "List appointments with optional filters by date, status, or staff."
    module_id = "appointments"
    required_permission = "appointments.view_appointment"
    parameters = {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Filter by date (YYYY-MM-DD). Defaults to today."},
            "status": {"type": "string", "description": "Filter: pending, confirmed, in_progress, completed, cancelled, no_show"},
            "staff_id": {"type": "string", "description": "Filter by staff member ID"},
            "limit": {"type": "integer", "description": "Max results (default 20)"},
        },
        "required": [],
        "additionalProperties": False,
    }

    def execute(self, args, request):
        from datetime import date
        from appointments.models import Appointment
        qs = Appointment.objects.all().order_by('start_datetime')
        if args.get('date'):
            qs = qs.filter(start_datetime__date=args['date'])
        else:
            qs = qs.filter(start_datetime__date=date.today())
        if args.get('status'):
            qs = qs.filter(status=args['status'])
        if args.get('staff_id'):
            qs = qs.filter(staff_id=args['staff_id'])
        limit = args.get('limit', 20)
        return {
            "appointments": [
                {
                    "id": str(a.id),
                    "appointment_number": a.appointment_number,
                    "customer_name": a.customer_name,
                    "service_name": a.service_name,
                    "staff": str(a.staff) if a.staff else None,
                    "start": str(a.start_datetime),
                    "end": str(a.end_datetime),
                    "duration_minutes": a.duration_minutes,
                    "status": a.status,
                }
                for a in qs[:limit]
            ],
            "total": qs.count(),
        }


@register_tool
class CreateAppointment(AssistantTool):
    name = "create_appointment"
    description = "Book a new appointment for a customer."
    module_id = "appointments"
    required_permission = "appointments.change_appointment"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "customer_name": {"type": "string", "description": "Customer name"},
            "customer_phone": {"type": "string", "description": "Customer phone"},
            "customer_email": {"type": "string", "description": "Customer email"},
            "customer_id": {"type": "string", "description": "Customer ID (if existing)"},
            "service_id": {"type": "string", "description": "Service ID"},
            "staff_id": {"type": "string", "description": "Staff member ID"},
            "start_datetime": {"type": "string", "description": "Start datetime (YYYY-MM-DD HH:MM)"},
            "duration_minutes": {"type": "integer", "description": "Duration in minutes"},
            "notes": {"type": "string", "description": "Appointment notes"},
        },
        "required": ["customer_name", "start_datetime"],
        "additionalProperties": False,
    }

    def execute(self, args, request):
        from datetime import datetime, timedelta
        from appointments.models import Appointment
        start = datetime.fromisoformat(args['start_datetime'])
        duration = args.get('duration_minutes', 60)
        end = start + timedelta(minutes=duration)
        appt = Appointment.objects.create(
            customer_name=args['customer_name'],
            customer_phone=args.get('customer_phone', ''),
            customer_email=args.get('customer_email', ''),
            customer_id=args.get('customer_id'),
            service_id=args.get('service_id'),
            staff_id=args.get('staff_id'),
            start_datetime=start,
            end_datetime=end,
            duration_minutes=duration,
            notes=args.get('notes', ''),
            status='pending',
        )
        return {
            "id": str(appt.id),
            "appointment_number": appt.appointment_number,
            "start": str(appt.start_datetime),
            "created": True,
        }


@register_tool
class GetTodaySchedule(AssistantTool):
    name = "get_today_schedule"
    description = "Get today's appointment schedule summary: total appointments, by status, by staff."
    module_id = "appointments"
    required_permission = "appointments.view_appointment"
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def execute(self, args, request):
        from datetime import date
        from django.db.models import Count
        from appointments.models import Appointment
        today = Appointment.objects.filter(start_datetime__date=date.today())
        by_status = dict(today.values_list('status').annotate(count=Count('id')).values_list('status', 'count'))
        return {
            "date": str(date.today()),
            "total": today.count(),
            "by_status": by_status,
        }
