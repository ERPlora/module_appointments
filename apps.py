from django.apps import AppConfig


class AppointmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "appointments"
    verbose_name = "Appointments"

    def ready(self):
        pass

    # =========================================================================
    # HOOK HELPER METHODS
    # =========================================================================
    # These methods are called by the hub's hook system at various points.
    # Override them to customize behavior.

    @staticmethod
    def do_before_appointment_create(data: dict) -> dict:
        """Called before creating an appointment. Can modify data."""
        return data

    @staticmethod
    def do_after_appointment_create(appointment) -> None:
        """Called after an appointment is created."""
        pass

    @staticmethod
    def do_before_appointment_update(appointment, data: dict) -> dict:
        """Called before updating an appointment. Can modify data."""
        return data

    @staticmethod
    def do_after_appointment_update(appointment) -> None:
        """Called after an appointment is updated."""
        pass

    @staticmethod
    def do_after_appointment_status_change(appointment, old_status: str, new_status: str) -> None:
        """Called after an appointment status changes."""
        pass

    @staticmethod
    def do_after_appointment_confirm(appointment) -> None:
        """Called after an appointment is confirmed."""
        pass

    @staticmethod
    def do_after_appointment_cancel(appointment) -> None:
        """Called after an appointment is cancelled."""
        pass

    @staticmethod
    def do_after_appointment_complete(appointment) -> None:
        """Called after an appointment is completed."""
        pass

    @staticmethod
    def filter_appointments_list(queryset, request):
        """Filter appointments queryset before display."""
        return queryset

    @staticmethod
    def filter_calendar_events(events: list, request) -> list:
        """Filter calendar events before display."""
        return events
