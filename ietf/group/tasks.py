# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import shutil

from celery import shared_task
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from ietf.doc.storage_utils import store_file
from ietf.liaisons.models import LiaisonStatement
from ietf.utils import log
from ietf.utils.test_runner import disable_coverage

from .models import Group, GroupHistory
from .utils import fill_in_charter_info, fill_in_wg_drafts, fill_in_wg_roles, save_group_in_history
from .views import extract_last_name, roles


@shared_task
def generate_wg_charters_files_task():
    areas = Group.objects.filter(type="area", state="active").order_by("name")
    groups = (
        Group.objects.filter(type="wg", state="active")
        .exclude(parent=None)
        .order_by("acronym")
    )
    for group in groups:
        fill_in_charter_info(group)
        fill_in_wg_roles(group)
        fill_in_wg_drafts(group)
    for area in areas:
        area.groups = [g for g in groups if g.parent_id == area.pk]
    charter_path = Path(settings.CHARTER_PATH)
    charters_file = charter_path / "1wg-charters.txt"
    charters_file.write_text(
        render_to_string("group/1wg-charters.txt", {"areas": areas}),
        encoding="utf8",
    )
    charters_by_acronym_file = charter_path / "1wg-charters-by-acronym.txt"
    charters_by_acronym_file.write_text(
        render_to_string("group/1wg-charters-by-acronym.txt", {"groups": groups}),
        encoding="utf8",
    )

    with charters_file.open("rb") as f:
        store_file("indexes", "1wg-charters.txt", f, allow_overwrite=True)
    with charters_by_acronym_file.open("rb") as f:
        store_file("indexes", "1wg-charters-by-acronym.txt", f, allow_overwrite=True)

    charter_copy_dests = [
        getattr(settings, "CHARTER_COPY_PATH", None), 
        getattr(settings, "CHARTER_COPY_OTHER_PATH", None),
        getattr(settings, "CHARTER_COPY_THIRD_PATH", None),
    ]
    for charter_copy_dest in charter_copy_dests:
        if charter_copy_dest is not None:
            if not Path(charter_copy_dest).is_dir():
                log.log(
                    f"Error copying 1wg-charter files to {charter_copy_dest}: it does not exist or is not a directory"
                )
            else:
                try:
                    shutil.copy2(charters_file, charter_copy_dest)
                except IOError as err:
                    log.log(f"Error copying {charters_file} to {charter_copy_dest}: {err}")
                try:
                    shutil.copy2(charters_by_acronym_file, charter_copy_dest)
                except IOError as err:
                    log.log(
                        f"Error copying {charters_by_acronym_file} to {charter_copy_dest}: {err}"
                    )


@shared_task
def generate_wg_summary_files_task():
    # Active WGs (all should have a parent, but filter to be sure)
    groups = (
        Group.objects.filter(type="wg", state="active")
        .exclude(parent=None)
        .order_by("acronym")
    )
    # Augment groups with chairs list
    for group in groups:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)

    # Active areas with one or more active groups in them 
    areas = Group.objects.filter(
        type="area",
        state="active",
        group__in=groups,
    ).distinct().order_by("name")
    # Augment areas with their groups
    for area in areas:
        area.groups = [g for g in groups if g.parent_id == area.pk]
    summary_path = Path(settings.GROUP_SUMMARY_PATH)
    summary_file = summary_path / "1wg-summary.txt"
    summary_file.write_text(
        render_to_string("group/1wg-summary.txt", {"areas": areas}),
        encoding="utf8",
    )
    summary_by_acronym_file = summary_path / "1wg-summary-by-acronym.txt"
    summary_by_acronym_file.write_text(
        render_to_string(
            "group/1wg-summary-by-acronym.txt",
            {"areas": areas, "groups": groups},
        ),
        encoding="utf8",
    )

    with summary_file.open("rb") as f:
        store_file("indexes", "1wg-summary.txt", f, allow_overwrite=True)
    with summary_by_acronym_file.open("rb") as f:
        store_file("indexes", "1wg-summary-by-acronym.txt", f, allow_overwrite=True)

@shared_task
@disable_coverage()
def run_once_adjust_liaison_groups():  # pragma: no cover
    log.log("Starting run_once_adjust_liaison_groups")
    if all(
        [
            Group.objects.filter(
                acronym__in=[
                    "3gpp-tsg-ct",
                    "3gpp-tsg-ran-wg1",
                    "3gpp-tsg-ran-wg4",
                    "3gpp-tsg-sa",
                    "3gpp-tsg-sa-wg5",
                    "3gpp-tsgct",  # duplicates 3gpp-tsg-ct above already
                    "3gpp-tsgct-ct1",  # will normalize all acronyms to hyphenated form
                    "3gpp-tsgct-ct3",  # and consistently match the name
                    "3gpp-tsgct-ct4",  # (particularly use of WG)
                    "3gpp-tsgran",
                    "3gpp-tsgran-ran2",
                    "3gpp-tsgsa",  # duplicates 3gpp-tsg-sa above
                    "3gpp-tsgsa-sa2",  # will normalize
                    "3gpp-tsgsa-sa3",
                    "3gpp-tsgsa-sa4",
                    "3gpp-tsgt-wg2",
                ]
            ).count()
            == 16,
            not Group.objects.filter(
                acronym__in=[
                    "3gpp-tsg-ran-wg3",
                    "3gpp-tsg-ct-wg1",
                    "3gpp-tsg-ct-wg3",
                    "3gpp-tsg-ct-wg4",
                    "3gpp-tsg-ran",
                    "3gpp-tsg-ran-wg2",
                    "3gpp-tsg-sa-wg2",
                    "3gpp-tsg-sa-wg3",
                    "3gpp-tsg-sa-wg4",
                    "3gpp-tsg-t-wg2",
                ]
            ).exists(),
            Group.objects.filter(acronym="o3gpptsgran3").exists(),
            not LiaisonStatement.objects.filter(
                to_groups__acronym__in=["3gpp-tsgct", "3gpp-tsgsa"]
            ).exists(),
            not LiaisonStatement.objects.filter(
                from_groups__acronym="3gpp-tsgct"
            ).exists(),
            LiaisonStatement.objects.filter(from_groups__acronym="3gpp-tsgsa").count()
            == 1,
            LiaisonStatement.objects.get(from_groups__acronym="3gpp-tsgsa").pk == 1448,
        ]
    ):
        for old_acronym, new_acronym, new_name in (
            ("o3gpptsgran3", "3gpp-tsg-ran-wg3", "3GPP TSG RAN WG3"),
            ("3gpp-tsgct-ct1", "3gpp-tsg-ct-wg1", "3GPP TSG CT WG1"),
            ("3gpp-tsgct-ct3", "3gpp-tsg-ct-wg3", "3GPP TSG CT WG3"),
            ("3gpp-tsgct-ct4", "3gpp-tsg-ct-wg4", "3GPP TSG CT WG4"),
            ("3gpp-tsgran", "3gpp-tsg-ran", "3GPP TSG RAN"),
            ("3gpp-tsgran-ran2", "3gpp-tsg-ran-wg2", "3GPP TSG RAN WG2"),
            ("3gpp-tsgsa-sa2", "3gpp-tsg-sa-wg2", "3GPP TSG SA WG2"),
            ("3gpp-tsgsa-sa3", "3gpp-tsg-sa-wg3", "3GPP TSG SA WG3"),
            ("3gpp-tsgsa-sa4", "3gpp-tsg-sa-wg4", "3GPP TSG SA WG4"),
            ("3gpp-tsgt-wg2", "3gpp-tsg-t-wg2", "3GPP TSG T WG2"),
        ):
            group = Group.objects.get(acronym=old_acronym)
            save_group_in_history(group)
            group.time = timezone.now()
            group.acronym = new_acronym
            group.name = new_name
            if old_acronym.startswith("3gpp-tsgct-"):
                group.parent = Group.objects.get(acronym="3gpp-tsg-ct")
            elif old_acronym.startswith("3gpp-tsgsa-"):
                group.parent = Group.objects.get(acronym="3gpp-tsg-sa")
            group.save()
            group.groupevent_set.create(
                time=group.time,
                by_id=1,  # (System)
                type="info_changed",
                desc=f"acronym changed from {old_acronym} to {new_acronym}, name set to {new_name}",
            )

        for acronym, new_name in (("3gpp-tsg-ct", "3GPP TSG CT"),):
            group = Group.objects.get(acronym=acronym)
            save_group_in_history(group)
            group.time = timezone.now()
            group.name = new_name
            group.save()
            group.groupevent_set.create(
                time=group.time,
                by_id=1,  # (System)
                type="info_changed",
                desc=f"name set to {new_name}",
            )

        ls = LiaisonStatement.objects.get(pk=1448)
        ls.from_groups.remove(Group.objects.get(acronym="3gpp-tsgsa"))
        ls.from_groups.add(Group.objects.get(acronym="3gpp-tsg-sa"))

        # Rewriting history to effectively merge the histories of the duplicate groups
        GroupHistory.objects.filter(parent__acronym="3gpp-tsgsa").update(
            parent=Group.objects.get(acronym="3gpp-tsg-sa")
        )
        GroupHistory.objects.filter(parent__acronym="3gpp-tsgct").update(
            parent=Group.objects.get(acronym="3gpp-tsg-ct")
        )

        deleted = Group.objects.filter(
            acronym__in=["3gpp-tsgsa", "3gpp-tsgct"]
        ).delete()
        log.log(f"Deleted Groups: {deleted}")
    else:
        log.log("* Refusing to continue as preconditions have changed")
