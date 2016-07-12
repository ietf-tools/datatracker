#!/usr/bin/env python

import sys, os

# boilerplate
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

import django
django.setup()


# script

import datetime
from collections import namedtuple
from django.db import connections
from ietf.review.models import ReviewRequest, Reviewer, ReviewResultName
from ietf.review.models import ReviewRequestStateName, ReviewTypeName, ReviewTeamResult
from ietf.group.models import Group, Role, RoleName
from ietf.person.models import Person, Email, Alias
import argparse
from unidecode import unidecode
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument("database", help="database must be included in settings")
parser.add_argument("team", help="team acronym, must exist")
args = parser.parse_args()

db_con = connections[args.database]
team = Group.objects.get(acronym=args.team)

def namedtuplefetchall(cursor):
    "Return all rows from a cursor as a namedtuple"
    desc = cursor.description
    nt_result = namedtuple('Result', [col[0] for col in desc])
    return (nt_result(*row) for row in cursor.fetchall())

def parse_timestamp(t):
    if not t:
        return None
    return datetime.datetime.fromtimestamp(t)

# personnel
with db_con.cursor() as c:
    c.execute("select distinct reviewer from reviews;")
    known_reviewers = { row[0] for row in c.fetchall() }

with db_con.cursor() as c:
    c.execute("select distinct who from doclog;")
    docloggers = { row[0] for row in c.fetchall() }

with db_con.cursor() as c:
    c.execute("select distinct login from members where permissions like '%secretary%';")
    secretaries = { row[0] for row in c.fetchall() }

autopolicy_days = {
    'weekly': 7,
    'biweekly': 14,
    'monthly': 30,
    'bimonthly': 61,
    'quarterly': 91,
}

known_personnel = {}
with db_con.cursor() as c:
    c.execute("select * from members;")

    needed_personnel = known_reviewers | docloggers | secretaries

    for row in namedtuplefetchall(c):
        if row.login not in needed_personnel:
            continue

        email = Email.objects.filter(address=row.email).select_related("person").first()
        if not email:
            person = Person.objects.filter(alias__name=row.name).first()
            if not person:
                person, created = Person.objects.get_or_create(name=row.name, ascii=unidecode(row.name))
                if created:
                    print "created person", unicode(person).encode("utf-8")
                existing_aliases = set(Alias.objects.filter(person=person).values_list("name", flat=True))
                curr_names = set(x for x in [person.name, person.ascii, person.ascii_short, person.plain_name(), ] if x)
                new_aliases = curr_names - existing_aliases
                for name in new_aliases:
                    Alias.objects.create(person=person, name=name)

            email, created = Email.objects.get_or_create(address=row.email, person=person)
            if created:
                print "created email", email

        known_personnel[row.login] = email

        if "secretary" in row.permissions:
            role, created = Role.objects.get_or_create(name=RoleName.objects.get(slug="secr"), person=email.person, email=email, group=team)
            if created:
                print "created role", unicode(role).encode("utf-8")

        if row.login in known_reviewers:
            if row.comment != "Inactive" and row.available != 2145916800: # corresponds to 2038-01-01
                role, created  = Role.objects.get_or_create(name=RoleName.objects.get(slug="reviewer"), person=email.person, email=email, group=team)

                if created:
                    print "created role", unicode(role).encode("utf-8")

                reviewer, created = Reviewer.objects.get_or_create(
                    team=team,
                    person=email.person,
                )
                if reviewer:
                    print "created reviewer", reviewer.pk, unicode(reviewer).encode("utf-8")

                if autopolicy_days.get(row.autopolicy):
                    reviewer.frequency = autopolicy_days.get(row.autopolicy)
                reviewer.unavailable_until = parse_timestamp(row.available)
                reviewer.filter_re = row.donotassign
                try:
                    reviewer.skip_next = int(row.autopolicy)
                except ValueError:
                    pass
                reviewer.save()

# review requests

# check that we got the needed names
results = { n.name.lower(): n for n in ReviewResultName.objects.all() }

with db_con.cursor() as c:
    c.execute("select distinct summary from reviews;")
    summaries = [r[0].lower() for r in c.fetchall() if r[0]]
    missing_result_names = set(summaries) - set(results.keys())
    assert not missing_result_names, "missing result names: {} {}".format(missing_result_names, results.keys())

    for s in summaries:
        ReviewTeamResult.objects.get_or_create(team=team, result=results[s])

states = { n.slug: n for n in ReviewRequestStateName.objects.all() }
# map some names
states["assigned"] = states["requested"]
states["done"] = states["completed"]
states["noresponse"] = states["no-response"]

with db_con.cursor() as c:
    c.execute("select distinct docstatus from reviews;")
    docstates = [r[0] for r in c.fetchall() if r[0]]
    missing_state_names = set(docstates) - set(states.keys())
    assert not missing_state_names, "missing state names: {}".format(missing_state_names)

type_names = { n.slug: n for n in ReviewTypeName.objects.all() }

# extract relevant log entries

request_assigned = defaultdict(list)

with db_con.cursor() as c:
    c.execute("select docname, time, who from doclog where text = 'AUTO UPDATED status TO working' order by time desc;")
    for row in namedtuplefetchall(c):
        request_assigned[row.docname].append((row.time, row.who))

# extract document request metadata

doc_metadata = {}

with db_con.cursor() as c:
    c.execute("select docname, version, deadline, telechat, lcend, status from documents order by docname, version;")

    for row in namedtuplefetchall(c):
        doc_metadata[(row.docname, row.version)] = doc_metadata[row.docname] = (parse_timestamp(row.deadline), parse_timestamp(row.telechat), parse_timestamp(row.lcend), row.status)


system_person = Person.objects.get(name="(System)")

with db_con.cursor() as c:
    c.execute("select * from reviews order by reviewid;")

    for row in namedtuplefetchall(c):
        meta = doc_metadata.get((row.docname, row.version))
        if not meta:
            meta = doc_metadata.get(row.docname)

        deadline, telechat, lcend, status = meta or (None, None, None, None)

        if not deadline:
            deadline = parse_timestamp(row.timeout)

        type_name = type_names["unknown"]
        # FIXME: use lcend and telechat to try to deduce type

        reviewed_rev = row.version if row.version and row.version != "99" else ""
        if row.summary == "noresponse":
            reviewed_rev = ""

        assignment_logs = request_assigned.get(row.docname, [])
        if assignment_logs:
            time, who = assignment_logs.pop()

            time = parse_timestamp(time)
        else:
            time = deadline

        if not deadline:
            # bogus row
            print "SKIPPING WITH NO DEADLINE", time, row, meta
            continue

        if status == "done" and row.docstatus in ("assigned", "accepted"):
            # filter out some apparently dead requests
            print "SKIPPING MARKED DONE even if assigned/accepted", time, row
            continue

        req, _ = ReviewRequest.objects.get_or_create(
            doc_id=row.docname,
            team=team,
            old_id=row.reviewid,
            defaults={
                "state": states["requested"],
                "type": type_name,
                "deadline": deadline,
                "requested_by": system_person,
            }
        )

        req.reviewer = known_personnel[row.reviewer] if row.reviewer else None
        req.result = results.get(row.summary.lower()) if row.summary else None
        req.state = states.get(row.docstatus) if row.docstatus else None
        req.type = type_name
        req.time = time
        req.reviewed_rev = reviewed_rev
        req.deadline = deadline
        req.save()

        # FIXME: add log entries
        # FIXME: add review from reviewurl
        # FIXME: do something about missing result

        # adcomments   IGNORED
        # lccomments   IGNORED
        # nits         IGNORED
        # reviewurl    review.external_url

        #print meta and meta[0], telechat, lcend, req.type

        if req.state_id == "requested" and req.doc.get_state_slug("draft-iesg") in ["approved", "ann", "rfcqueue", "pub"]:
            req.state = states["overtaken"]
            req.save()

        print "imported review", row.reviewid, "as", req.pk, req.time, req.deadline, req.type, req.doc_id, req.state, req.doc.get_state_slug("draft-iesg")
