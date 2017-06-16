import datetime

from ietf.utils import unaccent
from ietf.person.models import Person, Email, Alias
from ietf.doc.models import NewRevisionDocEvent
from ietf.idtracker.models import EmailAddress

def clean_email_address(addr):
    addr = addr.replace("!", "@").replace("(at)", "@") # some obvious @ replacements
    # whack surrounding <...>    
    addr = addr[addr.rfind('<') + 1:]
    end = addr.find('>')
    if end != -1:
        addr = addr[:end]
    addr = addr.strip()
    if not "@" in addr:
        return ""
    else:
        return addr

def person_name(person):
    def clean_prefix(n):
        n = clean(n)
        if n in [".", "Mr.", "<s/", "e", "fas", "lk", "Miss", "Mr", "Mr,", "Mr.", "Mr..", "MRS", "Mrs.", "ms", "Ms,", "Ms.", "Ms.    L", "mw", "prefix", "q", "qjfglesjtg", "s", "te mr", "\Mr.", "M.", "M"]:
            return "" # skip

        fixes = { "Dr": "Dr.", "Lt.Colonel": "Lt. Col.", "Prof": "Prof.", "Prof.Dr.": "Prof. Dr.", "Professort": "Professor" }
        return fixes.get(n, n)

    def clean_suffix(n):
        n = clean(n)
        if n in ["q", "a", "suffix", "u", "w", "x", "\\"]:
            return "" # skip

        fixes = { "Jr": "Jr.", "Ph. D.": "Ph.D.", "Ph.D": "Ph.D.", "PhD":"Ph.D.", "Phd.": "Phd.", "Scd": "Sc.D." }
        return fixes.get(n, n)

    def clean(n):
        if not n:
            return ""
        return n.replace("]", "").strip()

    def initial_fixup(n):
        if len(n) == 1:
            return n + "."
        return n

    names = [clean_prefix(person.name_prefix), clean(person.first_name),
             initial_fixup(clean(person.middle_initial)), clean(person.last_name), clean_suffix(person.name_suffix)]

    return u" ".join(n for n in names if n)

def old_person_to_person(person):
    try:
        return Person.objects.get(id=person.pk)
    except Person.DoesNotExist:
        return Person.objects.get(alias__name=person_name(person))

def old_person_to_email(person):
    # try connected addresses
    addresses = person.emailaddress_set.filter(address__contains="@").order_by('priority')[:1]
    if addresses:
        addr = clean_email_address(addresses[0].address)
        priority = addresses[0].priority
        return (addr, priority)

    # try to see if there's a person with the same name and an email address
    addresses = EmailAddress.objects.filter(person_or_org__first_name=person.first_name, person_or_org__last_name=person.last_name).filter(address__contains="@").order_by('priority')[:1]
    if addresses:
        addr = clean_email_address(addresses[0].address)
        priority = addresses[0].priority
        return (addr, priority)

    # otherwise try the short list
    hardcoded_emails = {
        "Dinara Suleymanova": "dinaras@ietf.org",
        "Dow Street": "dow.street@linquest.com",
        "Xiaoya Yang": "xiaoya.yang@itu.int",
        }

    addr = hardcoded_emails.get(u"%s %s" % (person.first_name, person.last_name), "")
    priority = 1
    return (addr, priority)



def calc_email_import_time(priority):
    # we may import some old email addresses that are now
    # inactive, to ensure everything is not completely borked, we
    # want to ensure that high-priority (< 100) email addresses
    # end up later (in reverse of priority - I-D addresses follow
    # the normal ordering, since higher I-D id usually means later)
    if priority < 100:
        d = -priority
    else:
        d = priority - 36000
    return datetime.datetime(1970, 1, 2, 0, 0, 0) + datetime.timedelta(seconds=d)

def get_or_create_email(o, create_fake):
    # take o.person (or o) and get or create new Email and Person objects
    person = o.person if hasattr(o, "person") else o

    name = person_name(person)

    email, priority = old_person_to_email(person)
    if not email:
        if create_fake:
            email = u"unknown-email-%s" % name.replace(" ", "-")
            print ("USING FAKE EMAIL %s for %s %s" % (email, person.pk, name)).encode('utf-8')
        else:
            print ("NO EMAIL FOR %s %s %s %s" % (o.__class__, o.pk, person.pk, name)).encode('utf-8')
            return None
    
    e, _ = Email.objects.select_related("person").get_or_create(address=email)
    if not e.person:
        asciified = unaccent.asciify(name)
        aliases = Alias.objects.filter(name__in=(name, asciified)).select_related('person')
        if aliases:
            p = aliases[0].person
        else:
            p = Person(id=person.pk, name=name, ascii=asciified)
            
            from ietf.idtracker.models import PostalAddress
            addresses = person.postaladdress_set.filter(address_priority=1)
            if addresses:
                p.affiliation = (addresses[0].affiliated_company or "").strip()
                # should probably import p.address here

            p.save()
            
            Alias.objects.create(name=p.name, person=p)
            if p.ascii != p.name:
                Alias.objects.create(name=p.ascii, person=p)

        e.person = p
        e.time = calc_email_import_time(priority)
        e.save()
    else:
        if e.person.name != name:
            if not Alias.objects.filter(name=name):
                Alias.objects.create(name=name, person=e.person)
            # take longest name rather than the first we encounter
            if len(name) > e.person.name:
                e.person.name = name
                e.person.save()

    return e

def possibly_import_other_priority_email(email, old_email):
    addr = clean_email_address(old_email.address or "")
    if not addr or addr.lower() == email.address.lower():
        return

    try:
        e = Email.objects.get(address=addr)
        if e.person != email.person:
            e.person = email.person
            e.save()
    except Email.DoesNotExist:
        Email.objects.create(address=addr, person=email.person,
                             time=calc_email_import_time(old_email.priority))

def make_revision_event(doc, system_person):
    try:
        e = NewRevisionDocEvent.objects.get(doc=doc, type="new_revision")
    except NewRevisionDocEvent.DoesNotExist:
        e = NewRevisionDocEvent(doc=doc, type="new_revision")
    e.rev = doc.rev
    e.time = doc.time
    e.by = system_person
    e.desc = "Added new revision"

    return e
    

def dont_save_queries():
    # prevent memory from leaking when settings.DEBUG=True
    from django.db import connection
    class DontSaveQueries(object):
        def append(self, x):
            pass 
    connection.queries = DontSaveQueries()
