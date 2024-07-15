# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import shutil

from celery import shared_task
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string

from ietf.utils import log

from .models import Group
from .utils import fill_in_charter_info, fill_in_wg_drafts, fill_in_wg_roles
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

    charter_copy_dest = getattr(settings, "CHARTER_COPY_PATH", None)
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
