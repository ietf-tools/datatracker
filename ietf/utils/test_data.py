from django.conf import settings
from django.contrib.auth.models import User

from ietf.iesg.models import TelechatDate
from ietf.ipr.models import IprDetail, IprDocAlias
from ietf.meeting.models import Meeting
from ietf.doc.models import *
from ietf.doc.utils import *
from ietf.name.models import *
from ietf.group.models import *
from ietf.person.models import *

import debug

def make_test_data():
    # telechat dates
    t = datetime.date.today()
    old = TelechatDate.objects.create(date=t - datetime.timedelta(days=14)).date
    date1 = TelechatDate.objects.create(date=t).date
    date2 = TelechatDate.objects.create(date=t + datetime.timedelta(days=14)).date
    date3 = TelechatDate.objects.create(date=t + datetime.timedelta(days=14 * 2)).date
    date4 = TelechatDate.objects.create(date=t + datetime.timedelta(days=14 * 3)).date

    # groups
    secretariat, created = Group.objects.get_or_create(
        name="IETF Secretariat",
        acronym="secretariat",
        state_id="active",
        type_id="ietf",
        parent=None)
    ietf, created = Group.objects.get_or_create(
        name="IETF",
        acronym="ietf",
        state_id="active",
        type_id="ietf",
        parent=None)

# XXX As given below, the group objects created doesn't match what's in the
# fixtures, so if both are used, things blow up.  The code below should
# probably be updated to match what's in the fixtures, making the fixtures
# unnecessary for a number of test cases.

#     irtf, created = Group.objects.get_or_create(
#         name="IRTF",
#         acronym="irtf",
#         state_id="active",
#         type_id="irtf",
#         parent=None)
#     for g,t,n,p in [("iab","ietf", "Internet Architecture Board",1),  ("ise","ietf", "Independent Submission Editor", None), ("iesg","ietf", "Internet Engineering Steering Group", 1), ]:
#         Group.objects.get_or_create(
#             name=n,
#             acronym=g,
#             state_id="active",
#             type_id=t,
#             parent_id=p)
    area = Group.objects.create(
        name="Far Future",
        acronym="farfut",
        state_id="active",
        type_id="area",
        parent=ietf)
#     individ, created = Group.objects.get_or_create(
#         name="Individual submissions",
#         acronym="none",
#         state_id="active",
#         type_id="individ",
#         parent=None)
    # mars WG
    group  = Group.objects.create(
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

    # persons

    # system
    system_person, created = Person.objects.get_or_create(
#        id=0, # special value
        name="(System)",
        ascii="(System)",
        address="",
        )
    system_person.save()

    # IANA and RFC Editor groups
    iana, created = Group.objects.get_or_create(
        name="IANA",
        acronym="iana",
        state_id="active",
        type_id="ietf",
        parent=None,
        )
    rfc_editor, created = Group.objects.get_or_create(
        name="RFC Editor",
        acronym="rfceditor",
        state_id="active",
        type_id="rfcedtyp",
        parent=None,
        )

#    if system_person.id != 0: # work around bug in Django
#        Person.objects.filter(id=system_person.id).update(id=0)
#        system_person = Person.objects.get(id=0)

    Alias.objects.get_or_create(person=system_person, name=system_person.name)
    Email.objects.get_or_create(address="", person=system_person)

    # plain IETF'er
    u, created = User.objects.get_or_create(username="plain")
    plainman, created = Person.objects.get_or_create(
        name="Plain Man",
        ascii="Plain Man",
        user=u)
    email, created = Email.objects.get_or_create(
        address="plain@example.com",
        person=plainman)
    
    # ad
    u = User.objects.create(username="ad")
    ad = p = Person.objects.create(
        name="Aread Irector",
        ascii="Aread Irector",
        user=u)
    email = Email.objects.create(
        address="aread@ietf.org",
        person=p)
    Role.objects.create(
        name_id="ad",
        group=area,
        person=p,
        email=email)

    mars_wg.ad = ad
    mars_wg.save()

    # create a bunch of ads for swarm tests
    for i in range(1, 10):
        u = User.objects.create(username="ad%s" % i)
        p = Person.objects.create(
            name="Ad No%s" % i,
            ascii="Ad No%s" % i,
            user=u)
        email = Email.objects.create(
            address="ad%s@ietf.org" % i,
            person=p)
        if i < 6:
            # active
            Role.objects.create(
                name_id="ad",
                group=area,
                person=p,
                email=email)
        else:
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
    
    # stream chairs
    for stream in ['ietf','irtf','iab','iesg']:
        u = User.objects.create( username= ("%schair"%stream) )
        p = Person.objects.create(
            name="%s chair"%stream,
            ascii="%s chair"%stream,
            user = u,
            )
        chairmail = Email.objects.create(
            address="%schair@ietf.org"%stream,
            person = p,
            )
        Role.objects.create(
            name_id = "chair",
            group = Group.objects.get(acronym=stream),
            person = p,
            email = chairmail,
            )

    # group chair
    u = User.objects.create(username="marschairman")
    p = Person.objects.create(
        name="WG Chair Man",
        ascii="WG Chair Man",
        user=u
        )
    wgchair = Email.objects.create(
        address="wgchairman@ietf.org",
        person=p)
    Role.objects.create(
        name_id="chair",
        group=mars_wg,
        person=p,
        email=wgchair,
        )

    # group delegate
    u = User.objects.create(username="wgdelegate")
    p = Person.objects.create(
        name="WG Delegate",
        ascii="WG Delegate",
        user=u
        )
    email = Email.objects.create(
        address="wgdelegate@ietf.org",
        person=p)
    Role.objects.create(
        name_id="delegate",
        group=mars_wg,
        person=p,
        email=email,
        )

    # secretary
    u = User.objects.create(username="secretary")
    p = Person.objects.create(
        name="Sec Retary",
        ascii="Sec Retary",
        user=u)
    email = Email.objects.create(
        address="sec.retary@ietf.org",
        person=p)
    Role.objects.create(
        name_id="secr",
        group=secretariat,
        person=p,
        email=email,
        )

    # IANA user
    u = User.objects.create(username="iana")
    p = Person.objects.create(
        name="Ina Iana",
        ascii="Ina Iana",
        user=u)
    Alias.objects.create(
        name=p.name,
        person=p)
    email = Email.objects.create(
        address="iana@ia.na",
        person=p)
    Role.objects.create(
        name_id="auth",
        group=iana,
        email=email,
        person=p,
        )

    # RFC Editor user
    u = User.objects.create(username="rfc")
    p = Person.objects.create(
        name="Rfc Editor",
        ascii="Rfc Editor",
        user=u)
    email = Email.objects.create(
        address="rfc@edit.or",
        person=p)
    Role.objects.create(
        name_id="auth",
        group=rfc_editor,
        email=email,
        person=p,
        )

    # Secretariat user
    u, created = User.objects.get_or_create(id=509, username="wnl")
    p, created = Person.objects.get_or_create(
        name="Wanda Lo",
        ascii="Wanda Lo",
        user=u)
    email, created = Email.objects.get_or_create(
        address="wnl@amsl.com",
        person=p)
    Role.objects.get_or_create(
        name_id="auth",
        group=secretariat,
        email=email,
        person=p,
        )
    
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
        shepherd=plainman,
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
        comments="",
        lic_checkbox=True,
        other_notes="",
        status=1,
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
    target_rfc = Document.objects.create(name='draft-ietf-random-thing', type_id='draft', std_level_id='ps')
    target_rfc.set_state(State.objects.get(slug='rfc',type__slug='draft'))
    target_rfc.save()
    docalias = DocAlias.objects.create(name='draft-ietf-random-thing',document=target_rfc)
    docalias = DocAlias.objects.create(name='rfc9999',document=target_rfc)
    target_rfc = Document.objects.create(name='draft-ietf-random-otherthing', type_id='draft', std_level_id='inf')
    target_rfc.set_state(State.objects.get(slug='rfc',type__slug='draft'))
    target_rfc.save()
    docalias = DocAlias.objects.create(name='draft-ietf-random-otherthing',document=target_rfc)
    docalias = DocAlias.objects.create(name='rfc9998',document=target_rfc)

    return draft
