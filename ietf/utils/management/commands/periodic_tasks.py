# Copyright The IETF Trust 2024, All Rights Reserved
import json
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from django.core.management.base import BaseCommand

CRONTAB_DEFS = {
    "daily": {
        "minute": "5",
        "hour": "0",
        "day_of_week": "*",
        "day_of_month": "*",
        "month_of_year": "*",
    },
    "hourly": {
        "minute": "5",
        "hour": "*",
        "day_of_week": "*",
        "day_of_month": "*",
        "month_of_year": "*",
    },
    "every_15m": {
        "minute": "*/15",
        "hour": "*",
        "day_of_week": "*",
        "day_of_month": "*",
        "month_of_year": "*",
    },
}


class Command(BaseCommand):
    """Manage periodic tasks"""

    def add_arguments(self, parser):
        parser.add_argument("--create-default", action="store_true")

    def handle(self, *args, **options):
        print(repr(options))
        if options["create_default"]:
            self.stdout.write("Ha!")
            return
        self.show_tasks()

    def get_or_create_crontabs(self):
        crontabs = {}
        for label, definition in CRONTAB_DEFS.items():
            crontabs[label], _ = CrontabSchedule.objects.get_or_create(**definition)
        return crontabs

    def create_default_tasks(self):
        # For now, just install the default task schedules
        crontabs = self.get_or_create_crontabs()

        # schedule the tasks
        PeriodicTask.objects.get_or_create(
            name="Send scheduled mail",
            task="ietf.utils.tasks.send_scheduled_mail_task",
            defaults=dict(
                crontab=crontabs["every_15m"],
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Partial sync with RFC Editor index",
            task="ietf.review.tasks.rfc_editor_index_update_task",
            kwargs=json.dumps(dict(full_index=False)),
            defaults=dict(
                crontab=crontabs["every_15m"],
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Full sync with RFC Editor index",
            task="ietf.review.tasks.rfc_editor_index_update_task",
            kwargs=json.dumps(dict(full_index=True)),
            defaults=dict(
                crontab=crontabs["daily"],
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Fetch meeting attendance",
            task="ietf.stats.tasks.fetch_meeting_attendance_task",
            defaults=dict(
                crontab=crontabs["daily"],
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Send review reminders",
            task="ietf.review.tasks.send_review_reminders_task",
            defaults=dict(
                crontab=crontabs["daily"],
            ),
        )

    def show_tasks(self):
        crontabs = self.get_or_create_crontabs()
        for label, crontab in crontabs.items():
            tasks = PeriodicTask.objects.filter(crontab=crontab).order_by(
                "task", "name"
            )
            self.stdout.write(f"\n{label} ({crontab.human_readable})\n")
            if tasks:
                for task in tasks:
                    self.stdout.write(f"  {task.task} - {task.name}\n")
            else:
                print("  Nothing scheduled")
