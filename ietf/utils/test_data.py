from django.contrib.auth.models import User

from ietf.iesg.models import TelechatDates, WGAction
from ietf.ipr.models import IprDetail, IprDocAlias
from ietf.meeting.models import Meeting
from redesign.doc.models import *
from redesign.doc.utils import *
from redesign.name.models import *
from redesign.group.models import *
from redesign.person.models import *

def make_test_data():
    # groups
    secretariat = Group.objects.create(
        name="Secretariat",
        acronym="secretariat",
        state_id="active",
        type_id="ietf",
        parent=None)
    ietf = Group.objects.create(
        name="IETF",
        acronym="ietf",
        state_id="active",
        type_id="ietf",
        parent=None)
    for x in ["irtf", "iab", "ise"]:
        Group.objects.create(
            name=x.upper(),
            acronym=x,
            state_id="active",
            type_id="ietf",
            parent=None)
    area = Group.objects.create(
        name="Far Future",
        acronym="farfut",
        state_id="active",
        type_id="area",
        parent=ietf)
    group = Group.objects.create(
        name="Martian Special Interest Group",
        acronym="mars",
        state_id="active",
        type_id="wg",
        parent=area,
        )
    individ = Group.objects.create(
        name="Individual submissions",
        acronym="none",
        state_id="active",
        type_id="individ",
        parent=None)
    
    # persons

    # system
    system_person = Person.objects.create(
        id=0, # special value
        name="(System)",
        ascii="(System)",
        address="",
        )
    
    if system_person.id != 0: # work around bug in Django
        Person.objects.filter(id=system_person.id).update(id=0)
        system_person = Person.objects.get(id=0)

    Alias.objects.get_or_create(person=system_person, name=system_person.name)
    Email.objects.get_or_create(address="", person=system_person)

    # plain IETF'er
    u = User.objects.create(username="plain")
    plainman = Person.objects.create(
        name="Plain Man",
        ascii="Plain Man",
        user=u)
    email = Email.objects.create(
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
        group=group,
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
        group=group,
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

    # draft
    draft = Document.objects.create(
        name="draft-ietf-mars-test",
        time=datetime.datetime.now(),
        type_id="draft",
        title="Optimizing Martian Network Topologies",
        stream_id="ietf",
        group=group,
        abstract="Techniques for achieving near-optimal Martian networks.",
        rev="01",
        pages=2,
        intended_std_level_id="ps",
        shepherd=plainman,
        ad=ad,
        notify="aliens@example.mars",
        note="",
        )

    draft.set_state(State.objects.get(type="draft", slug="active"))
    draft.set_state(State.objects.get(type="draft-iesg", slug="pub-req"))
    draft.set_state(State.objects.get(type="draft-stream-%s" % draft.stream_id, slug="wg-doc"))

    doc_alias = DocAlias.objects.create(
        document=draft,
        name=draft.name,
        )

    DocumentAuthor.objects.create(
        document=draft,
        author=Email.objects.get(address="aread@ietf.org"),
        order=1
        )

    # draft has only one event
    DocEvent.objects.create(
        type="started_iesg_process",
        by=ad,
        doc=draft,
        desc="Added draft",
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
    
    # telechat dates
    t = datetime.date.today()
    dates = TelechatDates(date1=t,
                          date2=t + datetime.timedelta(days=7),
                          date3=t + datetime.timedelta(days=14),
                          date4=t + datetime.timedelta(days=21),
                          )
    super(dates.__class__, dates).save(force_insert=True) # work-around hard-coded save block

    # WG Actions
    group = Group.objects.create(
        name="Asteroid Mining Equipment Standardization Group",
        acronym="ames",
        state_id="proposed",
        type_id="wg",
        parent=area,
        )
    WGAction.objects.create(
        pk=group.pk,
        note="",
        status_date=datetime.date.today(),
        agenda=1,
        token_name="Aread",
        category=13,
        telechat_date=dates.date2
        )

    # Meeting
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
    
    return draft
