# Copyright The IETF Trust 2021-2026 All Rights Reserved
import datetime
from pathlib import Path

from django.conf import settings

from ietf.doc.models import (
    BofreqEditorDocEvent,
    BofreqResponsibleDocEvent,
    DocEvent,
    DocHistory,
    Document,
)
from ietf.person.models import Person


def bofreq_editors(bofreq):
    e = bofreq.latest_event(BofreqEditorDocEvent)
    return e.editors.all() if e else Person.objects.none()


def bofreq_responsible(bofreq):
    e = bofreq.latest_event(BofreqResponsibleDocEvent)
    return e.responsible.all() if e else Person.objects.none()


def fixup_bofreq_timestamps():
    """Fixes bofreq event / document timestamps

    Timestamp errors resulted from the bug fixed by
    https://github.com/ietf-tools/datatracker/pull/10333
    """
    FIX_DEPLOYMENT_TIME = "2026-02-03T01:16:00+00:00"  # 12.58.0 -> production

    def _get_doc_time(doc_name: str, rev: str):
        path = Path(settings.BOFREQ_PATH) / f"{doc_name}-{rev}.md"
        return datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.UTC)

    # Find affected DocEvents and DocHistories
    new_bofreq_events = (
        DocEvent.objects.filter(
            doc__type="bofreq", type="new_revision", time__lt=FIX_DEPLOYMENT_TIME
        )
        .exclude(rev="00")
        .order_by("doc__name", "rev")
    )
    document_fixups = {}
    for e in new_bofreq_events:
        name = e.doc.name
        rev = e.rev
        filesystem_time = _get_doc_time(name, rev)
        assert e.time < filesystem_time, (
            f"Rev {rev} event timestamp for {name} unexpectedly later than the "
            "filesystem timestamp!"
        )
        try:
            dochistory = DocHistory.objects.filter(
                name=name, time__lt=filesystem_time
            ).get(rev=rev)
        except DocHistory.MultipleObjectsReturned as err:
            raise RuntimeError(
                f"Multiple DocHistories for {name} rev {rev} exist earlier than the "
                "filesystem timestamp!"
            ) from err
        except DocHistory.DoesNotExist as err:
            if rev == "00":
                dochistory = None
            else:
                raise RuntimeError(
                    f"No DocHistory for {name} rev {rev} exists earlier than the "
                    f"filesystem timestamp!"
                ) from err

        if name not in document_fixups:
            document_fixups[name] = []
        document_fixups[name].append(
            {
                "event": e,
                "dochistory": dochistory,
                "filesystem_time": filesystem_time,
            }
        )

    # Now do the actual fixup
    system_person = Person.objects.get(name="(System)")
    for doc_name, fixups in document_fixups.items():
        bofreq = Document.objects.get(type="bofreq", name=doc_name)
        adjusted_revs = []
        for fixup in fixups:
            event_to_fix = fixup["event"]
            dh_to_fix = fixup["dochistory"]
            new_time = fixup["filesystem_time"]

            adjusted_revs.append(event_to_fix.rev)
            if event_to_fix.rev == bofreq.rev and bofreq.time < new_time:
                # Update the Document without calling save(). Only update if
                # the time has not changed so we don't inadvertently overwrite
                # a concurrent update.
                Document.objects.filter(pk=bofreq.pk, time=bofreq.time).update(
                    time=new_time
                )
                bofreq.refresh_from_db()

            # Fix up the event
            event_to_fix.time = new_time
            event_to_fix.save()

            # Fix up the DocHistory
            dh_to_fix.time = new_time
            dh_to_fix.save()

        # Fix up the Document, if necessary, and add a record of the adjustment
        change_event = DocEvent.objects.create(
            type="added_comment",
            by=system_person,
            doc=bofreq,
            rev=bofreq.rev,
            desc=(
                "Corrected inaccurate document and new revision event timestamps for "
                f"revs {', '.join(adjusted_revs)}"
            ),
        )
