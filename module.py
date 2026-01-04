"""
Appointments Module Configuration

This file defines the module metadata and navigation for the Appointments module.
Used by the @module_view decorator to automatically render navigation tabs.
"""
from django.utils.translation import gettext_lazy as _

# Module Identification
MODULE_ID = "appointments"
MODULE_NAME = _("Appointments")
MODULE_ICON = "calendar-outline"
MODULE_VERSION = "1.0.0"
MODULE_CATEGORY = "pos"

# Target Industries (business verticals this module is designed for)
MODULE_INDUSTRIES = [
    "beauty",       # Beauty & wellness (peluquerías, spas)
    "healthcare",   # Healthcare (clinics, medical)
    "fitness",      # Fitness & sports (gyms)
    "consulting",   # Professional services (consulting)
    "education",    # Education (tutoring, academies)
]

# Sidebar Menu Configuration
MENU = {
    "label": _("Appointments"),
    "icon": "calendar-outline",
    "order": 60,
    "show": True,
}

# Internal Navigation (Tabs)
NAVIGATION = [
    {
        "id": "dashboard",
        "label": _("Overview"),
        "icon": "grid-outline",
        "view": "",
    },
    {
        "id": "calendar",
        "label": _("Calendar"),
        "icon": "calendar-outline",
        "view": "calendar",
    },
    {
        "id": "appointments",
        "label": _("List"),
        "icon": "list-outline",
        "view": "appointments",
    },
    {
        "id": "schedules",
        "label": _("Schedules"),
        "icon": "time-outline",
        "view": "schedules",
    },
    {
        "id": "settings",
        "label": _("Settings"),
        "icon": "settings-outline",
        "view": "settings",
    },
]

# Module Dependencies
DEPENDENCIES = []

# Default Settings
SETTINGS = {
    "default_duration": 60,
    "min_booking_notice": 60,
    "max_advance_booking": 90,
    "allow_overlapping": False,
    "send_reminders": True,
}

# Permissions - tuple format (action_suffix, display_name)
# Results in permission codenames like "appointments.view_appointment"
PERMISSIONS = [
    ("view_appointment", _("Can view appointments")),
    ("add_appointment", _("Can add appointments")),
    ("change_appointment", _("Can change appointments")),
    ("delete_appointment", _("Can delete appointments")),
    ("confirm_appointment", _("Can confirm appointments")),
    ("cancel_appointment", _("Can cancel appointments")),
    ("complete_appointment", _("Can complete appointments")),
    ("reschedule_appointment", _("Can reschedule appointments")),
    ("view_schedule", _("Can view schedules")),
    ("manage_schedule", _("Can manage schedules")),
    ("view_blocked_time", _("Can view blocked times")),
    ("manage_blocked_time", _("Can manage blocked times")),
    ("view_recurring", _("Can view recurring appointments")),
    ("manage_recurring", _("Can manage recurring appointments")),
    ("view_settings", _("Can view settings")),
    ("change_settings", _("Can change settings")),
]

# Role-based permission assignments
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions
    "manager": [
        "view_appointment",
        "add_appointment",
        "change_appointment",
        "delete_appointment",
        "confirm_appointment",
        "cancel_appointment",
        "complete_appointment",
        "reschedule_appointment",
        "view_schedule",
        "manage_schedule",
        "view_blocked_time",
        "manage_blocked_time",
        "view_recurring",
        "manage_recurring",
        "view_settings",
    ],
    "employee": [
        "view_appointment",
        "add_appointment",
        "confirm_appointment",
        "complete_appointment",
        "view_schedule",
        "view_blocked_time",
    ],
}
