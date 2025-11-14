from collections import Counter, defaultdict, namedtuple

import datetime

import debug  # pyflakes:ignore

from django.db import models
from django.utils import timezone

from ietf.doc.models import Document, STATUSCHANGE_RELATIONS
from ietf.doc.utils_search import fill_in_telechat_date
from ietf.group.models import Group
from ietf.iesg.agenda import get_doc_section
from ietf.person.utils import get_active_ads
from ietf.utils.unicodenormalize import normalize_for_sorting

TelechatPageCount = namedtuple(
    "TelechatPageCount",
    ["for_approval", "for_action", "related", "ad_pages_left_to_ballot_on"],
)


def telechat_page_count(date=None, docs=None, ad=None):
    if not date and not docs:
        return TelechatPageCount(0, 0, 0, 0)

    if not docs:
        candidates = Document.objects.filter(
            docevent__telechatdocevent__telechat_date=date
        ).distinct()
        fill_in_telechat_date(candidates)
        docs = [doc for doc in candidates if doc.telechat_date() == date]

    for_action = [d for d in docs if get_doc_section(d).endswith(".3")]

    for_approval = set(docs) - set(for_action)

    drafts = [d for d in for_approval if d.type_id == "draft"]

    ad_pages_left_to_ballot_on = 0
    pages_for_approval = 0

    for draft in drafts:
        pages_for_approval += draft.pages or 0
        if ad:
            ballot = draft.active_ballot()
            if ballot:
                positions = ballot.active_balloter_positions()
                ad_position = positions.get(ad, None)
                if ad_position is None or ad_position.pos_id == "norecord":
                    ad_pages_left_to_ballot_on += draft.pages or 0

    pages_for_action = 0
    for d in for_action:
        if d.type_id == "draft":
            pages_for_action += d.pages or 0
        elif d.type_id == "statchg":
            for rel in d.related_that_doc(STATUSCHANGE_RELATIONS):
                pages_for_action += rel.pages or 0
        elif d.type_id == "conflrev":
            for rel in d.related_that_doc("conflrev"):
                pages_for_action += rel.pages or 0
        else:
            pass

    related_pages = 0
    for d in for_approval - set(drafts):
        if d.type_id == "statchg":
            for rel in d.related_that_doc(STATUSCHANGE_RELATIONS):
                related_pages += rel.pages or 0
        elif d.type_id == "conflrev":
            for rel in d.related_that_doc("conflrev"):
                related_pages += rel.pages or 0
        else:
            # There's really nothing to rely on to give a reading load estimate for charters
            pass

    return TelechatPageCount(
        for_approval=pages_for_approval,
        for_action=pages_for_action,
        related=related_pages,
        ad_pages_left_to_ballot_on=ad_pages_left_to_ballot_on,
    )


def get_wg_dashboard_info():
    docs = (
        Document.objects.filter(
            group__type="wg",
            group__state="active",
            states__type="draft",
            states__slug="active",
        )
        .filter(models.Q(ad__isnull=True) | models.Q(ad__in=get_active_ads()))
        .distinct()
        .prefetch_related("group", "group__parent")
        .exclude(
            states__type="draft-stream-ietf",
            states__slug__in=["c-adopt", "wg-cand", "dead", "parked", "info"],
        )
    )
    groups = Group.objects.filter(state="active", type="wg")
    areas = Group.objects.filter(state="active", type="area")

    total_group_count = groups.count()
    total_doc_count = docs.count()
    total_page_count = docs.aggregate(models.Sum("pages"))["pages__sum"] or 0
    totals = {
        "group_count": total_group_count,
        "doc_count": total_doc_count,
        "page_count": total_page_count,
    }

    # Since this view is primarily about counting subsets of the above docs query and the
    # expected number of returned documents is just under 1000 typically - do the totaling
    # work in python rather than asking the db to do it.

    groups_for_area = defaultdict(set)
    pages_for_area = defaultdict(lambda: 0)
    docs_for_area = defaultdict(lambda: 0)
    groups_for_ad = defaultdict(lambda: defaultdict(set))
    pages_for_ad = defaultdict(lambda: defaultdict(lambda: 0))
    docs_for_ad = defaultdict(lambda: defaultdict(lambda: 0))
    groups_for_noad = defaultdict(lambda: defaultdict(set))
    pages_for_noad = defaultdict(lambda: defaultdict(lambda: 0))
    docs_for_noad = defaultdict(lambda: defaultdict(lambda: 0))
    docs_for_wg = defaultdict(lambda: 0)
    pages_for_wg = defaultdict(lambda: 0)
    groups_total = set()
    pages_total = 0
    docs_total = 0

    responsible_for_group = defaultdict(lambda: defaultdict(lambda: "None"))
    responsible_count = defaultdict(lambda: defaultdict(lambda: 0))
    for group in groups:
        responsible = f"{', '.join([r.person.plain_name() for r in group.role_set.filter(name_id='ad')])}"
        docs_for_noad[responsible][group.parent.acronym] = (
            0  # Ensure these keys are present later
        )
        docs_for_ad[responsible][group.parent.acronym] = 0
        responsible_for_group[group.acronym][group.parent.acronym] = responsible
        responsible_count[responsible][group.parent.acronym] += 1

    for doc in docs:
        docs_for_wg[doc.group] += 1
        pages_for_wg[doc.group] += doc.pages
        groups_for_area[doc.group.area.acronym].add(doc.group.acronym)
        pages_for_area[doc.group.area.acronym] += doc.pages
        docs_for_area[doc.group.area.acronym] += 1

        if doc.ad is None:
            responsible = responsible_for_group[doc.group.acronym][
                doc.group.parent.acronym
            ]
            groups_for_noad[responsible][doc.group.parent.acronym].add(
                doc.group.acronym
            )
            pages_for_noad[responsible][doc.group.parent.acronym] += doc.pages
            docs_for_noad[responsible][doc.group.parent.acronym] += 1
        else:
            responsible = f"{doc.ad.plain_name()}"
            groups_for_ad[responsible][doc.group.parent.acronym].add(doc.group.acronym)
            pages_for_ad[responsible][doc.group.parent.acronym] += doc.pages
            docs_for_ad[responsible][doc.group.parent.acronym] += 1

        docs_total += 1
        groups_total.add(doc.group.acronym)
        pages_total += doc.pages

    groups_total = len(groups_total)
    totals["groups_with_docs_count"] = groups_total

    area_summary = []

    for area in areas:
        group_count = len(groups_for_area[area.acronym])
        doc_count = docs_for_area[area.acronym]
        page_count = pages_for_area[area.acronym]
        area_summary.append(
            {
                "area": area.acronym,
                "groups_in_area": groups.filter(parent=area).count(),
                "groups_with_docs": group_count,
                "doc_count": doc_count,
                "page_count": page_count,
                "group_percent": group_count / groups_total * 100
                if groups_total != 0
                else 0,
                "doc_percent": doc_count / docs_total * 100 if docs_total != 0 else 0,
                "page_percent": page_count / pages_total * 100
                if pages_total != 0
                else 0,
            }
        )
    area_summary.sort(key=lambda r: r["area"])
    area_totals = {
        "group_count": groups_total,
        "doc_count": docs_total,
        "page_count": pages_total,
    }

    noad_summary = []
    noad_totals = {
        "ad_group_count": 0,
        "doc_group_count": 0,
        "doc_count": 0,
        "page_count": 0,
    }
    for ad in docs_for_noad:
        for area in docs_for_noad[ad]:
            noad_totals["ad_group_count"] += responsible_count[ad][area]
            noad_totals["doc_group_count"] += len(groups_for_noad[ad][area])
            noad_totals["doc_count"] += docs_for_noad[ad][area]
            noad_totals["page_count"] += pages_for_noad[ad][area]
    for ad in docs_for_noad:
        for area in docs_for_noad[ad]:
            noad_summary.append(
                {
                    "ad": ad,
                    "area": area,
                    "ad_group_count": responsible_count[ad][area],
                    "doc_group_count": len(groups_for_noad[ad][area]),
                    "doc_count": docs_for_noad[ad][area],
                    "page_count": pages_for_noad[ad][area],
                    "group_percent": len(groups_for_noad[ad][area])
                    / noad_totals["doc_group_count"]
                    * 100
                    if noad_totals["doc_group_count"] != 0
                    else 0,
                    "doc_percent": docs_for_noad[ad][area]
                    / noad_totals["doc_count"]
                    * 100
                    if noad_totals["doc_count"] != 0
                    else 0,
                    "page_percent": pages_for_noad[ad][area]
                    / noad_totals["page_count"]
                    * 100
                    if noad_totals["page_count"] != 0
                    else 0,
                }
            )
    noad_summary.sort(key=lambda r: (normalize_for_sorting(r["ad"]), r["area"]))

    ad_summary = []
    ad_totals = {
        "ad_group_count": 0,
        "doc_group_count": 0,
        "doc_count": 0,
        "page_count": 0,
    }
    for ad in docs_for_ad:
        for area in docs_for_ad[ad]:
            ad_totals["ad_group_count"] += responsible_count[ad][area]
            ad_totals["doc_group_count"] += len(groups_for_ad[ad][area])
            ad_totals["doc_count"] += docs_for_ad[ad][area]
            ad_totals["page_count"] += pages_for_ad[ad][area]
    for ad in docs_for_ad:
        for area in docs_for_ad[ad]:
            ad_summary.append(
                {
                    "ad": ad,
                    "area": area,
                    "ad_group_count": responsible_count[ad][area],
                    "doc_group_count": len(groups_for_ad[ad][area]),
                    "doc_count": docs_for_ad[ad][area],
                    "page_count": pages_for_ad[ad][area],
                    "group_percent": len(groups_for_ad[ad][area])
                    / ad_totals["doc_group_count"]
                    * 100
                    if ad_totals["doc_group_count"] != 0
                    else 0,
                    "doc_percent": docs_for_ad[ad][area] / ad_totals["doc_count"] * 100
                    if ad_totals["doc_count"] != 0
                    else 0,
                    "page_percent": pages_for_ad[ad][area]
                    / ad_totals["page_count"]
                    * 100
                    if ad_totals["page_count"] != 0
                    else 0,
                }
            )
    ad_summary.sort(key=lambda r: (normalize_for_sorting(r["ad"]), r["area"]))

    rfc_counter = Counter(
        Document.objects.filter(type="rfc").values_list("group__acronym", flat=True)
    )
    recent_rfc_counter = Counter(
        Document.objects.filter(
            type="rfc",
            docevent__type="published_rfc",
            docevent__time__gte=timezone.now() - datetime.timedelta(weeks=104),
        ).values_list("group__acronym", flat=True)
    )
    for wg in set(groups) - set(docs_for_wg.keys()):
        docs_for_wg[wg] += 0
        pages_for_wg[wg] += 0
    wg_summary = []
    for wg in docs_for_wg:
        wg_summary.append(
            {
                "wg": wg.acronym,
                "area": wg.parent.acronym,
                "ad": responsible_for_group[wg.acronym][wg.parent.acronym],
                "doc_count": docs_for_wg[wg],
                "page_count": pages_for_wg[wg],
                "rfc_count": rfc_counter[wg.acronym],
                "recent_rfc_count": recent_rfc_counter[wg.acronym],
            }
        )
    wg_summary.sort(key=lambda r: (r["wg"], r["area"]))

    return (
        area_summary,
        area_totals,
        ad_summary,
        noad_summary,
        ad_totals,
        noad_totals,
        totals,
        wg_summary,
    )
