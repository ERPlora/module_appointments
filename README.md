# Appointments

## Overview

| Property | Value |
|----------|-------|
| **Module ID** | `appointments` |
| **Version** | `1.0.0` |
| **Dependencies** | `customers`, `services` |

## Dependencies

This module requires the following modules to be installed:

- `customers`
- `services`

## Models

### `AppointmentsSettings`

Per-hub appointments configuration.

| Field | Type | Details |
|-------|------|---------|
| `default_duration` | PositiveIntegerField |  |
| `min_booking_notice` | PositiveIntegerField |  |
| `max_advance_booking` | PositiveIntegerField |  |
| `allow_overlapping` | BooleanField |  |
| `send_reminders` | BooleanField |  |
| `reminder_hours_before` | PositiveIntegerField |  |
| `allow_customer_cancellation` | BooleanField |  |
| `cancellation_notice_hours` | PositiveIntegerField |  |
| `calendar_start_hour` | PositiveIntegerField |  |
| `calendar_end_hour` | PositiveIntegerField |  |
| `slot_interval` | PositiveIntegerField |  |

**Methods:**

- `get_settings()`

### `Schedule`

Working schedule template for staff/service availability.

| Field | Type | Details |
|-------|------|---------|
| `name` | CharField | max_length=100 |
| `description` | TextField | optional |
| `is_default` | BooleanField |  |
| `is_active` | BooleanField |  |

**Methods:**

- `get_time_slots()`
- `is_available_at()`

### `ScheduleTimeSlot`

Time slot within a schedule.

| Field | Type | Details |
|-------|------|---------|
| `schedule` | ForeignKey | → `appointments.Schedule`, on_delete=CASCADE |
| `day_of_week` | PositiveSmallIntegerField | choices: 0, 1, 2, 3, 4, 5, ... |
| `start_time` | TimeField |  |
| `end_time` | TimeField |  |
| `is_active` | BooleanField |  |

**Properties:**

- `duration_minutes`

### `BlockedTime`

Blocked time periods (holidays, breaks, vacations).

| Field | Type | Details |
|-------|------|---------|
| `title` | CharField | max_length=200 |
| `block_type` | CharField | max_length=20, choices: holiday, vacation, break, maintenance, other |
| `start_datetime` | DateTimeField |  |
| `end_datetime` | DateTimeField |  |
| `all_day` | BooleanField |  |
| `staff` | ForeignKey | → `accounts.LocalUser`, on_delete=SET_NULL, optional |
| `reason` | TextField | optional |
| `is_recurring` | BooleanField |  |
| `recurrence_rule` | CharField | max_length=200, optional |

**Methods:**

- `conflicts_with()`

**Properties:**

- `duration`

### `Appointment`

An appointment/booking.

| Field | Type | Details |
|-------|------|---------|
| `appointment_number` | CharField | max_length=20, optional |
| `customer` | ForeignKey | → `customers.Customer`, on_delete=SET_NULL, optional |
| `customer_name` | CharField | max_length=200 |
| `customer_phone` | CharField | max_length=50, optional |
| `customer_email` | EmailField | max_length=254, optional |
| `staff` | ForeignKey | → `accounts.LocalUser`, on_delete=SET_NULL, optional |
| `staff_name` | CharField | max_length=200, optional |
| `service` | ForeignKey | → `services.Service`, on_delete=SET_NULL, optional |
| `service_name` | CharField | max_length=200 |
| `service_price` | DecimalField |  |
| `start_datetime` | DateTimeField |  |
| `end_datetime` | DateTimeField |  |
| `duration_minutes` | PositiveIntegerField |  |
| `status` | CharField | max_length=20, choices: pending, confirmed, in_progress, completed, cancelled, no_show |
| `notes` | TextField | optional |
| `internal_notes` | TextField | optional |
| `reminder_sent` | BooleanField |  |
| `reminder_sent_at` | DateTimeField | optional |
| `booked_online` | BooleanField |  |
| `cancelled_at` | DateTimeField | optional |
| `cancellation_reason` | TextField | optional |

**Methods:**

- `confirm()`
- `start()`
- `complete()`
- `cancel()`
- `mark_no_show()`
- `reschedule()`
- `get_for_date()`
- `get_upcoming()`

**Properties:**

- `is_past`
- `is_today`
- `can_cancel`
- `can_start`
- `can_confirm`
- `can_complete`
- `status_class`

### `AppointmentHistory`

Audit log for appointment changes.

| Field | Type | Details |
|-------|------|---------|
| `appointment` | ForeignKey | → `appointments.Appointment`, on_delete=CASCADE |
| `action` | CharField | max_length=20, choices: created, confirmed, started, rescheduled, cancelled, completed, ... |
| `description` | TextField | optional |
| `performed_by` | ForeignKey | → `accounts.LocalUser`, on_delete=SET_NULL, optional |
| `old_value` | JSONField | optional |
| `new_value` | JSONField | optional |

**Methods:**

- `log()`

### `RecurringAppointment`

Template for recurring appointments.

| Field | Type | Details |
|-------|------|---------|
| `customer` | ForeignKey | → `customers.Customer`, on_delete=SET_NULL, optional |
| `customer_name` | CharField | max_length=200 |
| `service` | ForeignKey | → `services.Service`, on_delete=SET_NULL, optional |
| `service_name` | CharField | max_length=200 |
| `staff` | ForeignKey | → `accounts.LocalUser`, on_delete=SET_NULL, optional |
| `staff_name` | CharField | max_length=200, optional |
| `frequency` | CharField | max_length=20, choices: daily, weekly, biweekly, monthly |
| `day_of_week` | PositiveSmallIntegerField | choices: 0, 1, 2, 3, 4, 5, ..., optional |
| `time` | TimeField |  |
| `duration_minutes` | PositiveIntegerField |  |
| `start_date` | DateField |  |
| `end_date` | DateField | optional |
| `max_occurrences` | PositiveIntegerField | optional |
| `is_active` | BooleanField |  |

**Methods:**

- `get_next_occurrence()`

## Cross-Module Relationships

| From | Field | To | on_delete | Nullable |
|------|-------|----|-----------|----------|
| `ScheduleTimeSlot` | `schedule` | `appointments.Schedule` | CASCADE | No |
| `BlockedTime` | `staff` | `accounts.LocalUser` | SET_NULL | Yes |
| `Appointment` | `customer` | `customers.Customer` | SET_NULL | Yes |
| `Appointment` | `staff` | `accounts.LocalUser` | SET_NULL | Yes |
| `Appointment` | `service` | `services.Service` | SET_NULL | Yes |
| `AppointmentHistory` | `appointment` | `appointments.Appointment` | CASCADE | No |
| `AppointmentHistory` | `performed_by` | `accounts.LocalUser` | SET_NULL | Yes |
| `RecurringAppointment` | `customer` | `customers.Customer` | SET_NULL | Yes |
| `RecurringAppointment` | `service` | `services.Service` | SET_NULL | Yes |
| `RecurringAppointment` | `staff` | `accounts.LocalUser` | SET_NULL | Yes |

## URL Endpoints

Base path: `/m/appointments/`

| Path | Name | Method |
|------|------|--------|
| `(root)` | `index` | GET |
| `appointments/` | `appointments` | GET |
| `dashboard/` | `dashboard` | GET |
| `calendar/` | `calendar` | GET |
| `calendar/data/` | `calendar_data` | GET |
| `list/` | `list` | GET |
| `create/` | `create` | GET/POST |
| `<uuid:pk>/` | `detail` | GET |
| `<uuid:pk>/edit/` | `edit` | GET |
| `<uuid:pk>/delete/` | `delete` | GET/POST |
| `<uuid:pk>/confirm/` | `confirm` | GET |
| `<uuid:pk>/start/` | `start` | GET |
| `<uuid:pk>/cancel/` | `cancel` | GET |
| `<uuid:pk>/complete/` | `complete` | GET |
| `<uuid:pk>/no-show/` | `no_show` | GET |
| `<uuid:pk>/reschedule/` | `reschedule` | GET |
| `availability/` | `availability` | GET |
| `availability/slots/` | `available_slots` | GET |
| `schedules/` | `schedules` | GET |
| `schedules/add/` | `schedule_add` | GET/POST |
| `schedules/<uuid:pk>/` | `schedule_detail` | GET |
| `schedules/<uuid:pk>/edit/` | `schedule_edit` | GET |
| `schedules/<uuid:pk>/delete/` | `schedule_delete` | GET/POST |
| `schedules/<uuid:pk>/slots/add/` | `add_time_slot` | GET/POST |
| `schedules/slots/<uuid:pk>/delete/` | `delete_time_slot` | GET/POST |
| `blocked/` | `blocked_list` | GET |
| `blocked/add/` | `blocked_add` | GET/POST |
| `blocked/<uuid:pk>/delete/` | `blocked_delete` | GET/POST |
| `recurring/` | `recurring_list` | GET |
| `recurring/add/` | `recurring_add` | GET/POST |
| `recurring/<uuid:pk>/` | `recurring_detail` | GET |
| `recurring/<uuid:pk>/delete/` | `recurring_delete` | GET/POST |
| `recurring/<uuid:pk>/generate/` | `recurring_generate` | GET |
| `settings/` | `settings` | GET |
| `settings/save/` | `settings_save` | GET/POST |
| `settings/toggle/` | `settings_toggle` | GET |
| `settings/input/` | `settings_input` | GET |
| `settings/reset/` | `settings_reset` | GET |

## Permissions

| Permission | Description |
|------------|-------------|
| `appointments.manage_settings` | Manage Settings |

**Role assignments:**

- **admin**: All permissions
- **manager**: 
- **employee**: 

## Navigation

| View | Icon | ID | Fullpage |
|------|------|----|----------|
| Overview | `grid-outline` | `dashboard` | No |
| Calendar | `calendar-outline` | `calendar` | No |
| List | `list-outline` | `appointments` | No |
| Schedules | `time-outline` | `schedules` | No |
| Recurring | `repeat-outline` | `recurring` | No |
| Settings | `settings-outline` | `settings` | No |

## AI Tools

Tools available for the AI assistant:

### `list_appointments`

List appointments with optional filters by date, status, or staff.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `date` | string | No | Filter by date (YYYY-MM-DD). Defaults to today. |
| `status` | string | No | Filter: pending, confirmed, in_progress, completed, cancelled, no_show |
| `staff_id` | string | No | Filter by staff member ID |
| `limit` | integer | No | Max results (default 20) |

### `create_appointment`

Book a new appointment for a customer.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `customer_name` | string | Yes | Customer name |
| `customer_phone` | string | No | Customer phone |
| `customer_email` | string | No | Customer email |
| `customer_id` | string | No | Customer ID (if existing) |
| `service_id` | string | No | Service ID |
| `staff_id` | string | No | Staff member ID |
| `start_datetime` | string | Yes | Start datetime (YYYY-MM-DD HH:MM) |
| `duration_minutes` | integer | No | Duration in minutes |
| `notes` | string | No | Appointment notes |

### `get_today_schedule`

Get today's appointment schedule summary: total appointments, by status, by staff.

## File Structure

```
CHANGELOG.md
README.md
TODO.md
__init__.py
ai_tools.py
apps.py
forms.py
locale/
  es/
    LC_MESSAGES/
      django.po
migrations/
  0001_initial.py
  __init__.py
models.py
module.py
static/
  icons/
    ion/
templates/
  appointments/
    pages/
      availability.html
      blocked.html
      calendar.html
      dashboard.html
      detail.html
      form.html
      list.html
      recurring.html
      recurring_detail.html
      schedule_detail.html
      schedules.html
      settings.html
    partials/
      availability.html
      blocked.html
      calendar.html
      dashboard.html
      detail.html
      form.html
      list.html
      recurring.html
      recurring_detail.html
      schedule_detail.html
      schedules.html
      settings.html
tests/
  __init__.py
  conftest.py
  test_models.py
  test_services.py
  test_views.py
urls.py
views.py
```
