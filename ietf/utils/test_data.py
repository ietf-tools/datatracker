# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.utils.encoding import smart_text

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, DocAlias, State, DocumentAuthor, DocEvent, RelatedDocument, NewRevisionDocEvent
from ietf.group.models import Group, GroupHistory, Role, RoleHistory
from ietf.iesg.models import TelechatDate
from ietf.ipr.models import HolderIprDisclosure, IprDocRel, IprDisclosureStateName, IprLicenseTypeName
from ietf.meeting.models import Meeting, ResourceAssociation
from ietf.name.models import StreamName, DocRelationshipName, RoomResourceName, ConstraintName
from ietf.person.models import Person, Email
from ietf.group.utils import setup_default_community_list_for_group
from ietf.review.models import (ReviewRequest, ReviewerSettings, ReviewResultName, ReviewTypeName, ReviewTeamSettings )
from ietf.person.name import unidecode_name


def create_person(group, role_name, name=None, username=None, email_address=None, password=None, is_staff=False, is_superuser=False):
    """Add person/user/email and role."""
    if not name:
        name = group.acronym.capitalize() + " " + role_name.capitalize()
    if not username:
        username = group.acronym + "-" + role_name
    if not email_address:
        email_address = username + "@example.org"
    if not password:
        password = username + "+password"

    user = User.objects.create(username=username,is_staff=is_staff,is_superuser=is_superuser)
    user.set_password(password)
    user.save()
    person = Person.objects.create(name=name, ascii=unidecode_name(smart_text(name)), user=user)
    email = Email.objects.create(address=email_address, person=person, origin=user.username)
    Role.objects.create(group=group, name_id=role_name, person=person, email=email)
    return person

def create_group(**kwargs):
    group, created = Group.objects.get_or_create(state_id="active", **kwargs)
    return group

def make_immutable_base_data():
    """Some base data (groups, etc.) that doesn't need to be modified by
    tests and is thus safe to load once and for all at the start of
    all tests in a run."""

    # telechat dates
    t = datetime.date.today() + datetime.timedelta(days=1)
    old = TelechatDate.objects.create(date=t - datetime.timedelta(days=14)).date        # pyflakes:ignore
    date1 = TelechatDate.objects.create(date=t).date                                    # pyflakes:ignore
    date2 = TelechatDate.objects.create(date=t + datetime.timedelta(days=14)).date      # pyflakes:ignore
    date3 = TelechatDate.objects.create(date=t + datetime.timedelta(days=14 * 2)).date  # pyflakes:ignore
    date4 = TelechatDate.objects.create(date=t + datetime.timedelta(days=14 * 3)).date  # pyflakes:ignore

    # system
    system_person = Person.objects.create(name="(System)", ascii="(System)")
    Email.objects.create(address="", person=system_person, origin='test')

    # high-level groups
    ietf = create_group(name="IETF", acronym="ietf", type_id="ietf")
    create_person(ietf, "chair")
    create_person(ietf, "admdir")

    irtf = create_group(name="IRTF", acronym="irtf", type_id="irtf")
    create_person(irtf, "chair")

    secretariat = create_group(name="IETF Secretariat", acronym="secretariat", type_id="ietf")
    create_person(secretariat, "secr", name="Sec Retary", username="secretary", is_staff=True, is_superuser=True)

    iab = create_group(name="Internet Architecture Board", acronym="iab", type_id="ietf", parent=ietf)
    create_person(iab, "chair")
    create_person(iab, "member")

    ise = create_group(name="Independent Submission Editor", acronym="ise", type_id="rfcedtyp")
    create_person(ise, "chair")

    rsoc = create_group(name="RFC Series Oversight Committee", acronym="rsoc", type_id="rfcedtyp")
    create_person(rsoc, "chair")

    iepg = create_group(name="IEPG", acronym="iepg", type_id="adhoc")
    create_person(iepg, "chair")
    
    iana = create_group(name="IANA", acronym="iana", type_id="iana")
    create_person(iana, "auth", name="Iña Iana", username="iana", email_address="iana@ia.na")

    rfc_editor = create_group(name="RFC Editor", acronym="rfceditor", type_id="rfcedtyp")
    create_person(rfc_editor, "auth", name="Rfc Editor", username="rfc", email_address="rfc@edit.or")

    iesg = create_group(name="Internet Engineering Steering Group", acronym="iesg", type_id="ietf", parent=ietf) # pyflakes:ignore
    irsg = create_group(name="Internet Research Steering Group", acronym="irsg", type_id="irtf", parent=irtf) # pyflakes:ignore

    individ = create_group(name="Individual submissions", acronym="none", type_id="individ") # pyflakes:ignore

    # one area
    area = create_group(name="Far Future", acronym="farfut", type_id="area", parent=ietf)
    create_person(area, "ad", name="Areað Irector", username="ad", email_address="aread@example.org")

    # second area
    opsarea = create_group(name="Operations", acronym="ops", type_id="area", parent=ietf)
    ops_ad = create_person(opsarea, "ad")
    sops = create_group(name="Server Operations", acronym="sops", type_id="wg", parent=opsarea)
    create_person(sops, "chair", name="Sops Chairman", username="sopschairman")
    create_person(sops, "secr", name="Sops Secretary", username="sopssecretary")
    Role.objects.create(name_id='ad', group=sops, person=ops_ad, email=ops_ad.email())

    # create a bunch of ads for swarm tests
    for i in range(1, 10):
        u = User.objects.create(username="ad%s" % i)
        p = Person.objects.create(name="Ad No%s" % i, ascii="Ad No%s" % i, user=u)
        email = Email.objects.create(address="ad%s@example.org" % i, person=p, origin=u.username)
        if i < 6:
            # active
            Role.objects.create(name_id="ad", group=area, person=p, email=email)
        else:
            # inactive
            areahist = GroupHistory.objects.create(
                group=area,
                name=area.name,
                acronym=area.acronym,
                type_id=area.type_id,
                state_id=area.state_id,
                parent=area.parent
                )
            RoleHistory.objects.create(
                name_id="ad",
                group=areahist,
                person=p,
                email=email)

    # Create some IRSG members (really should add some atlarge and the chair,
    # but this isn't currently essential)
    create_person(irsg, "member", name="R. Searcher", username="rsearcher", email_address="rsearcher@example.org")

    # Create a bunch of IRSG members for swarm tests
    for i in range(1, 5):
        u = User.objects.create(username="irsgmember%s" % i)
        p = Person.objects.create(name="IRSG Member No%s" % i, ascii="IRSG Member No%s" % i, user=u)
        email = Email.objects.create(address="irsgmember%s@example.org" % i, person=p, origin=u.username)
        Role.objects.create(name_id="member", group=irsg, person=p, email=email)

def make_test_data():
    area = Group.objects.get(acronym="farfut")
    ad = Person.objects.get(user__username="ad")
    irtf = Group.objects.get(acronym='irtf')

    # mars WG
    group = Group.objects.create(
        name="Martian Special Interest Group",
        acronym="mars",
        description="This group discusses mars issues.",
        state_id="active",
        type_id="wg",
        parent=area,
        list_email="mars-wg@ietf.org",
        )
    mars_wg = group
    charter = Document.objects.create(
        name="charter-ietf-" + group.acronym,
        type_id="charter",
        title=group.name,
        group=group,
        rev="00",
        )
    charter.set_state(State.objects.get(used=True, slug="approved", type="charter"))
    group.charter = charter
    group.save()
    DocAlias.objects.create(name=charter.name).docs.add(charter)
    setup_default_community_list_for_group(group)

    # ames WG
    group = Group.objects.create(
        name="Asteroid Mining Equipment Standardization Group",
        acronym="ames",
        description="This group works towards standardization of asteroid mining equipment.",
        state_id="proposed",
        type_id="wg",
        parent=area,
        list_email="ames-wg@ietf.org",
        )
    ames_wg = group
    charter = Document.objects.create(
        name="charter-ietf-" + group.acronym,
        type_id="charter",
        title=group.name,
        group=group,
        rev="00",
        )
    charter.set_state(State.objects.get(used=True, slug="infrev", type="charter"))
    DocAlias.objects.create(name=charter.name).docs.add(charter)
    group.charter = charter
    group.save()
    setup_default_community_list_for_group(group)

    # frfarea AG
    frfarea = Group.objects.create(
        name="Far Future Area Group",
        acronym="frfarea",
        description="This group discusses future space colonization issues.",
        state_id="active",
        type_id="ag",
        parent=area,
        list_email="frfarea-ag@ietf.org",
        )

    # irg RG
    irg_rg = Group.objects.create(
        name="Internet Research Group",
        acronym="irg",
        description="This group handles internet research.",
        state_id="active",
        type_id="rg",
        parent=irtf,
        list_email="irg-rg@ietf.org",
        )

    # A research area group
    rag = Group.objects.create(
        name="Internet Research Area Group",
        acronym="irag",
        description="This area group groups internet research.",
        state_id="active",
        type_id="rag",
        parent=irtf,
        list_email="irag@ietf.org",
        )
    #charter = Document.objects.create(
    #    name="charter-ietf-" + group.acronym,
    #    type_id="charter",
    #    title=group.name,
    #    group=group,
    #    rev="00",
    #    )
    #charter.set_state(State.objects.get(used=True, slug="infrev", type="charter"))
    #DocAlias.objects.create(name=charter.name).docs.add(charter)
    #group.charter = charter
    #group.save()

    # plain IETF'er
    u = User.objects.create(username="plain")
    u.set_password("plain+password")
    u.save()
    plainman = Person.objects.create(name="Plain Man", ascii="Plain Man", user=u)
    email = Email.objects.create(address="plain@example.com", person=plainman, origin=u.username)

    # group personnel
    create_person(mars_wg, "chair", name="WG Cháir Man", username="marschairman")
    create_person(mars_wg, "delegate", name="WG Dèlegate", username="marsdelegate")
    create_person(mars_wg, "secr", name="Miss Secretary", username="marssecretary")

    mars_wg.role_set.get_or_create(name_id='ad',person=ad,email=ad.role_email('ad'))
    mars_wg.save()

    create_person(ames_wg, "chair", name="Ames Chair Man", username="ameschairman")
    create_person(ames_wg, "delegate", name="Ames Delegate", username="amesdelegate")
    create_person(ames_wg, "secr", name="Mr Secretary", username="amessecretary")
    ames_wg.role_set.get_or_create(name_id='ad',person=ad,email=ad.role_email('ad'))
    ames_wg.save()

    frfarea.role_set.get_or_create(name_id='chair',person=ad,email=ad.role_email('ad'))
    frfarea.save()

    create_person(irg_rg, "chair", name="Irg Chair Man", username="irgchairman")
    create_person(rag, "chair", name="Rag Chair Man", username="ragchairman")

    # old draft
    old_draft = Document.objects.create(
        name="draft-foo-mars-test",
        time=datetime.datetime.now() - datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
        type_id="draft",
        title="Optimizing Martian Network Topologies",
        stream_id="ietf",
        abstract="Techniques for achieving near-optimal Martian networks.",
        rev="00",
        pages=2,
        expires=datetime.datetime.now(),
        )
    old_draft.set_state(State.objects.get(used=True, type="draft", slug="expired"))
    old_alias = DocAlias.objects.create(name=old_draft.name)
    old_alias.docs.add(old_draft)

    # draft
    draft = Document.objects.create(
        name="draft-ietf-mars-test",
        time=datetime.datetime.now(),
        type_id="draft",
        title="Optimizing Martian Network Topologies",
        stream_id="ietf",
        group=mars_wg,
        abstract="Techniques for achieving near-optimal Martian networks.",
        rev="01",
        pages=2,
        intended_std_level_id="ps",
        shepherd=email,
        ad=ad,
        expires=datetime.datetime.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
        notify="aliens@example.mars",
        note="",
        )

    draft.set_state(State.objects.get(used=True, type="draft", slug="active"))
    draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="pub-req"))
    draft.set_state(State.objects.get(used=True, type="draft-stream-%s" % draft.stream_id, slug="wg-doc"))

    doc_alias = DocAlias.objects.create(name=draft.name)
    doc_alias.docs.add(draft)

    RelatedDocument.objects.create(source=draft, target=old_alias, relationship=DocRelationshipName.objects.get(slug='replaces'))
    old_draft.set_state(State.objects.get(type='draft', slug='repl'))

    DocumentAuthor.objects.create(
        document=draft,
        person=Person.objects.get(email__address="aread@example.org"),
        email=Email.objects.get(address="aread@example.org"),
        country="Germany",
        affiliation="IETF",
        order=1
        )

    # fill in some useful default events
    DocEvent.objects.create(
        type="started_iesg_process",
        by=ad,
        doc=draft,
        rev=draft.rev,
        desc="Started IESG process",
        )

    NewRevisionDocEvent.objects.create(
        type="new_revision",
        by=ad,
        doc=draft,
        desc="New revision available",
        rev="01",
        )

    # IPR
    ipr = HolderIprDisclosure.objects.create(
        by=Person.objects.get(name="(System)"),
        title="Statement regarding rights",
        holder_legal_name="Native Martians United",
        state=IprDisclosureStateName.objects.get(slug='posted'),
        patent_info='Number: US12345\nTitle: A method of transfering bits\nInventor: A. Nonymous\nDate: 2000-01-01',
        holder_contact_name='George',
        holder_contact_email='george@acme.com',
        holder_contact_info='14 Main Street\nEarth',
        licensing=IprLicenseTypeName.objects.get(slug='royalty-free'),
        submitter_name='George',
        submitter_email='george@acme.com',
        )

    IprDocRel.objects.create(
        disclosure=ipr,
        document=doc_alias,
        revisions='00',
        )
    
    # meeting
    ietf72 = Meeting.objects.create(
        number="72",
        type_id="ietf",
        date=datetime.date.today() + datetime.timedelta(days=180),
        city="New York",
        country="US",
        time_zone="US/Eastern",
        break_area="Lounge",
        reg_area="Lobby",
        )
    # Use the "old" conflict names to avoid having to update tests
    for slug in ['conflict', 'conflic2', 'conflic3']:
        ietf72.group_conflict_types.add(ConstraintName.objects.get(slug=slug))

    # interim meeting
    Meeting.objects.create(
        number="interim-2015-mars-01",
        type_id='interim',
        date=datetime.date(2015,1,1),
        city="New York",
        country="US",
        )

    # an independent submission before review
    doc = Document.objects.create(name='draft-imaginary-independent-submission',type_id='draft',rev='00',
        title="Some Independent Notes on Imagination")
    doc.set_state(State.objects.get(used=True, type="draft", slug="active"))    
    DocAlias.objects.create(name=doc.name).docs.add(doc)

    # an irtf submission mid review
    doc = Document.objects.create(name='draft-imaginary-irtf-submission', type_id='draft',rev='00',
        stream=StreamName.objects.get(slug='irtf'), title="The Importance of Research Imagination")
    docalias = DocAlias.objects.create(name=doc.name)
    docalias.docs.add(doc)
    doc.set_state(State.objects.get(type="draft", slug="active"))
    crdoc = Document.objects.create(name='conflict-review-imaginary-irtf-submission', type_id='conflrev',
        rev='00', notify="fsm@ietf.org", title="Conflict Review of IRTF Imagination Document")
    DocAlias.objects.create(name=crdoc.name).docs.add(crdoc)
    crdoc.set_state(State.objects.get(name='Needs Shepherd', type__slug='conflrev'))
    crdoc.relateddocument_set.create(target=docalias,relationship_id='conflrev')
    
    # A status change mid review
    iesg = Group.objects.get(acronym='iesg')
    doc = Document.objects.create(name='status-change-imaginary-mid-review',type_id='statchg', rev='00',
        notify="fsm@ietf.org", group=iesg, title="Status Change Review without Imagination")
    doc.set_state(State.objects.get(slug='needshep',type__slug='statchg'))
    docalias = DocAlias.objects.create(name='status-change-imaginary-mid-review')
    docalias.docs.add(doc)

    # Some things for a status change to affect
    def rfc_for_status_change_test_factory(name,rfc_num,std_level_id):
        target_rfc = Document.objects.create(name=name, type_id='draft', std_level_id=std_level_id, notify="%s@ietf.org"%name)
        target_rfc.set_state(State.objects.get(slug='rfc',type__slug='draft'))
        DocAlias.objects.create(name=name).docs.add(target_rfc)
        DocAlias.objects.create(name='rfc%d'%rfc_num).docs.add(target_rfc)
        return target_rfc
    rfc_for_status_change_test_factory('draft-ietf-random-thing',9999,'ps')
    rfc_for_status_change_test_factory('draft-ietf-random-otherthing',9998,'inf')
    rfc_for_status_change_test_factory('draft-was-never-issued',14,'unkn')

    # Session Request ResourceAssociation
    name = RoomResourceName.objects.get(slug='project')
    ResourceAssociation.objects.create(name=name,icon='projector.png',desc='Projector in room')
    
    # Instances of the remaining document types 
    # (Except liaison, liai-att, and recording  which the code in ietf.doc does not use...)
    # Meeting-related documents are created in make_meeting_test_data, and
    # associated with a session

    return draft


def make_review_data(doc):
    team1 = create_group(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
    team2 = create_group(acronym="reviewteam2", name="Review Team 2", type_id="review", list_email="reviewteam2@ietf.org", parent=Group.objects.get(acronym="farfut"))
    team3 = create_group(acronym="reviewteam3", name="Review Team 3", type_id="review", list_email="reviewteam2@ietf.org", parent=Group.objects.get(acronym="farfut"))
    for team in (team1, team2, team3):
        ReviewTeamSettings.objects.create(group=team)
        for r in ReviewResultName.objects.filter(slug__in=["issues", "ready-issues", "ready", "not-ready"]):
            team.reviewteamsettings.review_results.add(r)
        for t in ReviewTypeName.objects.filter(slug__in=["early", "lc", "telechat"]):
            team.reviewteamsettings.review_types.add(t)

    u = User.objects.create(username="reviewer")
    u.set_password("reviewer+password")
    u.save()
    reviewer = Person.objects.create(name="Some Réviewer", ascii="Some Reviewer", user=u)
    email = Email.objects.create(address="reviewer@example.com", person=reviewer, origin=u.username)

    for team in (team1, team2, team3):
        Role.objects.create(name_id="reviewer", person=reviewer, email=email, group=team)
        ReviewerSettings.objects.create(team=team, person=reviewer, min_interval=14, skip_next=0)

    review_req = ReviewRequest.objects.create(
        doc=doc,
        team=team1,
        type_id="early",
        deadline=datetime.datetime.now() + datetime.timedelta(days=20),
        state_id="accepted",
        requested_by=reviewer,
        reviewer=email,
    )

    p = Person.objects.get(user__username="marschairman")
    Role.objects.create(name_id="reviewer", person=p, email=p.email_set.first(), group=team1)

    u = User.objects.create(username="reviewsecretary")
    u.set_password("reviewsecretary+password")
    u.save()
    reviewsecretary = Person.objects.create(name="Réview Secretary", ascii="Review Secretary", user=u)
    reviewsecretary_email = Email.objects.create(address="reviewsecretary@example.com", person=reviewsecretary, origin=u.username)
    Role.objects.create(name_id="secr", person=reviewsecretary, email=reviewsecretary_email, group=team1)

    u = User.objects.create(username="reviewsecretary3")
    u.set_password("reviewsecretary3+password")
    u.save()
    reviewsecretary3 = Person.objects.create(name="Réview Secretary3", ascii="Review Secretary3", user=u)
    reviewsecretary3_email = Email.objects.create(address="reviewsecretary3@example.com", person=reviewsecretary, origin=u.username)
    Role.objects.create(name_id="secr", person=reviewsecretary3, email=reviewsecretary3_email, group=team3)
    
    return review_req

