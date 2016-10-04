#!/usr/bin/env python

import sys, os

# boilerplate
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

import django
django.setup()


# script

import datetime, re, itertools
from collections import namedtuple
from django.db import connections
from ietf.review.models import (ReviewRequest, ReviewerSettings, ReviewResultName,
                                ReviewRequestStateName, ReviewTypeName, ReviewTeamResult,
                                UnavailablePeriod, NextReviewerInTeam)
from ietf.group.models import Group, Role, RoleName
from ietf.person.models import Person, Email, Alias
from ietf.doc.models import Document, DocAlias, ReviewRequestDocEvent, NewRevisionDocEvent, DocTypeName, State
from ietf.utils.text import strip_prefix
import argparse
from unidecode import unidecode

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

                reviewer, created = ReviewerSettings.objects.get_or_create(
                    team=team,
                    person=email.person,
                )
                if created:
                    print "created reviewer", reviewer.pk, unicode(reviewer).encode("utf-8")

                if autopolicy_days.get(row.autopolicy):
                    reviewer.min_interval = autopolicy_days.get(row.autopolicy)

                reviewer.filter_re = row.donotassign
                try:
                    reviewer.skip_next = int(row.autopolicy)
                except ValueError:
                    pass
                reviewer.save()

                unavailable_until = parse_timestamp(row.available)
                if unavailable_until:
                    today = datetime.date.today()
                    end_date = unavailable_until.date()
                    if end_date >= today:
                        UnavailablePeriod.objects.filter(person=email.person, team=team).delete()

                        UnavailablePeriod.objects.create(
                            team=team,
                            person=email.person,
                            start_date=today,
                            end_date=end_date,
                            availability="unavailable",
                        )

# check that we got the needed names
results = { n.name.lower(): n for n in ReviewResultName.objects.all() }

with db_con.cursor() as c:
    c.execute("select distinct summary from reviews;")
    summaries = [r[0].lower() for r in c.fetchall() if r[0]]
    missing_result_names = set(summaries) - set(results.keys())
    assert not missing_result_names, "missing result names: {} {}".format(missing_result_names, results.keys())


# configuration options
with db_con.cursor() as c:
    c.execute("select * from config;")

    for row in namedtuplefetchall(c):
        if row.name == "next": # next reviewer
            NextReviewerInTeam.objects.filter(team=team).delete()
            NextReviewerInTeam.objects.create(team=team, next_reviewer=known_personnel[row.value].person)

        if row.name == "summary-list": # review results used in team
            summaries = [v.strip().lower() for v in row.value.split(";") if v.strip()]

            for s in summaries:
                ReviewTeamResult.objects.get_or_create(team=team, result=results[s])

# review requests

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

document_history = {}

requested_re = re.compile("(?:ADDED docname =>|Created: remote=|AUTO UPDATED status TO new|CHANGED status FROM [^ ]+ => new|CHANGE status done => working)")

add_docstatus_re = re.compile('([a-zA-Z-_]+) ADD docstatus => (\w+)')
update_docstatus_re = re.compile('([a-zA-Z-_]+) (?:UPDATE|CHANGE) docstatus \w+ => (\w+)')
iesgstatus_re = re.compile('(?:ADD|ADDED|CHANGED) iesgstatus (?:FROM )?(?:[^ ]+ )?=> ([a-zA-Z-_]+)?')

deadline_re = re.compile('(?:ADD|ADDED|CHANGED) deadline (?:FROM )?(?:[^ ]+ )?=> ([1-9][0-9]+)')
telechat_re = re.compile('(?:ADD|ADDED|CHANGED) telechat (?:FROM )?(?:[^ ]+ )?=> ([1-9][0-9]+)')
lcend_re = re.compile('(?:ADD|ADDED|CHANGED) lcend (?:FROM )?(?:[^ ]+ )?=> ([1-9][0-9]+)')

close_states = ["done", "rejected", "withdrawn", "noresponse"]

with db_con.cursor() as c:
    c.execute("""select docname, time, who, text from doclog where
                        text like 'Created: remote=%'
                     or text like '%ADDED docname => %'
                     or text like '%AUTO UPDATED status TO new%'
                     or text like '%CHANGED status FROM % => new%'
                     or text like '%CHANGE status done => working%'

                     or text like '% ADD docstatus => %'
                     or text like '% UPDATE docstatus % => %'
                     or text like '% CHANGE docstatus % => %'
                     or text like '%CHANGE status working => done%'

                     or text like '%ADDED iesgstatus => %'
                     or text like '%ADD iesgstatus => %'
                     or text like '%CHANGED iesgstatus % => %'
                   order by docname, time asc;""")
    for docname, rows in itertools.groupby(namedtuplefetchall(c), lambda row: row.docname):
        branches = {}

        latest_requested = None
        non_specific_close = None
        latest_iesg_status = None

        for row in rows:
            state = None
            used = False

            if requested_re.search(row.text):
                if "Created: remote" in row.text:
                    latest_iesg_status = "early"
                state = "requested"
                membername = None
                used = True
            else:
                if "ADD docstatus" in row.text:
                    m = add_docstatus_re.match(row.text)
                    assert m, 'row.text "{}" does not match add regexp'.format(row.text)
                    membername, state = m.groups()
                    used = True
                elif "UPDATE docstatus" in row.text or "CHANGE docstatus" in row.text:
                    m = update_docstatus_re.match(row.text)
                    assert m, 'row.text "{}" does not match update regexp'.format(row.text)
                    membername, state = m.groups()
                    used = True

            if telechat_re.search(row.text) and not lcend_re.search(row.text):
                latest_iesg_status = "telechat"
                used = True
            elif ((not telechat_re.search(row.text) and lcend_re.search(row.text))
                or (deadline_re.search(row.text) and not telechat_re.search(row.text) and not lcend_re.search(row.text))):
                latest_iesg_status = "lc"
                used = True
            elif (deadline_re.search(row.text) and telechat_re.search(row.text) and lcend_re.search(row.text)):
                # if we got both, assume it was a Last Call
                latest_iesg_status = "lc"
                used = True

            if iesgstatus_re.search(row.text):
                m = iesgstatus_re.search(row.text)
                if m.groups():
                    literal_iesg_status = m.groups()[0]
                    if literal_iesg_status == "IESG_Evaluation":
                        latest_iesg_status = "telechat"
                    elif literal_iesg_status == "In_Last_Call":
                        latest_iesg_status = "lc"
                used = True

            if "CHANGE status working => done" in row.text:
                non_specific_close = (row, latest_iesg_status)
                used = True

            if not used:
                raise Exception("Unknown text {}".format(row.text))
                
            if not state:
                continue

            if state == "working":
                state = "assigned"

            if state == "requested":
                latest_requested = (row.time, row.who, membername, state, latest_iesg_status)
            else:
                if membername not in branches:
                    branches[membername] = []

                latest = branches[membername][-1] if branches[membername] else None

                if not latest or ((state == "assigned" and ("assigned" in latest or "closed" in latest))
                    or (state not in ("assigned", "accepted") and "closed" in latest)):
                    # open new
                    branches[membername].append({})
                    latest = branches[membername][-1]
                    if latest_requested:
                        latest["requested"] = latest_requested
                        latest_requested = None

                if state in ("assigned", 'accepted'):
                    latest[state] = (row.time, row.who, membername, state, latest_iesg_status)
                else:
                    latest["closed"] = (row.time, row.who, membername, state, latest_iesg_status)


        if branches:
            if non_specific_close:
                # find any open branches
                for m, hs in branches.iteritems():
                    latest = hs[-1]
                    if "assigned" in latest and "closed" not in latest:
                        #print "closing with non specific", docname
                        close_row, iesg_status = non_specific_close
                        latest["closed"] = (close_row.time, close_row.who, m, "done", iesg_status)
            
            document_history[docname] = branches

        # if docname in document_history:
        #     print docname, document_history[docname]

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

        reviewed_rev = row.version if row.version and row.version != "99" else ""
        if row.summary == "noresponse":
            reviewed_rev = ""

        event_collection = None
        branches = document_history.get(row.docname)
        if not branches:
            print "WARNING: no history for", row.docname
        else:
            history = branches.get(row.reviewer)
            if not history:
                print "WARNING: reviewer {} not found in history for".format(row.reviewer), row.docname
            else:
                event_collection = history.pop(0)
                if "requested" not in event_collection:
                    print "WARNING: no requested log entry for", row.docname, [event_collection] + history

                if "assigned" not in event_collection:
                    print "WARNING: no assigned log entry for", row.docname, [event_collection] + history

                if "closed" not in event_collection and row.docstatus in close_states:
                    print "WARNING: no {} log entry for".format("/".join(close_states)), row.docname, [event_collection] + history

                def day_delta(time_from, time_to):
                    if time_from is None or time_to is None:
                        return None

                    return float(time_to[0] - time_from[0]) / (24 * 60 * 60)

                requested_assigned_days = day_delta(event_collection.get("requested"), event_collection.get("assigned"))
                if requested_assigned_days is not None and requested_assigned_days < 0:
                    print "WARNING: assignment before request", requested_assigned_days, row.docname
                at_most_days = 20
                if requested_assigned_days is not None and requested_assigned_days > at_most_days:
                    print "WARNING: more than {} days between request and assignment".format(at_most_days), round(requested_assigned_days), event_collection, row.docname

                if "closed" in event_collection:
                    assigned_closed_days = day_delta(event_collection.get("assigned"), event_collection.get("closed"))
                    if assigned_closed_days is not None and assigned_closed_days < 0:
                        print "WARNING: closure before assignment", assigned_closed_days, row.docname
                    at_most_days = 60
                    if assigned_closed_days is not None and assigned_closed_days > at_most_days and event_collection.get("closed")[3] not in ("noresponse", "withdrawn"):
                        print "WARNING: more than {} days between assignment and completion".format(at_most_days), round(assigned_closed_days), event_collection, row.docname

        if event_collection:
            time = None
            if "requested" in event_collection:
                time = parse_timestamp(event_collection["requested"][0])
            elif "assigned" in event_collection:
                time = parse_timestamp(event_collection["assigned"][0])
            elif "closed" in event_collection:
                time = parse_timestamp(event_collection["closed"][0])
            else:
                time = deadline

        if not deadline and "closed" in event_collection:
            deadline = parse_timestamp(event_collection["closed"][0])

        if not deadline:
            print "SKIPPING WITH NO DEADLINE", row.reviewid, row.docname, meta, event_collection
            continue

        type_slug = None
        if "assigned" in event_collection:
            type_slug = event_collection["assigned"][4]
            if type_slug:
                print "deduced type slug at assignment", type_slug, row.docname

        if not type_slug and "requested" in event_collection:
            type_slug = event_collection["requested"][4]
            if type_slug:
                print "deduced type slug at request", type_slug, row.docname

        if not type_slug and "closed" in event_collection and "assigned" not in event_collection:
            type_slug = event_collection["closed"][4]
            if type_slug:
                print "deduced type slug at closure", type_slug, row.docname

        if not type_slug:
            print "did not deduce type slug, assuming early", row.docname, deadline
            type_slug = "early"

        type_name = type_names[type_slug]

        def fix_docname(docname):
            if docname == "draft-fenner-obsolete":
                docname = "draft-fenner-obsolete-1264"
            return docname

        review_req, _ = ReviewRequest.objects.get_or_create(
            doc_id=fix_docname(row.docname),
            team=team,
            old_id=row.reviewid,
            defaults={
                "state": states["requested"],
                "type": type_name,
                "deadline": deadline.date(),
                "requested_by": system_person,
            }
        )

        review_req.reviewer = known_personnel[row.reviewer] if row.reviewer else None
        review_req.result = results.get(row.summary.lower()) if row.summary else None
        review_req.state = states.get(row.docstatus) if row.docstatus else None
        review_req.type = type_name
        review_req.time = time
        review_req.reviewed_rev = reviewed_rev if review_req.state_id not in ("requested", "accepted") else ""
        review_req.deadline = deadline.date()
        review_req.save()

        completion_event = None

        # review request events
        for key, data in event_collection.iteritems():
            timestamp, who_did_it, reviewer, state, latest_iesg_status = data

            if who_did_it in known_personnel:
                by = known_personnel[who_did_it].person
            else:
                by = system_person

            if key == "requested":
                if "assigned" in event_collection:
                    continue # skip requested unless there's no assigned event

                e = ReviewRequestDocEvent.objects.filter(type="requested_review", doc=review_req.doc, review_request=review_req).first()
                if not e:
                    e = ReviewRequestDocEvent(type="requested_review", doc=review_req.doc, review_request=review_req)
                e.time = time
                e.by = by
                e.desc = "Requested {} review by {}".format(review_req.type.name, review_req.team.acronym.upper())
                e.state = None
                e.skip_community_list_notification = True
                e.save()
                print "imported event requested_review", e.desc, e.doc_id

            elif key == "assigned":
                e = ReviewRequestDocEvent.objects.filter(type="assigned_review_request", doc=review_req.doc, review_request=review_req).first()
                if not e:
                    e = ReviewRequestDocEvent(type="assigned_review_request", doc=review_req.doc, review_request=review_req)
                e.time = parse_timestamp(timestamp)
                e.by = by
                e.desc = "Request for {} review by {} is assigned to {}".format(
                    review_req.type.name,
                    review_req.team.acronym.upper(),
                    review_req.reviewer.person if review_req.reviewer else "(None)",
                )
                e.state = None
                e.skip_community_list_notification = True
                e.save()
                print "imported event assigned_review_request", e.pk, e.desc, e.doc_id

            elif key == "closed" and review_req.state_id not in ("requested", "accepted"):
                e = ReviewRequestDocEvent.objects.filter(type="closed_review_request", doc=review_req.doc, review_request=review_req).first()
                if not e:
                    e = ReviewRequestDocEvent(type="closed_review_request", doc=review_req.doc, review_request=review_req)
                e.time = parse_timestamp(timestamp)
                e.by = by
                e.state = states.get(state) if state else None
                if e.state_id == "rejected":
                    e.desc = "Assignment of request for {} review by {} to {} was rejected".format(
                        review_req.type.name,
                        review_req.team.acronym.upper(),
                        review_req.reviewer.person,
                    )
                elif e.state_id == "completed":
                    e.desc = "Request for {} review by {} {}{}. Reviewer: {}.".format(
                        review_req.type.name,
                        review_req.team.acronym.upper(),
                        review_req.state.name,
                        ": {}".format(review_req.result.name) if review_req.result else "",
                        review_req.reviewer.person,
                    )
                else:
                    e.desc = "Closed request for {} review by {} with state '{}'".format(review_req.type.name, review_req.team.acronym.upper(), e.state.name)
                e.skip_community_list_notification = True
                e.save()
                completion_event = e
                print "imported event closed_review_request", e.desc, e.doc_id

        if review_req.state_id == "completed":
            if not row.reviewurl: # don't have anything to store, so skip
                continue

            if completion_event:
                completion_time = completion_event.time
                completion_by = completion_event.by
            else:
                completion_time = deadline
                completion_by = system_person

            # create the review document
            if review_req.review:
                review = review_req.review
            else:
                for i in range(1, 100):
                    name_components = [
                        "review",
                        strip_prefix(review_req.doc_id, "draft-"),
                        review_req.reviewed_rev,
                        review_req.team.acronym,
                        review_req.type_id,
                        review_req.reviewer.person.ascii_parts()[3],
                        completion_time.date().isoformat(),
                    ]
                    if i > 1:
                        name_components.append(str(i))

                    name = "-".join(c for c in name_components if c).lower()
                    if not Document.objects.filter(name=name).exists():
                        review = Document.objects.create(name=name)
                        DocAlias.objects.create(document=review, name=review.name)
                        break

            review.set_state(State.objects.get(type="review", slug="active"))

            review.time = completion_time
            review.type = DocTypeName.objects.get(slug="review")
            review.rev = "00"
            review.title = "{} Review of {}-{}".format(review_req.type.name, review_req.doc.name, review_req.reviewed_rev)
            review.group = review_req.team
            review.external_url = row.reviewurl

            existing = NewRevisionDocEvent.objects.filter(doc=review).first() or NewRevisionDocEvent(doc=review)
            e.type = "new_revision"
            e.by = completion_by
            e.rev = review.rev
            e.desc = 'New revision available'
            e.time = completion_time
            e.skip_community_list_notification = True

            review.save_with_history([e])

            review_req.review = review
            review_req.save()

            print "imported review document", review_req.doc, review.name

        if review_req.state_id in ("requested", "accepted") and review_req.doc.get_state_slug("draft-iesg") in ["approved", "ann", "rfcqueue", "pub"]:
            review_req.state = states["overtaken"]
            review_req.save()

            if "closed" not in event_collection and "assigned" in event_collection:
                e = ReviewRequestDocEvent.objects.filter(type="closed_review_request", doc=review_req.doc, review_request=review_req).first()
                if not e:
                    e = ReviewRequestDocEvent(type="closed_review_request", doc=review_req.doc, review_request=review_req)
                e.time = datetime.datetime.now()
                e.by = by
                e.state = review_req.state
                e.desc = "Closed request for {} review by {} with state '{}'".format(review_req.type.name, review_req.team.acronym.upper(), e.state.name)
                e.skip_community_list_notification = True
                e.save()
                completion_event = e
                print "imported event closed_review_request (generated upon closing)", e.desc, e.doc_id
            

        print "imported review request", row.reviewid, "as", review_req.pk, review_req.time, review_req.deadline, review_req.type, review_req.doc_id, review_req.state, review_req.doc.get_state_slug("draft-iesg")
