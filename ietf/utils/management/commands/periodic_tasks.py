# Copyright The IETF Trust 2024, All Rights Reserved
import json
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Manage periodic tasks"""
    def handle(self, *args, **options):
        # For now, just install the default task schedules
        daily, _ = CrontabSchedule.objects.get_or_create(
            minute="5",
            hour="0",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )
        hourly, _ = CrontabSchedule.objects.get_or_create(
            minute="5",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )
        every_15m, _ = CrontabSchedule.objects.get_or_create(
            minute="*/15",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )

        # schedule the tasks
        PeriodicTask.objects.get_or_create(
            name="Send scheduled mail",
            task="ietf.utils.tasks.send_scheduled_mail_task",
            defaults=dict(
                crontab=every_15m,
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Partial sync with RFC Editor index",
            task="ietf.review.tasks.rfc_editor_index_update_task",
            kwargs=json.dumps(dict(full_index=False)),
            defaults=dict(
                crontab=every_15m,
            ),
        )
        
        PeriodicTask.objects.get_or_create(
            name="Full sync with RFC Editor index",
            task="ietf.review.tasks.rfc_editor_index_update_task",
            kwargs=json.dumps(dict(full_index=True)),
            defaults=dict(
                crontab=daily,
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Fetch meeting attendance",
            task="ietf.stats.tasks.fetch_meeting_attendance_task",
            defaults=dict(
                crontab=daily,
            ),
        )
        
        PeriodicTask.objects.get_or_create(
            name="Send review reminders",
            task="ietf.review.tasks.send_review_reminders_task",
            defaults=dict(
                crontab=daily,
            ),
        )
