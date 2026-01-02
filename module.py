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
MODULE_CATEGORY = "pos"  # Changed from "services" to valid category

# Target Industries (business verticals this module is designed for)
MODULE_INDUSTRIES = [
    "salon",        # Beauty & wellness (peluquerías, spas)
    "healthcare",   # Healthcare (clinics, medical)
    "fitness",      # Fitness & sports (gyms)
    "professional", # Professional services (consulting)
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

# Permissions
PERMISSIONS = [
    "appointments.view_appointment",
    "appointments.add_appointment",
    "appointments.change_appointment",
    "appointments.delete_appointment",
    "appointments.view_schedule",
    "appointments.manage_schedule",
]
