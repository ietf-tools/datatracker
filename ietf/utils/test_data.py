import datetime

from django.conf import settings
from django.contrib.auth.models import User

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, DocAlias, State, DocumentAuthor, BallotType, DocEvent, BallotDocEvent
from ietf.group.models import Group, GroupHistory, Role, RoleHistory
from ietf.iesg.models import TelechatDate
from ietf.ipr.models import IprDetail, IprDocAlias
from ietf.meeting.models import Meeting
from ietf.name.models import StreamName
from ietf.person.models import Person, Alias, Email

def create_person(group, role_name, name=None, username=None, email_address=None, password=None):
    """Add person/user/email and role."""
    if not name:
        name = group.acronym.capitalize() + " " + role_name.capitalize()
    if not username:
        username = group.acronym + "-" + role_name
    if not email_address:
        email_address = username + "@ietf.org"
    if not password:
        password = username + "+password"

    user = User.objects.create(username=username)
    user.set_password(password)
    user.save()
    person = Person.objects.create(name=name, ascii=name, user=user)
    Alias.objects.create(name=name, person=person)
    email = Email.objects.create(address=email_address, person=person)
    Role.objects.create(group=group, name_id=role_name, person=person, email=email)

def create_group(**kwargs):
    return Group.objects.create(state_id="active", **kwargs)

def make_immutable_base_data():
    """Some base data (groups, etc.) that doesn't need to be modified by
    tests and is thus safe to load once and for all at the start of
    all tests in a run."""

    # telechat dates
    t = datetime.date.today()
    old = TelechatDate.objects.create(date=t - datetime.timedelta(days=14)).date        # pyflakes:ignore
    date1 = TelechatDate.objects.create(date=t).date                                    # pyflakes:ignore
    date2 = TelechatDate.objects.create(date=t + datetime.timedelta(days=14)).date      # pyflakes:ignore
    date3 = TelechatDate.objects.create(date=t + datetime.timedelta(days=14 * 2)).date  # pyflakes:ignore
    date4 = TelechatDate.objects.create(date=t + datetime.timedelta(days=14 * 3)).date  # pyflakes:ignore

    # system
    system_person = Person.objects.create(name="(System)", ascii="(System)", address="")
    Alias.objects.create(person=system_person, name=system_person.name)
    Email.objects.create(address="", person=system_person)

    # high-level groups
    ietf = create_group(name="IETF", acronym="ietf", type_id="ietf")
    create_person(ietf, "chair")
    create_person(ietf, "admdir")

    irtf = create_group(name="IRTF", acronym="irtf", type_id="irtf")
    create_person(irtf, "chair")

    secretariat = create_group(name="IETF Secretariat", acronym="secretariat", type_id="ietf")
    create_person(secretariat, "secr", name="Sec Retary", username="secretary")

    iab = create_group(name="Internet Architecture Board", acronym="iab", type_id="ietf", parent=ietf)
    create_person(iab, "chair")

    ise = create_group(name="Independent Submission Editor", acronym="ise", type_id="ietf")
    create_person(ise, "chair")

    rsoc = create_group(name="RFC Series Oversight Committee", acronym="rsoc", type_id="ietf")
    create_person(rsoc, "chair")

    iepg = create_group(name="IEPG", acronym="iepg", type_id="ietf")
    create_person(iepg, "chair")
    
    iana = create_group(name="IANA", acronym="iana", type_id="ietf")
    create_person(iana, "auth", name="Ina Iana", username="iana", email_address="iana@ia.na")

    rfc_editor = create_group(name="RFC Editor", acronym="rfceditor", type_id="rfcedtyp")
    create_person(rfc_editor, "auth", name="Rfc Editor", username="rfc", email_address="rfc@edit.or")

    iesg = create_group(name="Internet Engineering Steering Group", acronym="iesg", type_id="ietf", parent=ietf) # pyflakes:ignore

    individ = create_group(name="Individual submissions", acronym="none", type_id="individ") # pyflakes:ignore

    # one area
    area = create_group(name="Far Future", acronym="farfut", type_id="area", parent=ietf)
    create_person(area, "ad", name="Aread Irector", username="ad", email_address="aread@ietf.org")

    # create a bunch of ads for swarm tests
    for i in range(1, 10):
        u = User.objects.create(username="ad%s" % i)
        p = Person.objects.create(name="Ad No%s" % i, ascii="Ad No%s" % i, user=u)
        Alias.objects.create(name=p.name, person=p)
        email = Email.objects.create(address="ad%s@ietf.org" % i, person=p)
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

def make_test_data():
    area = Group.objects.get(acronym="farfut")
    ad = Person.objects.get(user__username="ad")

    # mars WG
    group = Group.objects.create(
        name="Martian Special Interest Group",
        acronym="mars",
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
    DocAlias.objects.create(
        name=charter.name,
        document=charter
        )
    # ames WG
    group = Group.objects.create(
        name="Asteroid Mining Equipment Standardization Group",
        acronym="ames",
        state_id="proposed",
        type_id="wg",
        parent=area,
        list_email="ames-wg@ietf.org",
        )
    charter = Document.objects.create(
        name="charter-ietf-" + group.acronym,
        type_id="charter",
        title=group.name,
        group=group,
        rev="00",
        )
    charter.set_state(State.objects.get(used=True, slug="infrev", type="charter"))
    DocAlias.objects.create(
        name=charter.name,
        document=charter
        )
    group.charter = charter
    group.save()

    # plain IETF'er
    u = User.objects.create(username="plain")
    u.set_password("plain+password")
    u.save()
    plainman = Person.objects.create(name="Plain Man", ascii="Plain Man", user=u)
    email = Email.objects.create(address="plain@example.com", person=plainman)

    # group personnel
    create_person(mars_wg, "chair", name="WG Chair Man", username="marschairman")
    create_person(mars_wg, "delegate", name="WG Delegate", username="marsdelegate")
    
    mars_wg.ad = ad
    mars_wg.save()


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

    doc_alias = DocAlias.objects.create(
        document=draft,
        name=draft.name,
        )

    DocumentAuthor.objects.create(
        document=draft,
        author=Email.objects.get(address="aread@ietf.org"),
        order=1
        )

    # fill in some useful default events
    DocEvent.objects.create(
        type="started_iesg_process",
        by=ad,
        doc=draft,
        desc="Started IESG process",
        )

    BallotDocEvent.objects.create(
        type="created_ballot",
        ballot_type=BallotType.objects.get(doc_type="draft", slug="approve"),
        by=ad,
        doc=draft,
        desc="Created ballot",
        )

    # IPR
    ipr = IprDetail.objects.create(
        title="Statement regarding rights",
        legal_name="Native Martians United",
        is_pending=0,
        applies_to_all=1,
        licensing_option=1,
        lic_opt_a_sub=2,
        lic_opt_b_sub=2,
        lic_opt_c_sub=2,
        patents="PTO12345",
        date_applied="foo",
        country="Whole World",
        comments="",
        lic_checkbox=True,
        other_notes="",
        status=1,
        generic=0,
        third_party=0,
        submitted_date=datetime.date.today(),
        )

    IprDocAlias.objects.create(
        ipr=ipr,
        doc_alias=doc_alias,
        rev="00",
        )
    
    # meeting
    Meeting.objects.create(
        number="42",
        type_id="ietf",
        date=datetime.date.today() + datetime.timedelta(days=180),
        city="New York",
        country="US",
        time_zone="US/Eastern",
        break_area="Lounge",
        reg_area="Lobby",
        )

    # an independent submission before review
    doc = Document.objects.create(name='draft-imaginary-independent-submission',type_id='draft')
    doc.set_state(State.objects.get(used=True, type="draft", slug="active"))    
    DocAlias.objects.create(name=doc.name, document=doc)

    # an irtf submission mid review
    doc = Document.objects.create(name='draft-imaginary-irtf-submission', type_id='draft')
    docalias = DocAlias.objects.create(name=doc.name, document=doc)
    doc.stream = StreamName.objects.get(slug='irtf')
    doc.save()
    doc.set_state(State.objects.get(type="draft", slug="active"))
    crdoc = Document.objects.create(name='conflict-review-imaginary-irtf-submission', type_id='conflrev', rev='00', notify="fsm@ietf.org")
    DocAlias.objects.create(name=crdoc.name, document=crdoc)
    crdoc.set_state(State.objects.get(name='Needs Shepherd', type__slug='conflrev'))
    crdoc.relateddocument_set.create(target=docalias,relationship_id='conflrev')
    
    # A status change mid review
    iesg = Group.objects.get(acronym='iesg')
    doc = Document.objects.create(name='status-change-imaginary-mid-review',type_id='statchg', rev='00', notify="fsm@ietf.org",group=iesg)
    doc.set_state(State.objects.get(slug='needshep',type__slug='statchg'))
    doc.save()
    docalias = DocAlias.objects.create(name='status-change-imaginary-mid-review',document=doc)

    # Some things for a status change to affect
    def rfc_for_status_change_test_factory(name,rfc_num,std_level_id):
        target_rfc = Document.objects.create(name=name, type_id='draft', std_level_id=std_level_id)
        target_rfc.set_state(State.objects.get(slug='rfc',type__slug='draft'))
        target_rfc.notify = "%s@ietf.org"%name
        target_rfc.save()
        docalias = DocAlias.objects.create(name=name,document=target_rfc)
        docalias = DocAlias.objects.create(name='rfc%d'%rfc_num,document=target_rfc) # pyflakes:ignore
        return target_rfc
    rfc_for_status_change_test_factory('draft-ietf-random-thing',9999,'ps')
    rfc_for_status_change_test_factory('draft-ietf-random-otherthing',9998,'inf')
    rfc_for_status_change_test_factory('draft-was-never-issued',14,'unkn')

    return draft
