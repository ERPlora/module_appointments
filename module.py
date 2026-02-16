from django.utils.translation import gettext_lazy as _

MODULE_ID = 'appointments'
MODULE_NAME = _('Appointments')
MODULE_VERSION = '1.0.0'

MENU = {
    'label': _('Appointments'),
    'icon': 'calendar-outline',
    'order': 60,
}

NAVIGATION = [
    {'id': 'dashboard', 'label': _('Overview'), 'icon': 'grid-outline', 'view': ''},
    {'id': 'calendar', 'label': _('Calendar'), 'icon': 'calendar-outline', 'view': 'calendar'},
    {'id': 'appointments', 'label': _('List'), 'icon': 'list-outline', 'view': 'list'},
    {'id': 'schedules', 'label': _('Schedules'), 'icon': 'time-outline', 'view': 'schedules'},
    {'id': 'recurring', 'label': _('Recurring'), 'icon': 'repeat-outline', 'view': 'recurring'},
    {'id': 'settings', 'label': _('Settings'), 'icon': 'settings-outline', 'view': 'settings'},
]

# Module Dependencies
DEPENDENCIES = ['customers', 'services']
