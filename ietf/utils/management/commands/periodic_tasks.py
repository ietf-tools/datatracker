# Copyright The IETF Trust 2024, All Rights Reserved
import json
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from django.core.management.base import BaseCommand

CRONTAB_DEFS = {
    # same as "@weekly" in a crontab
    "weekly": {
        "minute": "0",
        "hour": "0",
        "day_of_month": "*",
        "month_of_year": "*",
        "day_of_week": "0",
        "timezone": "America/Los_Angeles",
    },
    "daily": {
        "minute": "5",
        "hour": "0",
        "day_of_month": "*",
        "month_of_year": "*",
        "day_of_week": "*",
        "timezone": "America/Los_Angeles",
    },
    "hourly": {
        "minute": "5",
        "hour": "*",
        "day_of_month": "*",
        "month_of_year": "*",
        "day_of_week": "*",
    },
    "every_15m": {
        "minute": "*/15",
        "hour": "*",
        "day_of_month": "*",
        "month_of_year": "*",
        "day_of_week": "*",
    },
    "every_15m_except_midnight": {
        "minute": "*/15",
        "hour": "1-23",
        "day_of_month": "*",
        "month_of_year": "*",
        "day_of_week": "*",
        "timezone": "America/Los_Angeles",
    },
}


class Command(BaseCommand):
    """Manage periodic tasks"""
    crontabs = None

    def add_arguments(self, parser):
        parser.add_argument("--create-default", action="store_true")
        parser.add_argument("--enable", type=int, action="append")
        parser.add_argument("--disable", type=int, action="append")

    def handle(self, *args, **options):
        self.crontabs = self.get_or_create_crontabs()
        if options["create_default"]:
            self.create_default_tasks()
        if options["enable"]:
            self.enable_tasks(options["enable"])
        if options["disable"]:
            self.disable_tasks(options["disable"])
        self.show_tasks()

    def get_or_create_crontabs(self):
        crontabs = {}
        for label, definition in CRONTAB_DEFS.items():
            crontabs[label], _ = CrontabSchedule.objects.get_or_create(**definition)
        return crontabs

    def create_default_tasks(self):
        PeriodicTask.objects.get_or_create(
            name="Send scheduled mail",
            task="ietf.message.tasks.send_scheduled_mail_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["every_15m"],
                description="Send mail scheduled to go out at certain times"
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Partial sync with RFC Editor index",
            task="ietf.sync.tasks.rfc_editor_index_update_task",
            kwargs=json.dumps(dict(full_index=False)),
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["every_15m_except_midnight"],  # don't collide with full sync
                description=(
                    "Reparse the last _year_ of RFC index entries until "
                    "https://github.com/ietf-tools/datatracker/issues/3734 is addressed. "
                    "This takes about 20s on production as of 2022-08-11."
                )
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Full sync with RFC Editor index",
            task="ietf.sync.tasks.rfc_editor_index_update_task",
            kwargs=json.dumps(dict(full_index=True)),
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["daily"],
                description=(
                    "Run an extended version of the rfc editor update to catch changes with backdated timestamps"
                ),
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Fetch meeting attendance",
            task="ietf.stats.tasks.fetch_meeting_attendance_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["daily"],
                description="Fetch meeting attendance data from ietf.org/registration/attendees",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Send review reminders",
            task="ietf.review.tasks.send_review_reminders_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["daily"],
                description="Send reminders originating from the review app",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Expire I-Ds",
            task="ietf.doc.tasks.expire_ids_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["daily"],
                description="Create expiration notices for expired I-Ds",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Expire Last Calls",
            task="ietf.doc.tasks.expire_last_calls_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["daily"],
                description="Move docs whose last call has expired to their next states",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Sync with IANA changes",
            task="ietf.sync.tasks.iana_changes_update_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["hourly"],
                description="Fetch change list from IANA and apply to documents",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Sync with IANA protocols page",
            task="ietf.sync.tasks.iana_protocols_update_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["hourly"],
                description="Fetch protocols page from IANA and update document event logs",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Update I-D index files",
            task="ietf.idindex.tasks.idindex_update_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["hourly"],
                description="Update I-D index files",
            ),
        )
        
        PeriodicTask.objects.get_or_create(
            name="Send expiration notifications",
            task="ietf.doc.tasks.notify_expirations_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["weekly"],
                description="Send notifications about I-Ds that will expire in the next 14 days",
            )
        )

        PeriodicTask.objects.get_or_create(
            name="Generate idnits2 rfcs-obsoleted blob",
            task="ietf.doc.tasks.generate_idnits2_rfcs_obsoleted_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["hourly"],
                description="Generate the rfcs-obsoleted file used by idnits",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Generate idnits2 rfc-status blob",
            task="ietf.doc.tasks.generate_idnits2_rfc_status_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["hourly"],
                description="Generate the rfc_status blob used by idnits",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Send NomCom reminders",
            task="ietf.nomcom.tasks.send_nomcom_reminders_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["daily"],
                description="Send acceptance and questionnaire reminders to nominees",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Generate WG charter files",
            task="ietf.group.tasks.generate_wg_charters_files_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["hourly"],
                description="Update 1wg-charters.txt and 1wg-charters-by-acronym.txt",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Generate WG summary files",
            task="ietf.group.tasks.generate_wg_summary_files_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["hourly"],
                description="Update 1wg-summary.txt and 1wg-summary-by-acronym.txt",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Generate I-D bibxml files",
            task="ietf.doc.tasks.generate_draft_bibxml_files_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["hourly"],
                description="Generate draft bibxml files for the last week's drafts",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Send personal API key usage emails",
            task="ietf.person.tasks.send_apikey_usage_emails_task",
            kwargs=json.dumps(dict(days=7)),
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["weekly"],
                description="Send personal API key usage summary emails for the past week",
            ),
        )
        
        PeriodicTask.objects.get_or_create(
            name="Purge old personal API key events",
            task="ietf.person.tasks.purge_personal_api_key_events_task",
            kwargs=json.dumps(dict(keep_days=14)),
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["daily"],
                description="Purge PersonApiKeyEvent instances older than 14 days",
            ),
        )

        PeriodicTask.objects.get_or_create(
            name="Run Yang model checks",
            task="ietf.submit.tasks.run_yang_model_checks_task",
            defaults=dict(
                enabled=False,
                crontab=self.crontabs["daily"],
                description="Re-run Yang model checks on all active drafts",
            ),
        )

    def show_tasks(self):
        for label, crontab in self.crontabs.items():
            tasks = PeriodicTask.objects.filter(crontab=crontab).order_by(
                "task", "name"
            )
            self.stdout.write(f"\n{label} ({crontab.human_readable})\n")
            if tasks:
                for task in tasks:
                    desc = f"  {task.id:-3d}: {task.task} - {task.name}"
                    if task.enabled:
                        self.stdout.write(desc)
                    else:
                        self.stdout.write(self.style.NOTICE(f"{desc} - disabled"))
            else:
                self.stdout.write("  Nothing scheduled")

    def enable_tasks(self, pks):
        PeriodicTask.objects.filter(
            crontab__in=self.crontabs.values(), pk__in=pks
        ).update(enabled=True)

    def disable_tasks(self, pks):
        PeriodicTask.objects.filter(
            crontab__in=self.crontabs.values(), pk__in=pks
        ).update(enabled=False)
