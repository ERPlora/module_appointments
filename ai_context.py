"""
AI context for the Appointments module.
Loaded into the assistant system prompt when this module's tools are active.
"""

CONTEXT = """
## Module Knowledge: Appointments

### Models

**AppointmentsSettings** (singleton per hub)
- default_duration (min, 60), min_booking_notice (min), max_advance_booking (days)
- allow_overlapping (bool), send_reminders (bool), reminder_hours_before (int)
- allow_customer_cancellation (bool), cancellation_notice_hours (int)
- calendar_start_hour (8), calendar_end_hour (20), slot_interval (min, 15)

**Schedule** + **ScheduleTimeSlot**
- Schedule: name, is_default, is_active — template for staff/service availability
- ScheduleTimeSlot: schedule (FK), day_of_week (0=Mon–6=Sun), start_time, end_time
- Unique: (schedule, day_of_week, start_time)

**BlockedTime**
- title, block_type: holiday | vacation | break | maintenance | other
- start_datetime, end_datetime, all_day (bool)
- staff (FK → accounts.LocalUser, optional — if null, applies to all)
- is_recurring (bool), recurrence_rule (str)

**Appointment**
- appointment_number (auto-generated: APT-YYYYMMDD-NNNN)
- customer (FK → customers.Customer, optional), customer_name, customer_phone, customer_email
- staff (FK → accounts.LocalUser, optional), staff_name (cached)
- service (FK → services.Service, optional), service_name (cached), service_price
- start_datetime, end_datetime (auto-set from start + duration_minutes), duration_minutes
- status: pending | confirmed | in_progress | completed | cancelled | no_show
- notes, internal_notes, booked_online (bool)
- reminder_sent (bool), cancelled_at, cancellation_reason
- Methods: confirm(), start(), complete(), cancel(reason), mark_no_show(), reschedule(new_start, new_duration)
- Class methods: get_for_date(hub_id, date), get_upcoming(hub_id, limit)

**AppointmentHistory**
- appointment (FK), action: created | confirmed | started | rescheduled | cancelled | completed | no_show | note_added
- description, performed_by (FK → accounts.LocalUser), old_value/new_value (JSON)
- Class method: log(appointment, action, description, performed_by, old_value, new_value)

**RecurringAppointment**
- customer (FK → customers.Customer), service (FK → services.Service), staff (FK → accounts.LocalUser)
- frequency: daily | weekly | biweekly | monthly
- day_of_week (for weekly/biweekly), time (TimeField), duration_minutes
- start_date, end_date (optional), max_occurrences (optional)
- Method: get_next_occurrence(after_date)

### Key flows

1. **Book appointment**: Create Appointment with customer, service, staff, start_datetime, duration_minutes; end_datetime auto-set; appointment_number auto-generated
2. **Confirm**: Call appointment.confirm() → status: pending → confirmed
3. **Start service**: Call appointment.start() → status: confirmed → in_progress
4. **Complete**: Call appointment.complete() → status: in_progress/confirmed → completed
5. **Cancel**: Call appointment.cancel(reason) → status → cancelled
6. **No-show**: Call appointment.mark_no_show() — only works if past and was pending/confirmed
7. **Reschedule**: Call appointment.reschedule(new_start_datetime, new_duration_minutes)
8. **Log change**: Call AppointmentHistory.log(appointment, action, …) after each transition

### Relationships

- Appointment.customer → customers.Customer
- Appointment.staff → accounts.LocalUser
- Appointment.service → services.Service
- BlockedTime.staff → accounts.LocalUser
"""
