# Appointments Module

Appointment scheduling and management for service-based businesses like salons, spas, clinics, and consultants.

## Features

- Calendar view with day/week/month modes
- Appointment scheduling with service duration
- Staff availability management
- Customer notifications (email/SMS)
- Booking confirmation workflow
- Recurring appointments support
- Integration with Services and Staff modules

## Installation

This module is installed automatically when activated in ERPlora Hub.

### Dependencies

- ERPlora Hub >= 1.0.0
- Optional: `services` module for service catalog
- Optional: `staff` module for staff scheduling
- Optional: `customers` module for customer management

## Configuration

Access module settings at `/m/appointments/settings/`.

### Available Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `default_duration` | integer | `60` | Default appointment duration in minutes |
| `min_booking_notice` | integer | `60` | Minimum notice time for bookings (minutes) |
| `max_advance_booking` | integer | `90` | Max days in advance for booking |
| `allow_overlapping` | boolean | `false` | Allow overlapping appointments |
| `send_reminders` | boolean | `true` | Send reminder notifications |

## Usage

### Views

| View | URL | Description |
|------|-----|-------------|
| Overview | `/m/appointments/` | Dashboard with today's appointments |
| Calendar | `/m/appointments/calendar/` | Full calendar view |
| List | `/m/appointments/appointments/` | Appointment list |
| Schedules | `/m/appointments/schedules/` | Staff availability |
| Settings | `/m/appointments/settings/` | Module configuration |

## Permissions

| Permission | Description |
|------------|-------------|
| `appointments.view_appointment` | View appointments |
| `appointments.add_appointment` | Create appointments |
| `appointments.change_appointment` | Edit appointments |
| `appointments.delete_appointment` | Cancel/delete appointments |
| `appointments.view_schedule` | View staff schedules |
| `appointments.manage_schedule` | Manage staff availability |

## Module Icon

Location: `static/icons/icon.svg`

Icon source: [React Icons - Ionicons 5](https://react-icons.github.io/react-icons/icons/io5/)

---

**Version:** 1.0.0
**Category:** services
**Author:** ERPlora Team
